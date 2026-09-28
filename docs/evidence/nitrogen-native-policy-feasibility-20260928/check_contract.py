"""CPU-only contract probe. Executes pinned tokenizer methods, never the game harness.

Synthetic labels only. This is a feasibility adapter, not a live executor/trainer.
Run with --assets data/diagnostics/native-policy-feasibility-20260928.
"""
import argparse
import ast
import ctypes
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys

import numpy as np
import torch

SHA = 'a266f5fb9c7dbdcdf97216558d2d82075a9a994b824cda69afa9fd3280260a81'
REV = '32608444660950ffda95e1e57c79632ad65bea10'
BUTTONS = ['BACK', 'DPAD_DOWN', 'DPAD_LEFT', 'DPAD_RIGHT', 'DPAD_UP', 'EAST',
           'GUIDE', 'LEFT_SHOULDER', 'LEFT_THUMB', 'LEFT_TRIGGER', 'NORTH',
           'RIGHT_BOTTOM', 'RIGHT_LEFT', 'RIGHT_RIGHT', 'RIGHT_SHOULDER',
           'RIGHT_THUMB', 'RIGHT_TRIGGER', 'RIGHT_UP', 'SOUTH', 'START', 'WEST']
MAP = {'jump': 'LEFT_SHOULDER', 'get_over_here': 'RIGHT_SHOULDER',
       'web_cluster': 'LEFT_TRIGGER', 'spider_power': 'RIGHT_TRIGGER',
       'web_swing': 'SOUTH', 'amazing_combo': 'EAST'}
MOVE = ('move_forward', 'move_left', 'move_back', 'move_right')


def targets(states, sticks=(None, None)):
    """Tri-state labels: absent/None means unknown, not an observed zero.

    States already combine held/press within a native 30 Hz bin. RT is the OR
    of Spider-Power and its melee alias. Masks represent physical-coordinate
    knowledge, not permission to send; non-whitelisted outputs stay masked.
    Calibrated stick targets must be supplied separately; no default Cal map.
    """
    a = np.zeros(25, dtype=np.float32)
    a[21:] = .5
    mask = np.zeros(25, dtype=bool)
    for semantic, button in MAP.items():
        values = [states.get(semantic)]
        if semantic == 'spider_power':
            values.append(states.get('melee'))
        value = 1 if 1 in values else (0 if all(v == 0 for v in values) else None)
        if value is not None:
            a[BUTTONS.index(button)] = value
            mask[BUTTONS.index(button)] = True
    move = [states.get(n) for n in MOVE]
    if all(v is not None for v in move):
        f, left, back, right = move
        x, y = right-left, f-back
        norm = max(1, math.hypot(x, y))
        a[21:23] = (np.array([x/norm, y/norm]) + 1) / 2
        mask[21:23] = True
    for i, value in enumerate(sticks, 23):
        if value is not None:
            if not math.isfinite(value) or not -1 <= value <= 1:
                raise ValueError('calibrated stick outside [-1,1]')
            a[i], mask[i] = (value+1)/2, True
    return a, mask


