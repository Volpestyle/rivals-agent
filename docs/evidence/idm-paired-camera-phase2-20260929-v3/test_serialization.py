import json
import unittest
import paired


class SerializationTest(unittest.TestCase):
    def test_flattened_list_refuses_corrected_nested_list_accepts(self):
        review=json.loads('{"reviewer":"synthetic","prepared_sha256":"fake","evidence":"fake","same_identity":true,"continuous_pov":true,"replay_1x":true,"focused":true,"ui_excluded":true,"valid_live_intervals":[120,155]}')
        with self.assertRaises(TypeError):
            paired.check_review(review,'fake')
        review['valid_live_intervals']=[[120,155]]
        self.assertEqual(paired.check_review(review,'fake'),[[120,155]])


if __name__=='__main__':unittest.main()
