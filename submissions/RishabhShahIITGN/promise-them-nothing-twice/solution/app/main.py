import os
import json
import uuid
from typing import Optional
from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.responses import JSONResponse
import redis.asyncio as aioredis
import redis

BASE_DIR = os.path.dirname(__file__)
LUA_PATH = os.path.join(BASE_DIR, '..', 'limiter', 'redis_scripts', 'sliding_window.lua')
CONFIG_PATH = os.path.join(BASE_DIR, 'config', 'customers.json')

app = FastAPI()

# Globals populated at startup
redis_client: Optional[aioredis.Redis] = None
rl_sha: Optional[str] = None
CUSTOMERS = {}
WINDOW_MS = 60_000


@app.on_event('startup')
async def startup_event():
    global redis_client, rl_sha, CUSTOMERS
    # load customer config
    with open(CONFIG_PATH, 'r') as f:
        CUSTOMERS = json.load(f)
    # create redis client
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    redis_client = aioredis.from_url(redis_url, decode_responses=True)
    # load lua script
    lua_path = os.path.join(os.path.dirname(__file__), '..', 'limiter', 'redis_scripts', 'sliding_window.lua')
    lua_path = os.path.normpath(lua_path)
    with open(lua_path, 'r') as f:
        script_src = f.read()
    # script_load returns SHA
    rl_sha = await redis_client.script_load(script_src)


@app.on_event('shutdown')
async def shutdown_event():
    global redis_client
    if redis_client:
        await redis_client.close()


@app.get('/health')
async def health():
    # Check Redis connection
    redis_ok = False
    try:
        # use ping with timeout
        if redis_client:
            await redis_client.ping()
            redis_ok = True
    except Exception:
        redis_ok = False
    return JSONResponse({'status': 'ok', 'redis': redis_ok})


@app.get('/api/resource')
async def get_resource(response: Response, x_customer_id: Optional[str] = Header(None)):
    if not x_customer_id:
        raise HTTPException(status_code=400, detail='Missing X-Customer-ID header')
    cust = x_customer_id
    quota = CUSTOMERS.get(cust)
    if quota is None:
        # default to 10 for unknown customers
        quota = 10
    key = f"rl:{cust}"
    member = f"{uuid.uuid4()}"
    try:
        # call Lua script via EVALSHA
        # KEYS[1] then ARGV
        res = await redis_client.evalsha(rl_sha, 1, key, str(quota), str(WINDOW_MS), member)
    except aioredis.exceptions.RedisError:
        # fail-closed
        headers = {'X-Service-Dependency': 'redis'}
        return JSONResponse({'detail': 'dependency failure'}, status_code=503, headers=headers)
    except Exception:
        headers = {'X-Service-Dependency': 'redis'}
        return JSONResponse({'detail': 'dependency failure'}, status_code=503, headers=headers)
    # res: [allowed, remaining, limit, retry_after]
    try:
        allowed = int(res[0])
        remaining = int(res[1])
        limit = int(res[2])
        retry_after = int(res[3])
    except Exception:
        # malformed script response
        return JSONResponse({'detail': 'rate limiter error'}, status_code=500)
    # set headers
    response.headers['X-RateLimit-Limit'] = str(limit)
    response.headers['X-RateLimit-Remaining'] = str(remaining)
    if allowed == 1:
        return JSONResponse({'result': 'ok'}, status_code=200)
    else:
        # include Retry-After
        headers = {'Retry-After': str(retry_after)}
        response = JSONResponse({'detail': 'Too Many Requests'}, status_code=429, headers=headers)
        response.headers['X-RateLimit-Limit'] = str(limit)
        response.headers['X-RateLimit-Remaining'] = '0'
        response.headers['Retry-After'] = str(retry_after)
        return response