def low_priority():
    if sys.platform == 'win32':
        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = ctypes.c_void_p
        k.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        assert k.SetPriorityClass(k.GetCurrentProcess(), 0x4000)
    torch.set_num_threads(2)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--assets', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    low_priority()
    receipt = json.loads((args.assets/'checkpoint-receipt.json').read_text())
    assert receipt['sha256'] == SHA
    # Streaming hash in the acquisition receipt; no expensive second scan during
    # the live sitting. The eventual sampler must independently authenticate it.
    checkpoint = torch.load(args.assets/'ng.pt', map_location='cpu', weights_only=True, mmap=True)
    cfg = checkpoint['ckpt_config']
    assert (cfg['model_cfg']['action_dim'], cfg['model_cfg']['action_horizon'],
            cfg['model_cfg']['num_inference_timesteps']) == (25, 18, 16)
    assert cfg['tokenizer_cfg']['old_layout'] is False
    assert cfg['tokenizer_cfg']['game_mapping_cfg'] is None
    source = args.assets/'upstream/nitrogen/mm_tokenizers.py'
    tree = ast.parse(source.read_text())
    klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'NitrogenTokenizer')
    names = {'pack_actions', 'unpack_actions', '_prepare_action'}
    methods = [n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name in names]
    probe = ast.ClassDef(name='PinnedTokenizerMethods', bases=[], keywords=[], body=methods, decorator_list=[])
    scope = {'np': np, 'torch': torch}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[probe], type_ignores=[])), str(source), 'exec'), scope)
    tok = scope['PinnedTokenizerMethods']()
    tok.old_layout, tok.action_horizon, tok.max_action_dim = False, 18, 25
    # The actual named channels come from the pinned shared file, not this copy.
    shared = ast.parse((args.assets/'upstream/nitrogen/shared.py').read_text())
    actual = next(ast.literal_eval(n.value) for n in shared.body if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == 'BUTTON_ACTION_TOKENS' for t in n.targets))
    assert actual == BUTTONS
    checks = []
    for j in range(21):
        buttons = np.zeros((1, 18, 21), dtype=np.float32)
        buttons[0, :, j] = 1
        axes = np.zeros((1, 18, 2), dtype=np.float32)
        packed = tok.pack_actions(buttons, axes, axes)
        left, right, decoded = tok.unpack_actions(torch.from_numpy(packed)[None])
        assert np.array_equal(decoded.numpy(), buttons)
        assert not left.any() and not right.any()
    checks.append('all 21 button one-hots, neutral axes: exact')
    axes = np.resize(np.array([-1, -.5, 0, .5, 1], np.float32), (1, 18, 2))
    packed = tok.pack_actions(np.zeros((1, 18, 21)), axes, -axes)
    left, right, _ = tok.unpack_actions(torch.from_numpy(packed)[None])
    assert np.array_equal(left.numpy(), axes) and np.array_equal(right.numpy(), -axes)
    checks.append('both sticks, five signed values: exact')
    a, mask = targets({})
    assert not mask.any() and np.array_equal(a[21:], [.5]*4)
    base = {n: 0 for n in (*MAP, *MOVE, 'melee')}
    for n, button in MAP.items():
        a, mask = targets(base | {n: 1}, (.5, -.5))
        assert a[BUTTONS.index(button)] == 1
        assert mask.sum() == 10
        assert not mask[[i for i in range(21) if BUTTONS[i] not in MAP.values()]].any()
    for n in MOVE:
        _, mask = targets(base | {n: None})
        assert not mask[21:23].any()
    rt = BUTTONS.index('RIGHT_TRIGGER')
    assert not targets(base | {'melee': None})[1][rt]
    assert targets(base | {'melee': None, 'spider_power': 1})[1][rt]
    # Mask must REPLACE the upstream all-supplied-columns-known mask.
    a, mask = targets({})
    _, upstream_mask, _ = tok._prepare_action({'action': np.tile(a, (18, 1))})
    assert upstream_mask.all() and not np.tile(mask, (18, 1)).any()
    checks.append('unknown actions/axes and unsupported channels remain masked; upstream replacement required')
    # A masked velocity target contributes zero gradient (finite placeholders).
    pred = torch.ones((18, 25), requires_grad=True)
    known = torch.from_numpy(np.tile(targets(base)[1], (18, 1)))
    ((pred.square()*known).sum()/(known.sum()+1e-6)).backward()
    assert not pred.grad[~known].any() and pred.grad[known].gt(0).all()
    checks.append('masked loss coordinates have zero direct gradient')
    directions = {tuple(targets(dict(zip(MOVE, bits)))[0][21:23]) for bits in itertools.product((0, 1), repeat=4)}
    assert len(directions) == 9
    checks.append('16 digital movement combinations collapse to 9 stick states (opposite-key ambiguity)')
    # An 18-row chunk boundary must carry previous state. No invented press at boundary.
    states = [0]*17 + [1]*3 + [0]*16
    edges = [int(s and not (states[i-1] if i else 0)) for i, s in enumerate(states)]
    assert sum(edges) == 1 and edges[17] == 1 and edges[18] == 0
    checks.append('cross-chunk held-state edge: one press, no duplicate at chunk start')
    fps = 30
    shift = cfg['modality_cfg']['action_shift']
    indices = list(range(shift, shift+18))
    times = [i/fps for i in indices]
    assert [round(t*fps) for t in times] == indices
    checks.append('declared native 30 Hz row/time round trip exact; checkpoint shift=3 preserved')
    tensors = checkpoint['model']
    total = sum(t.numel() for t in tensors.values())
    frozen = sum(t.numel() for n,t in tensors.items() if n.startswith(('vision_encoder.encoder.layers.11.', 'vision_encoder.head.')))
    groups = {}
    for name, tensor in tensors.items():
        key = name.split('.')[0]
        groups[key] = groups.get(key, 0)+tensor.numel()
    result = dict(checkpoint_sha256=SHA, source_commit=REV, checkpoint_config=cfg,
                  tensor_elements=total, upstream_frozen_elements=frozen,
                  trainable_elements_from_state_names=total-frozen, groups=groups,
                  checks=checks, check_groups_passed=len(checks),
                  native_cadence=dict(hz=fps, row_indices=indices, first_start_s=times[0],
                                      last_start_s=times[-1], last_end_s=(indices[-1]+1)/fps,
                                      chunk_duration_s=18/fps, pretrained_hz='not recorded'),
                  limitations=['No physical camera calibration verified', 'State channels lose within-bin taps and semantic aliases',
                               'Masking loss does not eliminate unknown-channel conditioning; finite fillers are not observed neutral',
                               'No sampler or training forward executed; PC GPU held for live sitting'],
                  source_hashes={str(f.relative_to(args.assets)): hashlib.sha256(f.read_bytes()).hexdigest()
                                 for f in (args.assets/'upstream').rglob('*') if f.is_file()})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x', encoding='utf-8') as out:
        json.dump(result, out, indent=2)
    print(json.dumps({k: result[k] for k in ('check_groups_passed', 'tensor_elements', 'trainable_elements_from_state_names', 'native_cadence')}))


if __name__ == '__main__':
    main()
