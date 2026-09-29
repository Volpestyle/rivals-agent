"""Private inference-only, one-get_action-call VL cache. No package-file edits."""
from contextlib import contextmanager
from unittest.mock import patch


@contextmanager
def cached_vl(model, *, verify=False, hash_input=False):
    import hashlib
    import torch

    if model.training or model.vl_self_attention_model.training:
        raise ValueError('VL caching is eval-only')
    original = model.vl_self_attention_model.forward
    state = {'calls': 0, 'computes': 0, 'input_sha256': None}
    cached = None
    first_input = None

    def forward(context):
        nonlocal cached, first_input
        state['calls'] += 1
        if cached is None:
            if verify:
                first_input = context.detach().clone()
            if hash_input:
                raw = context.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes()
                state['input_sha256'] = hashlib.sha256(raw).hexdigest()
            cached = original(context)
            state['computes'] += 1
        elif verify and not torch.equal(context, first_input):
            raise AssertionError('VL context changed within sampler invocation')
        return cached

    try:
        with patch.object(model.vl_self_attention_model, 'forward', forward):
            yield state
    finally:
        cached = None
        first_input = None
