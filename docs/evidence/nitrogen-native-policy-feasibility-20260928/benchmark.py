"""Bounded offline sampler/synthetic-update benchmark. NEVER launches automatically.

Requires the lead's explicit GPU release, absent game/OBS, and a private runtime.
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


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--assets', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--gpu-released', action='store_true')
    args = p.parse_args()
    if not args.gpu_released:
        raise SystemExit('Lead GPU release required; no CUDA inspection performed')
    if args.out.exists():
        raise SystemExit('Refuse result overwrite')
    import psutil
    def conflicts():
        return [p.name() for p in psutil.process_iter(['name'])
                if any(n in (p.info['name'] or '').lower() for n in ('marvel', 'rivals', 'obs64', 'obs32'))]
    if conflicts():
        raise SystemExit('Game or OBS present; refused')
    start = time.monotonic()
    done = threading.Event()
    def watch():
        while not done.wait(1):
            if conflicts() or time.monotonic()-start > 600:
                args.out.with_suffix('.aborted.json').write_text(json.dumps({'reason': 'game/OBS or ten-minute limit'}))
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
    name = 'native-policy-sampler-20260928'
    write(name, owner='explore-policy', stage='running', host='pc', evidence=str(args.out.resolve()))
    try:
        contract_path = Path(__file__).with_name('contract-cpu.json')
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
        def sample(d):
            with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                output = tok.decode(model.get_action(d, old_layout=False))
                return {k:v.cpu().numpy() for k,v in output.items()}
        model.eval()
        for i in range(3):
            sample(data[i])
        torch.cuda.reset_peak_memory_stats()
        samples = []
        for i in range(30):
            torch.cuda.synchronize()
            t = time.perf_counter()
            out = sample(data[i%3])
            samples.append((time.perf_counter()-t)*1000)
            assert all(np.isfinite(v).all() for v in out.values())
        result = dict(checkpoint_sha256=contract['checkpoint_sha256'], checkpoint_config=cfg,
                      benchmark_sha256=digest(__file__), contract_sha256=digest(contract_path),
                      vision_config_sha256=digest(vision_cfg_path),
                      fixture_hashes={str(f):digest(f) for f in fixtures},
                      versions={n:importlib.metadata.version(n) for n in ['torch','torchvision','transformers','diffusers','numpy','pydantic','einops','polars','psutil']},
                      gpu=torch.cuda.get_device_name(), cuda=torch.version.cuda,
                      precision='FP32 parameters, BF16 autocast; original 16-step sampler, CFG=1',
                      parameters=parameters, trainable_parameters=trainable,
                      sampler=dict(calls=30, warmup=3, ms=samples,
                                   p50_ms=float(np.percentile(samples,50)), p95_ms=float(np.percentile(samples,95)),
                                   peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                                   peak_reserved_bytes=torch.cuda.max_memory_reserved()),
                      excludes=['capture', 'image decode/resize', 'host-to-device input transfer', 'hardware pad', 'game contention'])
        # Preserve inference evidence even if the bounded synthetic update OOMs.
        args.out.with_suffix('.sampler.json').write_text(json.dumps(result, indent=2))
        write(name, progress='sampler measured; synthetic batch-1 updates')
        model.train()
        d = batch(images[0])
        d['actions'] = torch.zeros((1,18,25), device='cuda')
        d['actions'][:,:,21:] = .5
        d['actions_mask'] = torch.zeros((1,18,25), dtype=torch.bool, device='cuda')
        d['actions_mask'][:,:,[5,7,9,14,16,18,21,22,23,24]] = True
        d['has_real_action'] = torch.ones(1, dtype=torch.bool, device='cuda')
        optimizer = torch.optim.AdamW([t for t in model.parameters() if t.requires_grad], lr=1e-4, weight_decay=.001, foreach=False)
        steps = []
        try:
            torch.cuda.reset_peak_memory_stats()
            for i in range(12):
                torch.cuda.synchronize()
                t = time.perf_counter()
                optimizer.zero_grad(set_to_none=True)
                with torch.autocast('cuda', dtype=torch.bfloat16):
                    loss = model(d)['loss']
                assert torch.isfinite(loss)
                loss.backward()
                optimizer.step()
                torch.cuda.synchronize()
                steps.append(time.perf_counter()-t)
            result['synthetic_training'] = dict(batch=1, warmup=2, measured_updates=10,
                seconds=steps[2:], updates_s=10/sum(steps[2:]),
                peak_allocated_bytes=torch.cuda.max_memory_allocated(), peak_reserved_bytes=torch.cuda.max_memory_reserved(),
                scope='all released trainable modules; upstream vision layer11/head remain frozen',
                exclusions='no real data I/O, masks/calibration qualification, evaluation or checkpoint writes; not a fit')
        except torch.cuda.OutOfMemoryError as exc:
            result['synthetic_training'] = dict(status='OOM; no larger attempt', completed_updates=len(steps), error=str(exc))
        result['process_peak_working_set_bytes'] = psutil.Process().memory_info().peak_wset
        assert not any(x in sys.modules for x in ('nitrogen.game_env','xspeedhack','nitrogen.inference_session'))
        result['forbidden_imports_absent'] = True
        result['elapsed_s'] = time.monotonic()-start
        with args.out.open('x') as f:
            json.dump(result, f, indent=2)
        write(name, stage='done')
        print(json.dumps({k: result[k] for k in ('sampler','synthetic_training','process_peak_working_set_bytes')}, indent=2))
    except BaseException:
        write(name, stage='failed')
        raise
    finally:
        done.set()


if __name__ == '__main__':
    main()
