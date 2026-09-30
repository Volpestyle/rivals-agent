"""Pure synthetic gate tests; never boundary(), prepare() or score()."""
import unittest
from types import SimpleNamespace
import paired


class ReviewTests(unittest.TestCase):
    def valid(self):
        return {'reviewer':'synthetic', 'prepared_sha256':'a'*64, 'evidence':'fake evidence',
                'same_identity':True,'continuous_pov':True,'replay_1x':True,'focused':True,
                'ui_excluded':True,'valid_live_intervals':[[120,155]]}

    def test_valid(self):
        self.assertEqual(paired.check_review(self.valid(),'a'*64),[[120,155]])

    def test_flags_refuse_false_missing_and_truthy(self):
        for flag in ('same_identity','continuous_pov','replay_1x','focused','ui_excluded'):
            for value in (False,None,1,'true'):
                r=self.valid(); r[flag]=value
                with self.subTest(flag=flag,value=value), self.assertRaises(RuntimeError):
                    paired.check_review(r,'a'*64)
            r=self.valid(); del r[flag]
            with self.assertRaises(RuntimeError):
                paired.check_review(r,'a'*64)

    def test_metadata_refusals(self):
        for field,value in (('reviewer',''),('evidence',''),('prepared_sha256','b'*64)):
            r=self.valid();r[field]=value
            with self.subTest(field=field),self.assertRaises(RuntimeError):
                paired.check_review(r,'a'*64)

    def test_interval_refusals(self):
        for intervals in ([],[[119,155]],[[120,156]],[[122,121]],[[120,123],[122,124]],
                          [[float('nan'),155]],[['120',155]]):
            r=self.valid(); r['valid_live_intervals']=intervals
            with self.subTest(intervals=intervals),self.assertRaises((RuntimeError,TypeError)):
                paired.check_review(r,'a'*64)
        r=self.valid();del r['valid_live_intervals']
        with self.assertRaises(KeyError):
            paired.check_review(r,'a'*64)

    def test_module_origin_refuses_before_hash(self):
        bad=SimpleNamespace(__file__=str(paired.PACKET/'fake_policy.py'))
        with self.assertRaisesRegex(RuntimeError,'outside original closure'):
            paired.module_provenance(bad,bad,bad)


if __name__ == '__main__':
    unittest.main()
