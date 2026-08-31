DECISIONS — RelayAPI rate limiter

Stakeholder conflict
- CTO requires strict, auditable enforcement: customers must not exceed contracted RPM.
- Support requests Northwind see no 429 during nightly batch (02:00–04:00 UTC).

Decision
- We prioritize the CTO: enforce a strict sliding-window limit that guarantees no more than N requests in any 60s interval.
- Northwind receives no hidden runtime bypass. If business grants an exception, it must be an explicit, auditable config change to the customer's quota (recorded in billing/config systems).

Algorithm
- Sliding-window log per customer implemented with Redis Sorted Sets.
- Each request inserts a timestamped member; Redis `ZREMRANGEBYSCORE` cleans older than 60s; admission is `ZCARD < quota`.
- Atomicity achieved with a Redis Lua script that uses `redis.call('TIME')` for server-side timestamps.

Distributed coordination
- Authoritative state lives in Redis. All app nodes call the Lua script; no per-process authoritative memory.
- Atomic Lua script avoids read-modify-write races and ensures global correctness across three app instances.

Harness proof & limits
- The harness demonstrates:
  - exact-quota enforcement (no off-by-one acceptance),
  - atomicity under concurrency (no more than N admitted across concurrent requests),
  - shared enforcement across three app nodes (no per-process duplication).
- The harness does NOT prove:
  - Redis failover or network partitions; it assumes a single authoritative Redis instance.
  - Geographically distributed clocks or multiple Redis masters.

Next four hours
1. Add integration test to simulate Redis latency and verify Retry-After accuracy.
2. Replace sorted-set log with a memory-efficient leaky-bucket approximation and add benchmarking.
3. Add audit export logs per customer (append-only) and wire simple CLI to inspect counts for a time window.
4. Add optional operational mode to grant temporary per-customer quota overrides via a config file with change audit.

"""
