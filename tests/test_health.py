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

class NativeWorkerTests(unittest.TestCase):
    def test_native_worker_called_and_failure_is_not_silent(self):
        import os
        from unittest.mock import patch
        import subprocess
        with patch.dict(os.environ, {'PULSEGRID_HEALTH_BIN': '/test/health-worker'}), \
             patch('pulsegrid.health.subprocess.run') as run:
            run.return_value.stdout = '80\n'
            self.assertEqual(score_health(10, 0, True, True, True), 80)
            self.assertEqual(run.call_args.args[0], ['/test/health-worker', '10', '0', 'true', 'true', 'true'])
            run.side_effect = OSError('unavailable')
            with self.assertRaises(RuntimeError):
                score_health(10, 0, True, True, True)
