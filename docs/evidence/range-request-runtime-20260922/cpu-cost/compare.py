"""One bounded synthetic CPU comparison; no checkpoints, training or game imports."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SEED, WARMUP, REPEATS = 7, 32, 200


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def stats(samples):
    ordered = sorted(samples)
    return {"n": len(samples), "min_ms": min(samples), "median_ms": statistics.median(samples),
            "p95_nearest_rank_ms": ordered[math.ceil(.95*len(samples))-1], "max_ms": max(samples),
            "mean_ms": statistics.mean(samples)}


def timed(call):
    t = time.perf_counter_ns()
    value = call()
    return value, (time.perf_counter_ns()-t)/1e6


def cpu_context():
    context = {"platform": platform.platform(), "machine": platform.machine(),
               "processor": platform.processor(), "logical_cpu_count_os": os.cpu_count(),
               "python": sys.version, "executable": sys.executable, "pid": os.getpid(),
               "thread_env": {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                                                           "NUMEXPR_NUM_THREADS", "OMP_DYNAMIC", "MKL_DYNAMIC")},
               "affinity": "inherited; not set/measured", "priority": "inherited; not adjusted",
               "background_load": "uncontrolled; no original-live thread counts or contention inferred"}
    if sys.platform == "win32":
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
            context["windows_cpu_registry"] = {name: winreg.QueryValueEx(key, name)[0]
                                               for name in ("ProcessorNameString", "Identifier", "VendorIdentifier")}
    return context


def worker(mode):
    sys.path.insert(0, str(ROOT))
    import torch
    from agent.state import Ability, Detection, State
    from policy.range_skill_policy import RangeSkillPolicy, SourceIdentity, Snapshot, Spec, REQUEST_SEMANTIC_REVISION, event_window, make_model

    context = cpu_context()
    initial = {"intra": torch.get_num_threads(), "inter": torch.get_num_interop_threads()}
    if mode != "default":
        torch.set_num_threads(int(mode))
    # Keep inter-op at fresh-process default in all arms: isolate intra-op change.
    context.update(torch_version=torch.__version__, device="cpu", initial_threads=initial,
                   effective_threads={"intra": torch.get_num_threads(), "inter": torch.get_num_interop_threads()},
                   torch_parallel_info=torch.__config__.parallel_info(), torch_build=torch.__config__.show(),
                   mkldnn_enabled=torch.backends.mkldnn.enabled, num_interop_threads_modified=False)
    torch.manual_seed(SEED)
    spec = Spec(hidden=8)
    model = make_model(spec, feature_count=26, output_count=2)
    history = []
    for i in range(5):
        t = i*.1
        target = Detection("enemy", (1100+i*2, 450, 1200+i*2, 720), .9, tagged=False, track=1, plate=True)
        state = State(t, (2560,1440), hp=250, max_hp=250, webs=3,
                      abilities={"pull": Ability(True), "uppercut": Ability(False, 1), "swing": Ability(True, 3)},
                      on_target=None, detections=[target])
        history.append(Snapshot(state, target, t))
    history = tuple(history)
    identity = SourceIdentity("synthetic-cpu-benchmark", "normal", digest("synthetic-profile"),
                              digest("synthetic-perception"), digest("synthetic-selector"),
                              semantic_revision=REQUEST_SEMANTIC_REVISION)
    fixture = [s.state.to_dict() for s in history]
    policy = RangeSkillPolicy(model, spec, identity, (1,1), "synthetic", digest(fixture),
                              {"bin_support":[1,1], "unique_events":1, "sampling":"full_grid_masked",
                               "synthetic_constructor_fixture_only":True, "optimizer_steps":0})
    call = lambda: policy.probabilities(history, .4, sampling="live")
    cold_probability, cold_ms = timed(call)
    for _ in range(WARMUP):
        call()
    probabilities, samples = [], []
    cpu_start = time.process_time()
    for _ in range(REPEATS):
        probability, ms = timed(call)
        samples.append(ms)
        probabilities.append(probability)
    cpu_seconds = time.process_time()-cpu_start

    # Same pure feature/window and tensor conversion as probabilities, timed
    # separately. Not a subtraction estimate of live stages or a fake forward.
    conversion = lambda: torch.tensor([event_window(history,.4,spec,sampling="live")], dtype=torch.float32, device="cpu")
    for _ in range(WARMUP):
        conversion()
    conversion_samples = [timed(conversion)[1] for _ in range(REPEATS)]
    tensor = conversion()
    assert list(tensor.shape) == [1,5,26]
    flat = tensor.flatten().tolist()
    weights = {name: {"shape":list(v.shape), "values":v.flatten().tolist()} for name,v in model.state_dict().items()}
    spread = max(abs(p[k]-cold_probability[k]) for p in probabilities for k in range(2))
    forbidden = [m for m in sys.modules if m in ("agent.controller", "agent.loop", "agent.learned_range_skill")
                 or m.startswith(("cv2", "perception", "dxcam", "vgamepad", "scripts.range_cast_probe"))]
    assert not forbidden
    return {"mode":mode, "context":context, "seed":SEED, "warmup":WARMUP, "repeats":REPEATS,
            "architecture":"actual make_model:GRU(26,8,batch_first=True)+Linear(8,2), eval/no_grad CPU float32",
            "weights_origin":"fresh fixed-seed initialization; no optimizer/training/checkpoint", "weights_sha256":digest(weights),
            "synthetic_fixture_sha256":digest(fixture), "input_tensor_shape":list(tensor.shape),
            "input_tensor_float32_sha256":hashlib.sha256(struct.pack('<130f',*flat)).hexdigest(),
            "input_tensor_float32":flat, "probabilities":list(cold_probability),
            "maximum_within_process_probability_delta":spread, "cold_first_probability_ms":cold_ms,
            "actual_probability_path":stats(samples), "probability_path_samples_ms":samples,
            "feature_window_tensor_conversion":stats(conversion_samples),
            "probability_batch_process_cpu_seconds":cpu_seconds,
            "forbidden_modules_imported":forbidden,
            "code_sha256":{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
                           ("agent/state.py", "policy/range_policy.py", "policy/range_skill_policy.py", "policy/execution.py")}}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--worker", choices=("default","1","4"))
    args=ap.parse_args()
    if args.worker:
        print(json.dumps(worker(args.worker), allow_nan=False))
        return
    paths=[OUT/(mode+'.json') for mode in ('default','1','4')]+[OUT/'report.json']
    assert not any(p.exists() for p in paths), "preserve completed comparison; no tuning reruns"
    results=[]
    for mode,path in zip(('default','1','4'),paths):
        completed=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--worker',mode],
                                 capture_output=True,text=True,check=True,timeout=60,
                                 creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
        result=json.loads(completed.stdout)
        with path.open('x',encoding='utf-8',newline='\n') as stream:
            json.dump(result,stream,indent=2);stream.write('\n')
        results.append(result)
    assert len({r['context']['effective_threads']['inter'] for r in results})==1
    assert len({r['weights_sha256'] for r in results})==1
    assert len({r['input_tensor_float32_sha256'] for r in results})==1
    assert len({r['synthetic_fixture_sha256'] for r in results})==1
    baseline=results[0]['probabilities']
    deltas={r['mode']:max(abs(a-b) for a,b in zip(baseline,r['probabilities'])) for r in results}
    assert all(all(abs(a-b)<=1e-7+1e-6*abs(a) for a,b in zip(baseline,r['probabilities'])) for r in results)
    report={'scope':'one_fresh_process_per_configuration_synthetic_untrained_cpu_cost_only',
            'inter_op_design':'unchanged fresh-process default in all arms; isolates intra-op thread setting; no inter-op tuning',
            'seed':SEED,'warmup':WARMUP,'repeats':REPEATS,'order':['default','1','4'],
            'contextual_reference_from_root_not_remeasured':{'HUD_ms':[13.3,13.6],'tag_ms':[6.9,7.2]},
            'comparison':[{'mode':r['mode'],'threads':r['context']['effective_threads'],
                           'cold_ms':r['cold_first_probability_ms'],'probability_path':r['actual_probability_path'],
                           'conversion':r['feature_window_tensor_conversion']} for r in results],
            'equality':{'weights_exact':True,'input_float32_exact':True,'synthetic_fixture_exact':True,
                        'probability_atol':1e-7,'probability_rtol':1e-6,'max_absolute_probability_delta':deltas},
            'worker_reports':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths[:3]},
            'limits':['Original live Torch thread counts unrecorded; these are current fresh-process defaults only.',
                      'No human checkpoint/rows, model replay, training, native JPGs or cv2 imports.',
                      'Synthetic probabilities test numeric dispatch only, not trained policy behavior.',
                      'Sequential bounded microbenchmark with uncontrolled background load; no live contention or stage attribution.',
                      'Root HUD/tag measurements are context, not combined with this into a measured live budget.']}
    with paths[-1].open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(report,stream,indent=2);stream.write('\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
