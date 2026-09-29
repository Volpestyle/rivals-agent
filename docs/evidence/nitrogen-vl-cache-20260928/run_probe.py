"""Bounded offline sampler/synthetic-update benchmark. NEVER launches automatically.

Requires the lead's explicit GPU release, absent game/recording, and a private runtime. Idle OBS needs explicit allowance.
No live input, corpus loading, cloud API, model checkpoint writes, or upstream harness.
"""
import argparse
import ctypes
import gc
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import threading
import time
from unittest.mock import patch


def digest(path):
    with open(path, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def save(path, value):
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2)
        f.flush()
        os.fsync(f.fileno())


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--assets', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--gpu-released', action='store_true')
    p.add_argument('--allow-idle-obs', action='store_true')
    args = p.parse_args()
    import datetime
    if datetime.datetime.now(datetime.timezone.utc) >= datetime.datetime.fromisoformat('2026-09-29T00:57:46+00:00'):
        raise SystemExit('45-minute owner deadline expired')
    if not args.gpu_released:
        raise SystemExit('Lead GPU release required; no CUDA inspection performed')
    if args.out.exists():
        raise SystemExit('Refuse result overwrite')
    import psutil
    def conflicts():
        return [p.name() for p in psutil.process_iter(['name'])
                if any(n in (p.info['name'] or '').lower() for n in (('marvel', 'rivals', 'obs-ffmpeg-mux') if args.allow_idle_obs else ('marvel', 'rivals', 'obs64', 'obs32', 'obs-ffmpeg-mux')))]
    if conflicts():
        raise SystemExit('Game/recording or unapproved OBS present; refused')
    start = time.monotonic()
    done = threading.Event()
    def watch():
        while not done.wait(1):
            if conflicts() or time.monotonic()-start > 300:
                args.out.with_suffix('.aborted.json').write_text(json.dumps({'reason': 'game/recording/unapproved OBS or five-minute limit'}))
                os._exit(3)
    threading.Thread(target=watch, daemon=True).start()
    k = ctypes.windll.kernel32
    k.GetCurrentProcess.restype = ctypes.c_void_p
    k.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
    assert k.SetPriorityClass(k.GetCurrentProcess(), 0x4000)
    import numpy as np
    import torch
    from PIL import Image
    from transformers import SiglipVisionConfig, SiglipVisionModel
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    torch.manual_seed(0)
    sys.path.insert(0, str(Path.cwd()))
    from scripts.job_status import write
    name = 'nitrogen-vl-cache-20260928'
    write(name, owner='explore-policy', stage='running', host='pc', evidence=str(args.out.resolve()))
    try:
        contract_path = Path('docs/evidence/nitrogen-native-policy-feasibility-20260928/gpu-01/contract-cpu-executed.json')
        contract = json.loads(contract_path.read_text())
        assert digest(args.assets/'ng.pt') == contract['checkpoint_sha256']
        for relative, sha in contract['source_hashes'].items():
            assert digest(args.assets/relative) == sha, relative
        sys.path.insert(0, str((args.assets/'upstream').resolve()))
        from nitrogen.flow_matching_transformer import nitrogen as upstream
        from nitrogen.mm_tokenizers import NitrogenTokenizer, NitrogenTokenizerConfig
        checkpoint = torch.load(args.assets/'ng.pt', map_location='cpu', weights_only=True, mmap=True)
        cfg = checkpoint['ckpt_config']
        assert cfg == contract['checkpoint_config']
        assert cfg['tokenizer_cfg']['game_mapping_cfg'] is None
        vision_cfg_path = Path('data/diagnostics/live-loop-profile-20260927/weights/config.json')
        vc = SiglipVisionConfig(**json.loads(vision_cfg_path.read_text())['vision_config'])
        # Shape-only construction on meta avoids random 2 GB CPU initialization
        # and avoids downloading an unrelated stock initialization. Every model
        # parameter is then assigned from the authenticated released checkpoint.
        with patch.object(upstream.SiglipVisionModel, 'from_pretrained', side_effect=lambda *_a, **_k: SiglipVisionModel(vc)), \
             patch.object(upstream, 'Beta', side_effect=lambda a,b: None), torch.device('meta'):
            model = upstream.NitroGen(upstream.NitroGen_Config(**cfg['model_cfg']), game_mapping=None)
        model.load_state_dict({n: v.to('cuda') for n,v in checkpoint['model'].items()}, strict=True, assign=True)
        model.vision_encoder.embeddings.position_ids = torch.arange(256, device='cuda').expand((1,-1))
        model.beta_dist = torch.distributions.Beta(cfg['model_cfg']['noise_beta_alpha'], cfg['model_cfg']['noise_beta_beta'])
        assert not any(t.is_meta for t in model.parameters())
        assert not any(t.is_meta for t in model.buffers())
        del checkpoint
        gc.collect()
        parameters = sum(t.numel() for t in model.parameters())
        trainable = sum(t.numel() for t in model.parameters() if t.requires_grad)
        assert parameters == contract['tensor_elements']
        assert trainable == contract['trainable_elements_from_state_names']
        tok = NitrogenTokenizer(NitrogenTokenizerConfig(**cfg['tokenizer_cfg']))
        tok.eval()
        fixtures = [Path(f'tests/fixtures/range/pos-fight-{n}.jpg') for n in ('017','060','101')]
        images = [torch.from_numpy(np.asarray(Image.open(f).convert('RGB').resize((256,256), Image.Resampling.BICUBIC)).copy())
                  .permute(2,0,1).float().div(127.5).sub(1)[None] for f in fixtures]
        def batch(image, count=1):
            data = tok.encode({'frames': image, 'dropped_frames': np.array([False])})
            data = {k: torch.as_tensor(v).unsqueeze(0).to('cuda') for k,v in data.items()}
            return {k: v.expand(count, *v.shape[1:]).contiguous() for k,v in data.items()}
        data = [batch(im) for im in images]
        from cache_wrapper import cached_vl
        model.eval()
        def raw_call(d, seed, cached=False, verify=False):
            torch.manual_seed(seed)
            state = None
            with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                if cached:
                    with cached_vl(model, verify=verify, hash_input=verify) as state:
                        raw = model.get_action(d, old_layout=False)['action_tensor']
                else:
                    raw = model.get_action(d, old_layout=False)['action_tensor']
                decoded = tok.decode({'action_tensor': raw})
                result = raw.float().cpu().numpy()
                decoded = {k:v.cpu().numpy() for k,v in decoded.items()}
            assert np.isfinite(result).all()
            return result, decoded, state

        def decoded_equal(a, b):
            return (np.array_equal(a['buttons'], b['buttons'])
                    and np.array_equal(np.sign(a['j_left']), np.sign(b['j_left']))
                    and np.array_equal(np.sign(a['j_right']), np.sign(b['j_right'])))

        refs = {}
        repeat_rows = []
        repeat_max = 0.
        repeat_decoded = True
        for fixture in range(3):
            for seed in range(3):
                first, decoded, _ = raw_call(data[fixture], seed)
                refs[fixture,seed] = first, decoded
                errors = []
                for _ in range(2):
                    other, other_decoded, _ = raw_call(data[fixture], seed)
                    errors.append(float(np.max(np.abs(other-first))))
                    repeat_decoded &= decoded_equal(decoded, other_decoded)
                repeat_max = max(repeat_max, *errors)
                repeat_rows.append(dict(fixture=fixture, seed=seed, max_abs=errors))
        tolerance = max(1e-6, 5*repeat_max)
        repeat = dict(max_abs=repeat_max, absolute_tolerance=tolerance, relative_tolerance=0,
                      hard_tolerance_ceiling=1e-5, decoded_equal=bool(repeat_decoded), rows=repeat_rows,
                      protocol_sha256=digest(Path(__file__).with_name('PROTOCOL.md')),
                      script_sha256=digest(__file__), wrapper_sha256=digest(Path(__file__).with_name('cache_wrapper.py')))
        save(args.out.with_suffix('.repeatability.json'), repeat)
        if tolerance > 1e-5 or not repeat_decoded:
            save(args.out, dict(verdict='PARK: baseline repeatability failed', repeatability=repeat))
            write(name, stage='done', progress='PARK: baseline repeatability failed')
            return
        write(name, progress='repeatability/tolerance frozen; cached parity')
        parity_rows = []
        parity_max = 0.
        parity_pass = True
        retained = {}
        for fixture,seed in [(i,j) for i in range(3) for j in range(3)]+[(0,0),(1,0),(0,0)]:
            raw, decoded, state = raw_call(data[fixture], seed, cached=True, verify=True)
            ref, ref_decoded = refs[fixture,seed]
            error = float(np.max(np.abs(raw-ref)))
            decisions_equal = decoded_equal(decoded, ref_decoded)
            count_ok = state['calls'] == 16 and state['computes'] == 1
            parity_pass &= error <= tolerance and decisions_equal and count_ok
            parity_max = max(parity_max, error)
            parity_rows.append(dict(fixture=fixture, seed=seed, max_abs=error,
                                    decoded_equal=bool(decisions_equal), **state))
            retained[f'baseline_{fixture}_{seed}'] = ref
            retained[f'cached_{fixture}_{seed}'] = raw
        aba = parity_rows[-3:]
        reset_ok = aba[0]['input_sha256'] == aba[2]['input_sha256'] != aba[1]['input_sha256']
        parity_pass &= reset_ok
        parity = dict(pass_=bool(parity_pass), max_abs=parity_max, tolerance=tolerance,
                      decoded_buttons_and_stick_signs_equal=all(r['decoded_equal'] for r in parity_rows),
                      aba_cache_reset=reset_ok, rows=parity_rows)
        np.savez(args.out.with_suffix('.raw-actions.npz'), **retained)
        save(args.out.with_suffix('.parity.json'), parity)
        if not parity_pass:
            save(args.out, dict(verdict='PARK: parity failed', repeatability=repeat, parity=parity))
            write(name, stage='done', progress='PARK: parity failed')
            return
        # First timing instrumentation occurs only after tolerance and parity files.
        mixer_events = []
        original = model.vl_self_attention_model.forward
        def timed_mixer(context):
            begin, end = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
            begin.record()
            output = original(context)
            end.record()
            mixer_events.append((begin,end))
            return output
        with patch.object(model.vl_self_attention_model, 'forward', timed_mixer):
            raw_call(data[0], 0)
        torch.cuda.synchronize()
        mixer_ms = [a.elapsed_time(b) for a,b in mixer_events]
        assert len(mixer_ms) == 16
        def timed_calls(use_cache):
            def sample(d):
                with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                    if use_cache:
                        with cached_vl(model):
                            output = model.get_action(d, old_layout=False)
                    else:
                        output = model.get_action(d, old_layout=False)
                    return {k:v.cpu().numpy() for k,v in tok.decode(output).items()}
            torch.manual_seed(0)
            for i in range(3):
                sample(data[i])
            torch.cuda.reset_peak_memory_stats()
            times = []
            for i in range(30):
                torch.cuda.synchronize()
                t = time.perf_counter()
                decoded = sample(data[i%3])
                times.append((time.perf_counter()-t)*1000)
                assert all(np.isfinite(v).all() for v in decoded.values())
            return dict(calls=30, warmup=3, ms=times, p50_ms=float(np.percentile(times,50)),
                        p95_ms=float(np.percentile(times,95)), peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                        peak_reserved_bytes=torch.cuda.max_memory_reserved())
        write(name, progress='parity PASS; standalone timing')
        baseline = timed_calls(False)
        cached = timed_calls(True)
        verdict = 'PASS: proposal only, no fit' if cached['p95_ms'] <= 150 else 'PARK: cached p95 above 150 ms'
        result = dict(verdict=verdict, repeatability=repeat, parity=parity, baseline=baseline, cached=cached,
                      mixer_profile=dict(call_count=16, ms=mixer_ms, sum_ms=sum(mixer_ms)),
                      parameters=parameters, trainable_parameters=trainable, checkpoint_config=cfg,
                      checkpoint_sha256=contract['checkpoint_sha256'], contract_sha256=digest(contract_path),
                      source_hashes=contract['source_hashes'], fixture_hashes={str(f):digest(f) for f in fixtures},
                      versions={n:importlib.metadata.version(n) for n in ['torch','torchvision','transformers','diffusers','numpy','pydantic','einops','polars','psutil']},
                      gpu=torch.cuda.get_device_name(), cuda=torch.version.cuda,
                      precision='FP32 parameters/BF16 autocast, eager, CFG1, all16 steps, horizon18',
                      elapsed_s=time.monotonic()-start, idle_obs_authorized=args.allow_idle_obs,
                      process_peak_working_set_bytes=psutil.Process().memory_info().peak_wset)
        assert not any(x in sys.modules for x in ('nitrogen.game_env','xspeedhack','nitrogen.inference_session'))
        save(args.out, result)
        write(name, stage='done', progress=verdict)
        print(json.dumps(dict(verdict=verdict, parity_max=parity_max, tolerance=tolerance,
                             baseline_p50=baseline['p50_ms'], baseline_p95=baseline['p95_ms'],
                             cached_p50=cached['p50_ms'], cached_p95=cached['p95_ms'],
                             mixer_sum_ms=sum(mixer_ms), elapsed_s=result['elapsed_s']),indent=2))
    except BaseException:
        write(name, stage='failed')
        raise
    finally:
        done.set()


if __name__ == '__main__':
    main()
