"""Synthetic selection checks: no corpus or video reads."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("intent_audit", Path(__file__).with_name("audit.py"))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class SelectionTests(unittest.TestCase):
    def rows(self):
        return [{"i": i, "anchor_ns": i*100000000, "run": "a", "suitability": "accepted",
                 "regime": "normal", "gap_free": True, "relative_known": True,
                 "mouse_dx": 3 if 20 <= i < 25 else 0} for i in range(60)]

    def test_valid_direction_and_exact_offsets(self):
        events = audit.candidates(self.rows(), 100000000, 1)
        self.assertTrue(events)
        self.assertTrue(all(e["direction"] == "right" for e in events))
        self.assertEqual([r["offset_rows"] for r in events[0]["frames"]], [-10, -5, 0, 5, 10, 20])

    def test_left(self):
        rows = self.rows()
        for r in rows:
            r["mouse_dx"] *= -1
        self.assertTrue(all(e["direction"] == "left" for e in audit.candidates(rows, 100000000, 1)))

    def test_reject_gap_unknown_and_unaccepted(self):
        for key, value in (("gap_free", False), ("relative_known", False),
                           ("suitability", "rejected"), ("run", "b")):
            rows = self.rows()
            rows[20][key] = value
            self.assertEqual(audit.candidates(rows, 100000000, 1), [])

    def test_still_and_balanced_motion_do_not_qualify(self):
        rows = self.rows()
        for r in rows:
            r["mouse_dx"] = 0
        self.assertEqual(audit.candidates(rows, 100000000, 1), [])
        for r in rows:
            r["mouse_dx"] = 5 if r["i"] % 2 else -5
        self.assertEqual(audit.candidates(rows, 100000000, 1), [])

    def test_selection_separation_and_shortfall(self):
        pool = [{"center": i, "direction": d} for i, d in
                ((0, "left"), (1, "left"), (50, "right"), (200, "left"), (400, "right"))]
        selected = audit.choose(pool, 100000000)
        self.assertEqual([e["center"] for e in selected], [0, 200, 400])


if __name__ == "__main__":
    unittest.main()
