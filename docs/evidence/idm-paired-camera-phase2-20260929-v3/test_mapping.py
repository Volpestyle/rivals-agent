"""Synthetic mapping/scoring only, no boundary/prepare/score calls."""
import unittest
import paired


class MappingTests(unittest.TestCase):
    def test_offset_nearest_and_tie(self):
        self.assertEqual(paired.nearest([0, 2], 1), 0)
        self.assertEqual(paired.nearest([0, 2], 1.01), 1)

    def test_complete_context_and_all_shifts(self):
        live = [120 + i/120 for i in range(240)]
        replay = [t + paired.OFFSET for t in live]
        rows = paired.pairs(live,replay,[(120,122)])
        self.assertTrue(rows)
        for r in rows:
            self.assertEqual(len(r['live']),17)
            self.assertEqual(len(r['replay']),17)
            self.assertGreaterEqual(min(r['replay']),1)
            self.assertLess(max(r['replay'])+1,len(replay))
            self.assertLess(abs(r['alignment_ms']),1e-9)

    def test_exclusion_applies_to_whole_context(self):
        live=[120+i/120 for i in range(360)]
        replay=[t+paired.OFFSET for t in live]
        intervals=[(120,121),(122,123)]
        rows=paired.pairs(live,replay,intervals)
        self.assertTrue(rows)
        self.assertTrue(all(any(a<=live[r['live'][0]] and live[r['live'][-1]]<b for a,b in intervals) for r in rows))
        self.assertEqual(paired.pairs(live,replay,[(120,120.1)]),[])

    def test_missing_replay_frame_refuses_affected_contexts(self):
        live=[120+i/120 for i in range(240)]
        replay=[t+paired.OFFSET for t in live]
        del replay[100]
        for r in paired.pairs(live,replay,[(120,122)]):
            self.assertFalse(live[r['live'][0]] <= live[100] <= live[r['live'][-1]])

    def test_metric(self):
        self.assertEqual(paired.metric([1,-1],[0,0]),{'n':2,'mae_deg':1,'rmse_deg':1})
        self.assertIsNone(paired.metric([],[])['mae_deg'])
        with self.assertRaises(RuntimeError):
            paired.metric([1],[])


if __name__ == '__main__':
    unittest.main()
