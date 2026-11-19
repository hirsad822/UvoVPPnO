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

    def test_traffic_summary(self):
        self.db.add_usage("u1", up=100, down=200)
        t = self.api.traffic_summary()
        self.assertEqual(t["total_bytes"], 300)


if __name__ == "__main__":
    unittest.main()
