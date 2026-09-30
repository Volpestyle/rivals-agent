"""Offline regression checks for expert span boundaries; no corpus is opened."""
import unittest
from io import BytesIO

from scripts.footage_corpus import exclude_review_intervals, jpeg_frames, spans_from_reads


class SpanTests(unittest.TestCase):
    def test_non_player_watchparty_interval_withholds_touching_spans(self):
        spans = [dict(start_s=a, end_s=b) for a, b in [(0, 10), (10, 20), (21, 30)]]
        kept = exclude_review_intervals(spans, [dict(start_s=10, end_s=25)])
        self.assertEqual(kept, spans[:1])

    def test_unknown_and_rejected_samples_split_spans(self):
        reads = [dict(t=t, accepted=t not in (10, 20)) for t in range(32)]
        spans = spans_from_reads(reads, max_gap=1.1, trim_s=0.5, min_s=4)
        self.assertEqual([(s["start_s"], s["end_s"]) for s in spans],
                         [(0.5, 8.5), (11.5, 18.5), (21.5, 30.5)])

    def test_missing_samples_never_bridge(self):
        reads = [dict(t=t, accepted=True) for t in (*range(10), *range(20, 30))]
        spans = spans_from_reads(reads, max_gap=1.1, trim_s=0.5, min_s=4)
        self.assertEqual(len(spans), 2)
        self.assertLess(spans[0]["end_s"], spans[1]["start_s"])

    def test_short_or_single_sample_run_is_not_training_data(self):
        self.assertEqual(spans_from_reads([dict(t=100, accepted=True)]), [])
        self.assertEqual(spans_from_reads([]), [])

    def test_jpeg_transport_preserves_frame_boundaries(self):
        frames = [b"\xff\xd8first\xff\xd9", b"\xff\xd8second\xff\xd9"]
        self.assertEqual(list(jpeg_frames(BytesIO(b"".join(frames)))), frames)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            list(jpeg_frames(BytesIO(b"\xff\xd8truncated")))

    def test_short_unknown_has_temporal_support_but_exclusions_do_not(self):
        rows = [dict(t=t/2, accepted=t != 10, reason="unknown" if t == 10 else "gameplay") for t in range(30)]
        spans = spans_from_reads(rows, max_gap=.6, trim_s=.5, min_s=4, bridge_unknown=2)
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0]["weak_samples"], 1)
        rows[10]["reason"] = "scoreboard"
        spans = spans_from_reads(rows, max_gap=.6, trim_s=.5, min_s=4, bridge_unknown=2)
        self.assertEqual(len(spans), 1)  # first half is too short after trimming
        self.assertGreater(spans[0]["start_s"], 5)


if __name__ == "__main__":
    unittest.main()
