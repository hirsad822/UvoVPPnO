import unittest
from pulsegrid.presets import apply_preset, get_preset, list_presets, recommend_preset


class TestPresets(unittest.TestCase):
    def test_catalogue_has_five(self):
        self.assertEqual(len(list_presets("expert")), 5)

    def test_simple_mode_hides_expert_keys(self):
        for p in list_presets("simple"):
            self.assertNotIn("mux", p["config"])
            self.assertNotIn("sockopt", p["config"])

    def test_expert_mode_shows_keys(self):
        for p in list_presets("expert"):
            self.assertIn("mux", p["config"])

    def test_apply_unknown_raises(self):
        with self.assertRaises(ValueError):
            apply_preset("nope")

    def test_apply_merges_overrides(self):
        r = apply_preset("balanced", {"transport": "ws"})
        self.assertEqual(r["config"]["transport"], "ws")
        self.assertEqual(r["preset"], "balanced")

    def test_recommend_unreachable_is_resilient(self):
        self.assertEqual(recommend_preset({"reachable": False, "score": 0}), "resilient")

    def test_recommend_high_loss_is_resilient(self):
        self.assertEqual(recommend_preset({"reachable": True, "score": 40, "loss_pct": 8}), "resilient")

    def test_recommend_low_latency(self):
        self.assertEqual(recommend_preset({"reachable": True, "score": 95, "latency_ms": 20, "loss_pct": 0}), "low_latency")

    def test_get_preset_returns_copy(self):
        p = get_preset("balanced")
        p["config"]["transport"] = "mutated"
        self.assertNotEqual(get_preset("balanced")["config"]["transport"], "mutated")


if __name__ == "__main__":
    unittest.main()
