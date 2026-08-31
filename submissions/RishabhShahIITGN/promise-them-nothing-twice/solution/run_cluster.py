"""
Run 3 local FastAPI instances (uvicorn) for testing distributed behavior.
Starts uvicorn processes for `solution.app.main:app` on ports 8001,8002,8003.

Usage:
    python solution/run_cluster.py

Press Ctrl+C to stop all instances.
"""
import os
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(__file__))
PYTHONPATH = os.path.abspath(os.path.dirname(ROOT))

PORTS = [8001, 8002, 8003]
PROCS = []

def start():
    print('Starting 3 app instances...')
    for p in PORTS:
        cmd = [sys.executable, '-m', 'uvicorn', 'solution.app.main:app', '--host', '127.0.0.1', '--port', str(p), '--log-level', 'warning']
        env = os.environ.copy()
        # ensure repo root on PYTHONPATH so module path resolves
        env['PYTHONPATH'] = PYTHONPATH + (os.pathsep + env.get('PYTHONPATH',''))
        print('Starting:', ' '.join(cmd))
        proc = subprocess.Popen(cmd, env=env)
        PROCS.append(proc)
        time.sleep(0.2)
    print('Started processes:', [p.pid for p in PROCS])
    print('Give apps a second to warm up...')
    time.sleep(1.0)

def stop():
    print('Stopping processes...')
    for proc in PROCS:
        try:
            proc.terminate()
        except Exception:
            pass
    for proc in PROCS:
        try:
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    print('Stopped.')

if __name__ == '__main__':
    try:
        start()
        print('Cluster running. Press Ctrl+C to stop.')
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop()
        sys.exit(0)
