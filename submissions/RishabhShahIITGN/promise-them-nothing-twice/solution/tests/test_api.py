import os
import time
import json
from fastapi.testclient import TestClient
from unittest.mock import patch
import redis
import pytest

from solution.app.main import app

REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
LUA_PATH = os.path.join(os.path.dirname(__file__), '..', 'limiter', 'redis_scripts', 'sliding_window.lua')

@pytest.fixture(scope='module')
def client():
    client = TestClient(app)
    yield client

@pytest.fixture(scope='module')
def raw_redis():
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        r.ping()
    except Exception:
        pytest.skip(f"Redis not available at {REDIS_URL}")
    # Ensure script loaded via app startup; TestClient startup should have loaded it
    yield r
    r.flushdb()

def test_health(client):
    r = client.get('/health')
    assert r.status_code == 200
    assert 'redis' in r.json()

def test_missing_customer_header(client):
    r = client.get('/api/resource')
    assert r.status_code == 400

def test_valid_admission_and_headers(client, raw_redis):
    headers = {'X-Customer-ID': 'alpha'}
    # ensure clean
    raw_redis.flushdb()
    r = client.get('/api/resource', headers=headers)
    assert r.status_code == 200
    assert r.headers.get('X-RateLimit-Limit') is not None
    assert r.headers.get('X-RateLimit-Remaining') is not None

def test_quota_exhaustion_and_retry_after(client, raw_redis):
    headers = {'X-Customer-ID': 'quota-test'}
    # set quota config dynamically by patching CUSTOMERS in app
    from solution.app import main
    main.CUSTOMERS['quota-test'] = 3
    raw_redis.flushdb()
    # consume quota
    for _ in range(3):
        r = client.get('/api/resource', headers=headers)
        assert r.status_code == 200
    # next should be 429
    r = client.get('/api/resource', headers=headers)
    assert r.status_code == 429
    assert 'Retry-After' in r.headers
    assert int(r.headers['X-RateLimit-Limit']) == 3
    assert r.headers['X-RateLimit-Remaining'] in ('0', '0')

def test_dependency_failure_returns_503(client):
    # Patch redis client's evalsha to raise
    from solution.app import main
    with patch.object(main.redis_client, 'evalsha', side_effect=redis.RedisError('conn')):
        headers = {'X-Customer-ID': 'alpha'}
        r = client.get('/api/resource', headers=headers)
        assert r.status_code == 503
        assert r.headers.get('X-Service-Dependency') == 'redis'
