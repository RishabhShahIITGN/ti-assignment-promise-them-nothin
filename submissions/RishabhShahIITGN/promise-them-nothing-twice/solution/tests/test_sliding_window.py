import os
import time
import uuid
import pytest
import redis

ROOT = os.path.dirname(os.path.dirname(__file__))
LUA_PATH = os.path.join(ROOT, 'limiter', 'redis_scripts', 'sliding_window.lua')

REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

@pytest.fixture(scope='module')
def r():
    client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    # Ensure Redis is reachable
    try:
        client.ping()
    except Exception as e:
        pytest.skip(f"Redis not available at {REDIS_URL}: {e}")
    # Load script
    with open(LUA_PATH, 'r') as f:
        script_src = f.read()
    script = client.register_script(script_src)
    client._rl_script = script
    yield client
    # cleanup
    client.flushdb()

@pytest.fixture(autouse=True)
def flushdb(r):
    r.flushdb()
    yield
    r.flushdb()

def call_rl(r, key, quota, window_ms, member=None):
    if member is None:
        member = f"{uuid.uuid4()}"
    script = r._rl_script
    # Note: redis-py Script __call__ accepts keys and args
    res = script(keys=[key], args=[str(quota), str(window_ms), member])
    # res = [allowed, remaining, limit, retry_after]
    # Convert to integers where appropriate
    allowed = int(res[0])
    remaining = int(res[1])
    limit = int(res[2])
    retry_after = int(res[3])
    return allowed, remaining, limit, retry_after

# Test 1: Exact quota (off-by-one check)
def test_exact_quota(r):
    key = 'rl:test_exact'
    quota = 10
    window_ms = 1000  # 1 second window for fast tests
    # Send exactly quota requests
    for i in range(quota):
        allowed, remaining, limit, retry = call_rl(r, key, quota, window_ms, member=f'm{i}')
        assert allowed == 1
        assert limit == quota
    # The next request should be rejected
    allowed, remaining, limit, retry = call_rl(r, key, quota, window_ms, member='m_over')
    assert allowed == 0
    assert remaining == 0
    assert retry >= 0

# Test 2: One beyond quota across time (inclusive/exclusive boundary)
def test_one_beyond_across_time(r):
    key = 'rl:test_boundary'
    quota = 3
    window_ms = 200  # small window, ms precision
    # consume quota
    for i in range(quota):
        allowed, remaining, limit, retry = call_rl(r, key, quota, window_ms, member=f'b{i}')
        assert allowed == 1
    # immediate extra should be rejected
    allowed, remaining, limit, retry = call_rl(r, key, quota, window_ms, member='b_over')
    assert allowed == 0
    # wait for just over window_ms so earliest entries age out
    time.sleep((window_ms / 1000.0) + 0.05)
    # now request should be allowed
    allowed, remaining, limit, retry = call_rl(r, key, quota, window_ms, member='b_after')
    assert allowed == 1

# Test 6: Refill / recovery
def test_refill_recovery(r):
    key = 'rl:test_refill'
    quota = 4
    window_ms = 300
    for i in range(quota):
        allowed, remaining, limit, retry = call_rl(r, key, quota, window_ms, member=f'r{i}')
        assert allowed == 1
    # rejected now
    allowed, remaining, limit, retry = call_rl(r, key, quota, window_ms, member='r_over')
    assert allowed == 0
    # wait for window to pass
    time.sleep((window_ms / 1000.0) + 0.05)
    # should be allowed again
    allowed, remaining, limit, retry = call_rl(r, key, quota, window_ms, member='r_after')
    assert allowed == 1

# Test 7: Boundary timing micro-test (ms precision)
def test_boundary_timing_precision(r):
    key = 'rl:test_timing'
    quota = 1
    window_ms = 200
    # first request at t0
    allowed, remaining, limit, retry = call_rl(r, key, quota, window_ms, member='t0')
    assert allowed == 1
    # immediate second -> rejected
    allowed, remaining, limit, retry = call_rl(r, key, quota, window_ms, member='t_immediate')
    assert allowed == 0
    # wait exactly window_ms + small epsilon
    time.sleep((window_ms / 1000.0) + 0.05)
    # now should be allowed
    allowed, remaining, limit, retry = call_rl(r, key, quota, window_ms, member='t_after')
    assert allowed == 1
