import tempfile
import unittest
from pathlib import Path

from pulsegrid.api import API
from pulsegrid.config import Settings
from pulsegrid.db import DB


class TestAPI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = DB(Path(self.tmp.name) / "test.db")
        self.settings = Settings(token="test-token", port=18080)
        self.api = API(self.db, self.settings)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_node_crud(self):
        n = self.api.create_node({"name": "n1", "host": "1.1.1.1", "port": 443})
        self.assertIn("id", n)
        self.assertEqual(len(self.api.list_nodes()), 1)
        self.assertTrue(self.api.delete_node(n["id"]))
        self.assertEqual(len(self.api.list_nodes()), 0)

    def test_user_crud_and_status(self):
        u = self.api.create_user({"name": "bob", "quota_gb": 10, "days": 30})
        self.assertEqual(u["name"], "bob")
        users = self.api.list_users()
        self.assertEqual(users[0]["status"], "active")
        self.assertTrue(self.api.delete_user(u["id"]))

    def test_presets_apply(self):
        r = self.api.apply_preset({"preset": "low_latency"})
        self.assertEqual(r["preset"], "low_latency")
        self.assertEqual(self.db.get_setting("active_preset"), "low_latency")

    def test_dashboard_shape(self):
        self.api.create_node({"name": "n", "host": "127.0.0.1"})
        d = self.api.dashboard()
        for k in ("nodes", "users", "traffic", "alerts", "summary"):
            self.assertIn(k, d)

    def test_subscription_unknown_user_raises(self):
        with self.assertRaises(KeyError):
            self.api.subscription("nope")

    def test_subscription_for_user(self):
        u = self.api.create_user({"name": "carol"})
        self.api.create_node({"name": "n", "host": "127.0.0.1", "port": 443})
        # No health recorded -> score 0 -> filtered by default min_score
        sub = self.api.subscription(u["id"], fmt="plain", min_score=0)
        self.assertEqual(len(sub["links"]), 1)

    def test_user_configs_explain_empty_and_return_healthy_links(self):
        user = self.api.create_user({"name": "test"})
        self.assertEqual(self.api.user_configs(user["id"])["reason"], "no_nodes")
        node = self.api.create_node({"name": "n", "host": "example.com"})
        self.assertEqual(self.api.user_configs(user["id"])["reason"], "unchecked")
        self.db.record_health(node["id"], 0, 0, 100, False, "failed")
        self.assertEqual(self.api.user_configs(user["id"])["reason"], "no_healthy_nodes")
        self.db.record_health(node["id"], 95, 10, 0, True, "ok")
        result = self.api.user_configs(user["id"])
        self.assertEqual(result["reason"], "ready")
        self.assertIn(user["uuid"], result["links"][0])
        self.db.update_user(user["id"], enabled=0)
        self.assertEqual(self.api.user_configs(user["id"])["reason"], "disabled")
        self.assertEqual(self.api.user_configs(user["id"])["links"], [])
        with self.assertRaises(KeyError):
            self.api.user_configs("unknown")

    def test_traffic_summary(self):
        self.db.add_usage("u1", up=100, down=200)
        t = self.api.traffic_summary()
        self.assertEqual(t["total_bytes"], 300)


if __name__ == "__main__":
    unittest.main()

class TLSHealthTests(unittest.TestCase):
    def test_unverified_tls_is_excluded(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            db = DB(Path(tmp) / 'test.db')
            api = API(db, Settings(token='test'))
            user = api.create_user({'name': 'alice'})
            node = api.create_node({'name': 'n', 'host': 'example.com', 'port': 443, 'security': 'tls'})
            result = {'score': 85, 'latency_ms': 5, 'loss_pct': 0, 'reachable': True,
                      'summary': 'TLS failed', 'tls_ok': False}
            with patch('pulsegrid.api.run_diagnostics', return_value=result):
                api.check_all_nodes()
            self.assertEqual(db.latest_health(node['id'])['score'], 0)
            self.assertEqual(api.subscription(user['id'], fmt='plain')['links'], [])
            db.close()
