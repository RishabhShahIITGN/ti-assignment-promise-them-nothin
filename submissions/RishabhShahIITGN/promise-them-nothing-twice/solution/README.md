Solution core limiter tests

Prerequisites:
- Python 3.9+
- Redis running on localhost:6379

Quick start:

Create a venv and install deps:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r solution/requirements.txt
```

Run tests:

```bash
pytest -q solution/tests/test_sliding_window.py
```

Notes:
- Tests use small windows (ms) to remain fast and deterministic. They rely on Redis server TIME for timestamping.
- If Redis is not available, pytest will skip the tests.

Full reviewer guide
===================

This README explains how to run the project end-to-end: unit tests, API tests, and the distributed load harness that demonstrates global rate-limit enforcement across three app instances.

Prerequisites
-------------
- Python 3.9+ (3.10 or 3.11 recommended)
- Redis running locally and reachable at `localhost:6379` (default port)

Setup
-----
1. From the repository root, create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate
```

2. Install dependencies:

```powershell
pip install -r solution/requirements.txt
```

Running the unit & API tests
----------------------------
Run the Lua/core tests and API tests (requires Redis):

```powershell
# run the Lua core boundary tests
pytest -q solution/tests/test_sliding_window.py::test_exact_quota solution/tests/test_sliding_window.py::test_one_beyond_across_time solution/tests/test_sliding_window.py::test_refill_recovery solution/tests/test_sliding_window.py::test_boundary_timing_precision

# run the API tests
pytest -q solution/tests/test_api.py
```

Or run all tests together:

```powershell
pytest -q solution/tests
```

Running the distributed cluster and the harness
---------------------------------------------
We simulate three stateless app nodes locally. The cluster runner starts three Uvicorn processes bound to ports `8001`, `8002`, and `8003`.

1. Start the cluster in a terminal (this blocks; leave it running):

```powershell
python solution/run_cluster.py
```

You should see three uvicorn instances start. Give them a second to warm up.

2. In a separate terminal (same venv), run the harness which executes the scenarios and prints a short summary table:

```powershell
python solution/harness/run_scenarios.py
```

The harness will:
- Flush Redis at start for deterministic runs
- Run Scenario A (Exact Quota), Scenario B (Concurrent Boundary), Scenario C (Distributed Enforcement), and Scenario D (Independent Customers)
- Print per-scenario results and a summary table and exit with a non-zero code on failure

3. Stop the cluster:

- If you started `solution/run_cluster.py` in a terminal, press `Ctrl+C` to stop the processes cleanly.
- If started with `Start-Process`, terminate the processes with Task Manager or:

```powershell
# replace <PID> with the actual PIDs printed by the runner
Stop-Process -Id <PID>
```

Project structure overview
--------------------------
- `solution/app/` — FastAPI application and configuration loader
	- `main.py` — HTTP app with `GET /health` and `GET /api/resource` endpoints
	- `config/customers.json` — per-customer quota config (including `northwind: 300`)
- `solution/limiter/redis_scripts/` — Redis Lua scripts
	- `sliding_window.lua` — atomic sliding-window script that uses `redis.call('TIME')`
- `solution/tests/` — tests
	- `test_sliding_window.py` — isolated Lua/script tests for boundary correctness
	- `test_api.py` — API integration tests using FastAPI TestClient
- `solution/harness/` — load-testing harness
	- `run_scenarios.py` — async harness that round-robins requests across three nodes and prints PASS/FAIL
- `solution/run_cluster.py` — local cluster runner launching three uvicorn workers for `solution.app.main:app`
- `solution/DECISIONS.md` — one-page decisions and conflict resolution summary

Notes and limitations
---------------------
- This prototype uses a single Redis instance as authoritative state. It demonstrates correct multi-node enforcement and atomicity but does not implement Redis cluster failover or multi-master replication. Those are out-of-scope for this exercise.
- The limiter implements strict sliding-window semantics (no more than N requests in any 60s interval). This choice was made to satisfy the explicit CTO requirement for auditable, never-exceed behavior. Operational exceptions must be applied by changing the customer's configured quota in `solution/app/config/customers.json` and are auditable.

If something fails
------------------
- Confirm Redis is running at `localhost:6379`.
- Ensure your venv is activated and dependencies are installed.
- Check logs in the terminal running `solution/run_cluster.py` for uvicorn errors.

Contact
-------
If you want me to run the harness automatically and collect the output, tell me and I will prepare an orchestration script that starts the cluster, waits for readiness, runs the harness, and tears down the cluster.
