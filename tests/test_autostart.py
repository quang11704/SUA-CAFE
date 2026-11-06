"""Codespaces process lifecycle checks, entirely outside the shop workspace."""
import concurrent.futures
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


@unittest.skipUnless(sys.platform.startswith('linux'), 'Codespaces supervisor uses Linux process locks')
class AutostartTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sua-boot-test-')
        self.root = Path(self.temp.name)
        original = Path(__file__).resolve().parents[1]
        (self.root / '.devcontainer').mkdir()
        for name in ['boot.py', 'supervise.py']:
            shutil.copy2(original / '.devcontainer' / name, self.root / '.devcontainer' / name)
        (self.root / '.venv/bin').mkdir(parents=True)
        (self.root / '.venv/bin/python').symlink_to(sys.executable)
        (self.root / 'requirements.txt').write_text('')
        (self.root / 'server.py').write_text('''import os,json
from http.server import BaseHTTPRequestHandler,HTTPServer
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  data={'status':'ok','schema':1} if self.path=='/api/health' else {'authenticated':False}
  raw=json.dumps(data).encode();self.send_response(200);self.end_headers();self.wfile.write(raw)
HTTPServer(('127.0.0.1',int(os.environ['PORT'])),Handler).serve_forever()
''')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            self.port = sock.getsockname()[1]
        self.env = dict(os.environ, PORT=str(self.port))

    def boot(self, *args, check=True):
        result = subprocess.run([sys.executable, str(self.root / '.devcontainer/boot.py'), *args], cwd=self.root,
                                env=self.env, text=True, capture_output=True, timeout=25)
        if check:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def status(self):
        return json.loads(self.boot('--status').stdout)

    def tearDown(self):
        self.boot('--stop')
        self.temp.cleanup()

    def test_start_and_attach_are_idempotent_and_child_recovers(self):
        self.boot()
        first = self.status()
        self.assertTrue(first['healthy'])
        self.boot()
        self.assertEqual(self.status()['supervisor']['pid'], first['supervisor']['pid'])
        old_child = first['supervisor']['child_pid']
        os.kill(old_child, signal.SIGTERM)
        for _ in range(40):
            current = self.status()
            if current['healthy'] and current['supervisor']['child_pid'] != old_child:
                break
            time.sleep(.2)
        else:
            self.fail('Supervisor did not restart its terminated application')

    def test_code_update_and_restart_replace_only_managed_process(self):
        self.boot()
        first = self.status()['supervisor']['pid']
        with (self.root / 'server.py').open('a') as source:
            source.write('\n# test source update\n')
        self.boot()
        second = self.status()['supervisor']['pid']
        self.assertNotEqual(first, second)
        self.boot('--restart')
        self.assertNotEqual(self.status()['supervisor']['pid'], second)
        self.assertTrue(self.status()['healthy'])

    def test_concurrent_start_attach_hooks_create_one_supervisor(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.boot(), range(2)))
        self.assertTrue(all(result.returncode == 0 for result in results))
        first = self.status()['supervisor']['pid']
        self.boot()
        self.assertEqual(self.status()['supervisor']['pid'], first)

    def test_busy_foreign_port_is_not_killed(self):
        foreign = subprocess.Popen([sys.executable, '-m', 'http.server', str(self.port), '--bind', '127.0.0.1'],
                                   cwd=self.root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(30):
                with socket.socket() as sock:
                    if sock.connect_ex(('127.0.0.1', self.port)) == 0:
                        break
                time.sleep(.1)
            result = self.boot(check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIsNone(foreign.poll())
            self.assertIsNone(self.status()['supervisor'])
        finally:
            foreign.terminate()
            foreign.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
