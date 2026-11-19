import base64
import json
import time
import unittest

from pulsegrid.subscription import build_subscription


def _user(**kw):
    u = {"name": "alice", "uuid": "uuid-123", "quota_bytes": 0, "used_bytes": 0,
         "expires_at": 0, "enabled": 1}
    u.update(kw)
    return u


def _nodes():
    return [
        {"id": "n1", "name": "Good", "host": "1.1.1.1", "port": 443, "protocol": "vless",
         "transport": "tcp", "security": "tls", "uuid": "", "enabled": 1},
        {"id": "n2", "name": "Bad", "host": "2.2.2.2", "port": 443, "protocol": "vless",
         "transport": "tcp", "security": "tls", "uuid": "", "enabled": 1},
        {"id": "n3", "name": "Disabled", "host": "3.3.3.3", "port": 443, "protocol": "vless",
         "transport": "tcp", "security": "tls", "uuid": "", "enabled": 0},
    ]


def _health():
    return {"n1": {"score": 95, "latency_ms": 20, "loss_pct": 0},
            "n2": {"score": 10, "latency_ms": 900, "loss_pct": 30},
            "n3": {"score": 99, "latency_ms": 5, "loss_pct": 0}}


class TestSubscription(unittest.TestCase):
    def test_filters_unhealthy_and_disabled(self):
        sub = build_subscription(_user(), _nodes(), _health(), fmt="plain", min_score=50)
        self.assertEqual(len(sub["links"]), 1)
        self.assertIn("1.1.1.1", sub["links"][0])

    def test_base64_roundtrip(self):
        sub = build_subscription(_user(), _nodes(), _health(), fmt="base64", min_score=50)
        decoded = base64.b64decode(sub["payload"]).decode()
        self.assertIn("vless://", decoded)

    def test_json_format(self):
        sub = build_subscription(_user(), _nodes(), _health(), fmt="json", min_score=50)
        data = json.loads(sub["payload"])
        self.assertEqual(len(data["nodes"]), 1)
        self.assertEqual(data["nodes"][0]["health_score"], 95)

    def test_expired_user_gets_empty(self):
        u = _user(expires_at=time.time() - 100)
        sub = build_subscription(u, _nodes(), _health(), fmt="plain")
        self.assertEqual(sub["links"], [])
        self.assertEqual(sub["meta"]["status"], "expired")

    def test_quota_exceeded_gets_empty(self):
        u = _user(quota_bytes=100, used_bytes=200)
        sub = build_subscription(u, _nodes(), _health(), fmt="plain")
        self.assertEqual(sub["links"], [])
        self.assertEqual(sub["meta"]["status"], "quota_exceeded")

    def test_disabled_user_gets_empty_subscription(self):
        sub = build_subscription(_user(enabled=0), _nodes(), _health(), fmt="json")
        self.assertEqual(sub["links"], [])
        self.assertEqual(sub["payload"], "")

    def test_ipv6_host_is_bracketed(self):
        node = _nodes()[0]
        node["host"] = "2001:db8::1"
        sub = build_subscription(_user(), [node], _health(), fmt="plain")
        self.assertIn("@[2001:db8::1]:443", sub["links"][0])

    def test_headers_present(self):
        sub = build_subscription(_user(), _nodes(), _health(), fmt="plain")
        self.assertIn("X-Healthy-Nodes", sub["headers"])
        self.assertIn("X-Quota-Remaining", sub["headers"])

    def test_ranked_best_first(self):
        nodes = _nodes()
        health = {"n1": {"score": 60}, "n2": {"score": 90}}
        sub = build_subscription(_user(), nodes, health, fmt="plain", min_score=50)
        self.assertIn("2.2.2.2", sub["links"][0])


if __name__ == "__main__":
    unittest.main()
