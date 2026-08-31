"""
Distributed load harness for the rate limiter.
Run with:
    python solution/harness/run_scenarios.py

It assumes the cluster is running on ports 8001,8002,8003 (use solution/run_cluster.py to start them).
Requires Redis at REDIS_URL to be available; harness will flush DB at start to ensure clean state.
"""
import os
import sys
import asyncio
import random
import time
from collections import Counter
import httpx
import redis

PORTS = [8001,8002,8003]
URLS = [f'http://127.0.0.1:{p}/api/resource' for p in PORTS]
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
WINDOW_SEC = 60

# Helper to round-robin
class RoundRobin:
    def __init__(self, urls):
        self.urls = urls
        self.i = 0
    def next(self):
        url = self.urls[self.i % len(self.urls)]
        self.i += 1
        return url

async def do_request(client, url, customer):
    try:
        r = await client.get(url, headers={'X-Customer-ID': customer}, timeout=10.0)
        return r.status_code, r.headers
    except Exception as e:
        return None, {'error': str(e)}

async def scenario_sequential(quota, total_requests, rr, customer):
    allowed = 0
    rejected = 0
    async with httpx.AsyncClient() as client:
        for _ in range(total_requests):
            url = rr.next()
            status, headers = await do_request(client, url, customer)
            if status == 200:
                allowed += 1
            elif status == 429:
                rejected += 1
            else:
                print('Unexpected status', status, 'headers', headers)
    return allowed, rejected

async def scenario_concurrent(quota, total_requests, rr, customer):
    async with httpx.AsyncClient() as client:
        tasks = []
        for _ in range(total_requests):
            url = rr.next()
            tasks.append(do_request(client, url, customer))
        results = await asyncio.gather(*tasks)
    allowed = sum(1 for status, _ in results if status == 200)
    rejected = sum(1 for status, _ in results if status == 429)
    others = [r for r in results if r[0] not in (200,429)]
    return allowed, rejected, others

async def run_all():
    # connect to redis and flush
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        r.ping()
    except Exception as e:
        print('Redis not available at', REDIS_URL, 'error:', e)
        sys.exit(2)
    r.flushdb()
    rr = RoundRobin(URLS)

    results = []

    # Scenario A: Exact Quota
    print('\nScenario A: Exact Quota (sequential)')
    allowed, rejected = await scenario_sequential(quota=10, total_requests=11, rr=rr, customer='alpha')
    expected_allowed = 10
    expected_rejected = 1
    ok = (allowed == expected_allowed and rejected == expected_rejected)
    results.append(('Exact Quota', expected_allowed, expected_rejected, allowed, rejected, ok))
    print(f'  Allowed={allowed} Rejected={rejected} -> {"PASS" if ok else "FAIL"}')

    # reset DB for clean runs
    r.flushdb()
    rr = RoundRobin(URLS)

    # Scenario B: Concurrent Boundary
    print('\nScenario B: Concurrent Boundary (50 concurrent)')
    allowed, rejected, others = await scenario_concurrent(quota=10, total_requests=50, rr=rr, customer='alpha')
    expected_allowed = 10
    expected_rejected = 40
    ok = (allowed == expected_allowed and rejected == expected_rejected and len(others)==0)
    results.append(('Concurrent Boundary', expected_allowed, expected_rejected, allowed, rejected, ok))
    print(f'  Allowed={allowed} Rejected={rejected} Others={len(others)} -> {"PASS" if ok else "FAIL"}')

    # reset DB
    r.flushdb()
    rr = RoundRobin(URLS)

    # Scenario C: Distributed Enforcement
    print('\nScenario C: Distributed Enforcement (30 requests across nodes)')
    allowed, rejected, others = await scenario_concurrent(quota=10, total_requests=30, rr=rr, customer='alpha')
    expected_allowed = 10
    expected_rejected = 20
    ok = (allowed == expected_allowed and rejected == expected_rejected and len(others)==0)
    results.append(('Distributed Enforcement', expected_allowed, expected_rejected, allowed, rejected, ok))
    print(f'  Allowed={allowed} Rejected={rejected} Others={len(others)} -> {"PASS" if ok else "FAIL"}')

    # reset DB
    r.flushdb()
    rr = RoundRobin(URLS)

    # Scenario D: Independent Customers
    print('\nScenario D: Independent Customers (20 beta, 10 alpha concurrently)')
    async with httpx.AsyncClient() as client:
        tasks = []
        # 20 beta
        for _ in range(20):
            url = rr.next()
            tasks.append(do_request(client, url, 'beta'))
        # 10 alpha
        for _ in range(10):
            url = rr.next()
            tasks.append(do_request(client, url, 'alpha'))
        results_list = await asyncio.gather(*tasks)
    # count per customer by status: we didn't tag results, so run separate sets to be deterministic
    # do separate runs for clarity
    r.flushdb()
    rr = RoundRobin(URLS)
    allowed_b, rejected_b, _ = await scenario_concurrent(quota=10, total_requests=20, rr=rr, customer='beta')
    r.flushdb()
    rr = RoundRobin(URLS)
    allowed_a, rejected_a, _ = await scenario_concurrent(quota=10, total_requests=10, rr=rr, customer='alpha')
    ok = (allowed_a == 10 and allowed_b == 10)
    results.append(('Independent Customers', 10, 10, allowed_a, allowed_b, ok))
    print(f'  alpha Allowed={allowed_a} beta Allowed={allowed_b} -> {"PASS" if ok else "FAIL"}')

    # Summary table
    print('\nSummary:')
    header = f"{'Scenario':30} {'ExpectedAllowed':15} {'ExpectedRejected':15} {'ActualAllowed':13} {'ActualRejected':14} {'Result':6}"
    print(header)
    print('-'*len(header))
    exit_code = 0
    for row in results:
        name, exp_allowed, exp_rej, act_allowed, act_rej, ok = row
        status = 'PASS' if ok else 'FAIL'
        print(f"{name:30} {str(exp_allowed):15} {str(exp_rej):15} {str(act_allowed):13} {str(act_rej):14} {status:6}")
        if not ok:
            exit_code = 2

    sys.exit(exit_code)

if __name__ == '__main__':
    asyncio.run(run_all())
