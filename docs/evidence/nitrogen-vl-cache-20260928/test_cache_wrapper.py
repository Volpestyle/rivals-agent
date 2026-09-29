import unittest
import torch
from cache_wrapper import cached_vl


class Toy(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.vl_self_attention_model = torch.nn.Linear(2, 2)


class CacheTest(unittest.TestCase):
    def test_per_call_reset_and_restoration(self):
        model = Toy().eval()
        original = model.vl_self_attention_model.forward
        a, b = torch.zeros(1,2), torch.ones(1,2)
        with cached_vl(model, verify=True, hash_input=True) as first:
            x = model.vl_self_attention_model(a)
            self.assertIs(x, model.vl_self_attention_model(a))
        self.assertEqual((first['calls'],first['computes']), (2,1))
        self.assertEqual(model.vl_self_attention_model.forward, original)
        with cached_vl(model, verify=True, hash_input=True) as second:
            y = model.vl_self_attention_model(b)
        self.assertTrue(torch.equal(y, original(b)))
        self.assertNotEqual(first['input_sha256'], second['input_sha256'])

    def test_changed_context_refuses_and_restores(self):
        model = Toy().eval()
        original = model.vl_self_attention_model.forward
        with self.assertRaisesRegex(AssertionError, 'context changed'):
            with cached_vl(model, verify=True):
                model.vl_self_attention_model(torch.zeros(1,2))
                model.vl_self_attention_model(torch.ones(1,2))
        self.assertEqual(model.vl_self_attention_model.forward, original)

    def test_training_refused(self):
        with self.assertRaisesRegex(ValueError, 'eval-only'):
            with cached_vl(Toy()):
                pass


if __name__ == '__main__':
    torch.set_num_threads(2)
    unittest.main()
