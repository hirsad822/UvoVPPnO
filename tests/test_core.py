import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from pulsegrid.config import Settings
from pulsegrid.core import CoreSupervisor, xray_config
from pulsegrid.db import DB
from pulsegrid.tls import validate_certificate


class CoreTests(unittest.TestCase):
    def test_config_filters_inactive_users_and_requires_tls(self):
        users = [dict(id='a', uuid='a-uuid', enabled=1, expires_at=0, quota_bytes=0, used_bytes=0),
                 dict(id='b', uuid='b-uuid', enabled=0, expires_at=0, quota_bytes=0, used_bytes=0),
                 dict(id='c', uuid='c-uuid', enabled=1, expires_at=time.time()-1, quota_bytes=0, used_bytes=0)]
        cfg = xray_config(users, 10000, '/cert', '/key')
        inbound = cfg['inbounds'][0]
        self.assertEqual(inbound['settings']['clients'], [{'id': 'a-uuid', 'email': 'a'}])
        self.assertEqual(inbound['streamSettings']['security'], 'tls')
        self.assertEqual(inbound['streamSettings']['tlsSettings']['certificates'][0],
                         {'certificateFile': '/cert', 'keyFile': '/key'})

    def test_reconcile_migrates_node_and_restarts_for_certificate_change(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict('os.environ', {'PULSEGRID_PUBLIC_HOST': 'example.com', 'PULSEGRID_CORE_PORT': '12345'}):
            db = DB(Path(tmp) / 'db')
            old = db.create_node('Local Xray', 'old.example.com', 12345, security='none')
            db.set_setting('managed_core_node', old['id'])
            db.record_health(old['id'], 100, 1, 0, True, 'old')
            core = CoreSupervisor(Settings(data_dir=Path(tmp), config_dir=Path(tmp)))
            with patch('pulsegrid.core.validate_certificate', return_value='digest1') as cert, patch('pulsegrid.core.subprocess.run') as validate, patch('pulsegrid.core.subprocess.Popen') as popen:
                popen.return_value.poll.return_value = None
                core.reconcile(db)
                node = db.get_node(old['id'])
                self.assertEqual(node['host'], 'example.com')
                self.assertEqual(node['security'], 'tls')
                self.assertEqual(db.latest_health(old['id'])['score'], 0)
                core.reconcile(db)
                self.assertEqual(popen.call_count, 1)
                cert.return_value = 'digest2'
                core.reconcile(db)
                self.assertEqual(popen.call_count, 2)
                db.create_user('alice')
                core.reconcile(db)
                self.assertEqual(popen.call_count, 3)
                self.assertEqual(validate.call_count, 3)
            db.close()

    def test_invalid_certificate_stops_and_disables_node(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict('os.environ', {'PULSEGRID_PUBLIC_HOST': 'example.com'}):
            db = DB(Path(tmp) / 'db')
            node = db.create_node('managed', 'example.com', 10000, security='tls')
            db.set_setting('managed_core_node', node['id'])
            core = CoreSupervisor(Settings(data_dir=Path(tmp), config_dir=Path(tmp)))
            with patch('pulsegrid.core.validate_certificate', side_effect=ValueError('bad cert')):
                with self.assertRaises(ValueError):
                    core.reconcile(db)
            self.assertFalse(db.get_node(node['id'])['enabled'])
            db.close()

    def test_certificate_validation_with_real_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            cert, key = Path(tmp) / 'cert.pem', Path(tmp) / 'key.pem'
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                            '-keyout', str(key), '-out', str(cert), '-days', '1',
                            '-subj', '/CN=example.com', '-addext', 'subjectAltName=DNS:example.com'],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.assertEqual(len(validate_certificate('example.com', cert, key)), 64)
            with self.assertRaises(ValueError):
                validate_certificate('wrong.example.com', cert, key)
            with self.assertRaises(OSError):
                validate_certificate('example.com', cert, Path(tmp) / 'missing')

    def test_certificate_validation_with_ip_san(self):
        with tempfile.TemporaryDirectory() as tmp:
            cert, key = Path(tmp) / 'cert.pem', Path(tmp) / 'key.pem'
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                            '-keyout', str(key), '-out', str(cert), '-days', '1',
                            '-subj', '/CN=test', '-addext', 'subjectAltName=IP:8.8.8.8'],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.assertEqual(len(validate_certificate('8.8.8.8', cert, key)), 64)
            with self.assertRaises(ValueError):
                validate_certificate('8.8.4.4', cert, key)

if __name__ == '__main__':
    unittest.main()
