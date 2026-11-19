import unittest
from pulsegrid.health import rank_nodes, score_health, verdict_for


class TestHealth(unittest.TestCase):
    def test_unreachable_scores_zero(self):
        self.assertEqual(score_health(reachable=False), 0)

    def test_perfect_scores_100(self):
        self.assertEqual(score_health(latency_ms=10, loss_pct=0, reachable=True,
                                      tls_ok=True, service_ok=True), 100)

    def test_high_latency_lowers_score(self):
        good = score_health(latency_ms=20, loss_pct=0, reachable=True, tls_ok=True, service_ok=True)
        bad = score_health(latency_ms=500, loss_pct=0, reachable=True, tls_ok=True, service_ok=True)
        self.assertLess(bad, good)

    def test_high_loss_lowers_score(self):
        good = score_health(latency_ms=20, loss_pct=0, reachable=True, tls_ok=True, service_ok=True)
        bad = score_health(latency_ms=20, loss_pct=20, reachable=True, tls_ok=True, service_ok=True)
        self.assertLess(bad, good)

    def test_verdict_thresholds(self):
        self.assertEqual(verdict_for(90), "healthy")
        self.assertEqual(verdict_for(60), "degraded")
        self.assertEqual(verdict_for(10), "unhealthy")

    def test_rank_sorts_best_first(self):
        nodes = [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}]
        health = {"a": {"score": 30}, "b": {"score": 95}}
        ranked = rank_nodes(nodes, health)
        self.assertEqual(ranked[0]["id"], "b")
        self.assertEqual(ranked[0]["verdict"], "healthy")


if __name__ == "__main__":
    unittest.main()
