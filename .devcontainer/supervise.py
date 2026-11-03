"""Keep this workspace's SỨA process alive; never change application data."""
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

root, state, revision = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
state.mkdir(parents=True, exist_ok=True)
lock = (state / 'supervisor.lock').open('a')
try:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    raise SystemExit(0)
stop = False
child = None


def shutdown(signum, frame):
    global stop
    stop = True
    if child and child.poll() is None:
        child.terminate()


def record():
    target = state / 'status.json'
    temp = state / 'status.tmp'
    temp.write_text(json.dumps(dict(pid=os.getpid(), child_pid=child.pid if child else None,
                                    revision=revision, root=str(root))), encoding='utf-8')
    temp.replace(target)


signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)
environment = dict(os.environ, HOST='127.0.0.1')
if environment.get('CODESPACES') == 'true':
    environment['SUA_SECURE_COOKIE'] = '1'
backoff = 1
try:
    while not stop:
        started = time.monotonic()
        child = subprocess.Popen([str(root / '.venv/bin/python'), str(root / 'server.py')], cwd=root, env=environment)
        record()
        while child.poll() is None:
            if stop:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
                break
            time.sleep(.2)
        if stop:
            break
        if time.monotonic() - started > 30:
            backoff = 1
        print(f'SỨA stopped ({child.returncode}); restarting in {backoff}s.', flush=True)
        deadline = time.monotonic() + backoff
        while not stop and time.monotonic() < deadline:
            time.sleep(.2)
        backoff = min(backoff * 2, 30)
finally:
    if child and child.poll() is None:
        child.terminate()
        child.wait(timeout=5)
    (state / 'status.json').unlink(missing_ok=True)
