import http.client
import json
import ssl
import subprocess
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from pulsegrid.config import Settings
from pulsegrid.server import App, make_handler


class HTTPSTests(unittest.TestCase):
    def test_https_and_private_subscription_identifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cert, key = root / 'cert.pem', root / 'key.pem'
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                            '-keyout', str(key), '-out', str(cert), '-days', '1',
                            '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost'],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            settings = Settings(data_dir=root, config_dir=root, db_path=root / 'db', token='test')
            app = App(settings)
            user = app.api.create_user({'name': 'test'})
            server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(app))
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(str(cert), str(key))
            server.socket = context.wrap_socket(server.socket, server_side=True)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                conn = http.client.HTTPSConnection('localhost', server.server_port,
                                                  context=ssl.create_default_context(cafile=str(cert)))
                conn.request('GET', '/api/health')
                self.assertEqual(conn.getresponse().status, 200)
                conn.request('GET', '/api/dashboard')
                response = conn.getresponse()
                self.assertEqual(response.status, 401)
                response.read()
                conn.request('GET', '/api/dashboard', headers={'Authorization': 'Bearer test'})
                response = conn.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())['summary']['total_users'], 1)
                conn.request('GET', '/api/subscription/' + user['id'])
                response = conn.getresponse()
                self.assertEqual(response.status, 404)
                response.read()
                conn.request('GET', '/api/subscription/' + user['uuid'])
                response = conn.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.getheader('Cache-Control'), 'no-store')
                response.read()
                conn.close()
            finally:
                server.shutdown()
                thread.join()
                server.server_close()
                app.db.close()

if __name__ == '__main__':
    unittest.main()
