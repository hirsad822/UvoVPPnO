import socket
import threading
import unittest

from pulsegrid.doctor import run_diagnostics


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class TestDoctor(unittest.TestCase):
    def test_localhost_listening_port_is_reachable(self):
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        port = srv.getsockname()[1]
        srv.listen(5)
        t = threading.Thread(target=lambda: srv.accept(), daemon=True)
        t.start()
        try:
            r = run_diagnostics("127.0.0.1", port, probes=3)
            self.assertTrue(r["reachable"])
            self.assertGreaterEqual(r["score"], 0)
            self.assertIn("findings", r)
            self.assertIn("summary", r)
        finally:
            srv.close()

    def test_closed_port_is_unreachable(self):
        port = _free_port()
        r = run_diagnostics("127.0.0.1", port, probes=2)
        self.assertFalse(r["reachable"])
        self.assertEqual(r["score"], 0)
        self.assertEqual(r["verdict"], "unhealthy")

    def test_result_shape(self):
        r = run_diagnostics("127.0.0.1", _free_port(), probes=1)
        for k in ("host", "port", "reachable", "latency_ms", "loss_pct",
                  "dns_ok", "tls_ok", "score", "verdict", "findings", "summary"):
            self.assertIn(k, r)


if __name__ == "__main__":
    unittest.main()
