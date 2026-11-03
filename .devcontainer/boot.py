"""Idempotent Codespaces bootstrap; serializes concurrent start/attach hooks."""
import argparse
import fcntl
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = int(os.environ.get('PORT', '8000'))
KEY = hashlib.sha256((str(ROOT) + ':' + str(PORT)).encode()).hexdigest()[:16]
STATE = Path(tempfile.gettempdir()) / f'sua-cafe-{os.getuid()}-{KEY}'
STATE.mkdir(mode=0o700, parents=True, exist_ok=True)


def status():
    try:
        value = json.loads((STATE / 'status.json').read_text())
        pid = int(value['pid'])
        proc = Path('/proc') / str(pid)
        argv = [os.fsdecode(x) for x in (proc / 'cmdline').read_bytes().split(b'\0') if x]
        if len(argv) != 5 or Path(argv[1]).resolve() != ROOT / '.devcontainer/supervise.py' or Path(argv[2]).resolve() != ROOT:
            return None
        if Path(os.readlink(proc / 'cwd')).resolve() != ROOT:
            return None
        return value
    except (OSError, ValueError, KeyError, TypeError):
        return None


def healthy():
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/api/health', timeout=1) as response:
            payload = json.load(response)
        if payload.get('status') != 'ok' or payload.get('schema') != 1:
            return False
        with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/api/session', timeout=1) as response:
            return isinstance(json.load(response).get('authenticated'), bool)
    except Exception:
        return False


def stop_managed():
    current = status()
    if not current:
        return
    os.kill(current['pid'], signal.SIGTERM)
    for _ in range(70):
        if not status():
            return
        time.sleep(.1)
    raise RuntimeError('Server chưa dừng; không khởi chạy thêm tiến trình. Hãy kiểm tra nhật ký.')


def revision():
    sources = sorted(ROOT.glob('*.py')) + sorted((ROOT / '.devcontainer').glob('*.py')) + [ROOT / 'requirements.txt']
    digest = hashlib.sha256()
    for file in sources:
        digest.update(file.name.encode())
        digest.update(file.read_bytes())
    return digest.hexdigest()


def prepare():
    executable = ROOT / '.venv/bin/python'
    requirements = ROOT / 'requirements.txt'
    # Detect missing/changed packages without fetching the registry on every attach.
    probe = """import importlib.metadata as m,sys
for line in open(sys.argv[1]):
 line=line.strip()
 if not line or line.startswith('#'):continue
 name,version=line.split('==')
 assert m.version(name)==version
"""
    ready = executable.is_file() and subprocess.run([str(executable), '-c', probe, str(requirements)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    if not ready:
        subprocess.run(['bash', str(ROOT / 'install.sh')], cwd=ROOT, check=True)


def retire_legacy():
    candidates = []
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            argv = [os.fsdecode(x) for x in (proc / 'cmdline').read_bytes().split(b'\0') if x]
            if len(argv) == 2 and Path(argv[1]).name == 'server.py' and Path(argv[0]).name.startswith('python') and Path(os.readlink(proc / 'cwd')).resolve() == ROOT:
                candidates.append(int(proc.name))
        except OSError:
            continue
    if len(candidates) > 1:
        raise RuntimeError('Có nhiều server trong cùng thư mục. Chưa dừng tiến trình nào.')
    for pid in candidates:
        os.kill(pid, signal.SIGTERM)
        for _ in range(50):
            try:
                if (Path('/proc') / str(pid) / 'stat').read_text().split()[2] == 'Z':
                    break
            except OSError:
                break
            time.sleep(.1)
        else:
            raise RuntimeError('Server cũ chưa dừng; không khởi chạy thêm tiến trình.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--restart', action='store_true')
    parser.add_argument('--stop', action='store_true')
    parser.add_argument('--status', action='store_true')
    args = parser.parse_args()
    if args.status:
        print(json.dumps(dict(supervisor=status(), healthy=healthy())))
        return
    with (STATE / 'boot.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.stop:
            stop_managed()
            return
        prepare()
        code = revision()
        current = status()
        if current and (args.restart or current['revision'] != code):
            stop_managed()
            current = None
        if not current:
            retire_legacy()
            with socket.socket() as probe:
                if probe.connect_ex(('127.0.0.1', PORT)) == 0:
                    raise RuntimeError(f'Cổng {PORT} đang được chương trình khác dùng. Chưa dừng chương trình đó.')
            with (STATE / 'server.log').open('ab') as log:
                subprocess.Popen([sys.executable, str(ROOT / '.devcontainer/supervise.py'), str(ROOT), str(STATE), code], cwd=ROOT,
                                 env=dict(os.environ, PORT=str(PORT)), stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        for _ in range(60):
            if status() and healthy():
                print(f'SỨA đã sẵn sàng. Mở Ports → {PORT} → Open in Browser. Giữ cổng Private.')
                return
            time.sleep(.2)
        raise RuntimeError('Chưa khởi động được SỨA. Xem nhật ký: ' + str(STATE / 'server.log'))


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
