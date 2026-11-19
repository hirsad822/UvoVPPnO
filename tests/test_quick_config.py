import http.client
import json
import os
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from pulsegrid.config import Settings
from pulsegrid.core import CoreSupervisor
from pulsegrid.server import App, make_handler

# Test double only: this exercises supervisor lifecycle and TLS readiness, not VLESS.
FAKE_XRAY = '''#!/usr/bin/env python3
import json, socket, ssl, sys
if '-test' in sys.argv:
    sys.exit(0)
config = json.load(open(sys.argv[sys.argv.index('-config')+1]))
inbound = config['inbounds'][0]
cert = inbound['streamSettings']['tlsSettings']['certificates'][0]
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(cert['certificateFile'], cert['keyFile'])
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('127.0.0.1', inbound['port']))
s.listen(20)
while True:
    client, addr = s.accept()
    try:
        with context.wrap_socket(client, server_side=True):
            pass
    except (OSError, ssl.SSLError):
        client.close()
'''


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class QuickConfigTests(unittest.TestCase):
    def test_create_with_real_tls_and_fake_supervised_core(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            certdir = root / 'config' / 'tls-current'
            certdir.mkdir(parents=True)
            cert, key = certdir / 'fullchain.pem', certdir / 'privkey.pem'
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                            '-keyout', str(key), '-out', str(cert), '-days', '1',
                            '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost'],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            fake = root / 'xray'
            fake.write_text(FAKE_XRAY)
            fake.chmod(0o755)
            settings = Settings(data_dir=root / 'data', config_dir=root / 'config', db_path=root / 'data/db', token='test')
            with patch.dict(os.environ, {'PULSEGRID_XRAY_BIN': str(fake), 'PULSEGRID_PUBLIC_HOST': 'localhost',
                                         'PULSEGRID_CORE_PORT': str(free_port()), 'SSL_CERT_FILE': str(cert)}):
                app = App(settings)
                core = CoreSupervisor(settings)
                app.core = core
                app.api.managed_only = True
                core.start()
                server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(app))
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    self.assertTrue(core.wait_ready(timeout=8))
                    conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=30)
                    payload = json.dumps({'name': 'alice'})
                    conn.request('POST', '/api/configs/quick', payload, {'Content-Type': 'application/json'})
                    res = conn.getresponse()
                    self.assertEqual(res.status, 401)
                    res.read()
                    conn.request('POST', '/api/configs/quick', payload,
                                 {'Content-Type': 'application/json', 'Authorization': 'Bearer test'})
                    res = conn.getresponse()
                    data = json.loads(res.read())
                    self.assertEqual(res.status, 201, data)
                    self.assertIn('vless://' + data['user_uuid'] + '@localhost:', data['link'])
                    self.assertIn('security=tls', data['link'])
                    self.assertEqual(res.getheader('Cache-Control'), 'no-store')
                    config = json.loads((settings.data_dir / 'xray.json').read_text())
                    self.assertIn(data['user_uuid'], [x['id'] for x in config['inbounds'][0]['settings']['clients']])
                    conn.request('GET', '/api/subscription/' + data['user_uuid'] + '?format=plain')
                    res = conn.getresponse()
                    self.assertEqual(res.status, 200)
                    self.assertEqual(res.read().decode(), data['link'])
                    conn.close()
                finally:
                    server.shutdown()
                    thread.join()
                    server.server_close()
                    core.stop()
                    app.db.close()

    def test_core_unavailable_does_not_create_user(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = App(Settings(data_dir=root, config_dir=root, db_path=root / 'db', token='test'))
            server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(app))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                conn = http.client.HTTPConnection('127.0.0.1', server.server_port)
                conn.request('POST', '/api/configs/quick', json.dumps({'name': 'bob'}),
                             {'Content-Type': 'application/json', 'Authorization': 'Bearer test'})
                res = conn.getresponse()
                self.assertEqual(res.status, 503)
                res.read()
                self.assertEqual(app.db.list_users(), [])
                conn.close()
            finally:
                server.shutdown()
                thread.join()
                server.server_close()
                app.db.close()


if __name__ == '__main__':
    unittest.main()
