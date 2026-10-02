"""Live learned policy: native BGR frames in, semantic actions plus camera degrees out.

One call per decision. The model is recurrent and was trained at 30 Hz (one step = 1/30 s), so call `step` once per
captured frame at about that rate and `reset()` whenever the episode restarts. No capture, pad or game IO happens
here: the caller owns every live guard and turns `Step` into pad input (camera degrees through the camera map).

A bundle is a directory with `bundle.json` naming its files (see `write_bundle`). The first bundle is the confirmed
NitroGen-tower no-history policy (docs/lanes/policy.md): offline press F1 0.30, yaw worse than zero motion.
Decision latency on the RTX 4080 SUPER with torch preprocessing: p50 25 ms, p95 31 ms.

    from policy.live_policy import LivePolicy
    policy = LivePolicy("D:/rivals-policy/bundles/ng-nohist-s1", device="cuda")
    step = policy.step(frame_bgr)          # uint8 HxWx3 BGR, the desktop capture
    step.held["jump"], step.yaw_deg, step.pitch_deg, step.yaw_deg_s
"""
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import time

STEP_S = 1 / 30
TRAIN_SIZE = (2560, 1440)       # every admitted recording; the crop view is 256x256 native pixels at this size
MAX_GAP_S = .5                  # a longer gap between frames carries no usable motion for bc2


@dataclass
class Step:
    """One decision. Actions are semantic (policy.range_bc.vocab.NAMES); only `live` actions are ever set.

    held: the action should be held down during this step. press/release: edges this step (a tap is press and
    release in one step, with held False; hold it for one step). yaw_deg/pitch_deg: requested rotation over this
    step, yaw positive right, pitch positive DOWN; *_deg_s is the same as a rate. probs: raw (hold, press, release)
    probabilities. latency_ms: preprocessing + model on this call."""
    held: dict
    press: dict
    release: dict
    yaw_deg: float
    pitch_deg: float
    yaw_deg_s: float
    pitch_deg_s: float
    probs: dict
    latency_ms: float
    index: int

    def as_dict(self):
        return asdict(self)


def _sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_bundle(directory, *, checkpoint, vision, vision_config, evaluation, name, notes=""):
    """Record a bundle's files, hashes, TRAIN-chosen thresholds and live action mask in bundle.json."""
    from policy.range_bc import vocab
    directory = Path(directory)
    evaluation_data = json.loads((directory / evaluation).read_text())
    calibration = evaluation_data["threshold_calibration"]["actions"]
    bundle = {"format": "rivals-live-policy-bundle-v1", "name": name, "kind": "encoder_h1", "notes": notes,
              "step_s": STEP_S, "train_size": list(TRAIN_SIZE), "actions": list(vocab.NAMES),
              "files": {}, "thresholds": {n: calibration[n]["threshold"] for n in vocab.NAMES},
              "live": {n: bool(calibration[n]["live"]) for n in vocab.NAMES}}
    for key, file in (("checkpoint", checkpoint), ("vision", vision), ("vision_config", vision_config),
                      ("evaluation", evaluation)):
        bundle["files"][key] = {"path": file, "sha256": _sha256(directory / file)}
    (directory / "bundle.json").write_text(json.dumps(bundle, indent=2) + "\n")
    return bundle


def write_bc2_bundle(directory, *, checkpoint, report, tag="selected", name, notes="",
                     vision="vision.safetensors", vision_config="siglip2-large-config.json",
                     buttons=None, buttons_evaluation=None, camera_decode="mean"):
    """A policy.bc2 bundle: Policy2 checkpoint, the NitroGen tower, and report.json's TRAIN-calibrated thresholds.
    Hybrid: `buttons` (an encoder_h1 checkpoint on the same tower features) and its evaluation.json replace the
    action head and thresholds; the camera stays bc2's. camera_decode: "mean" (expectation; the better onset
    direction on val) or "median"."""
    from policy.range_bc import vocab
    directory = Path(directory)
    rep = json.loads((directory / report).read_text())
    live = vocab.live_mask([10 ** 6] * vocab.N)
    bundle = {"format": "rivals-live-policy-bundle-v1", "name": name, "kind": "bc2", "notes": notes,
              "step_s": STEP_S, "train_size": list(TRAIN_SIZE), "actions": list(vocab.NAMES), "files": {},
              "thresholds": rep[tag]["thresholds"], "live": dict(zip(vocab.NAMES, map(bool, live))),
              "camera_decode": camera_decode}
    entries = [("checkpoint", checkpoint), ("vision", vision), ("vision_config", vision_config), ("report", report)]
    if buttons:
        calibration = json.loads((directory / buttons_evaluation).read_text())["threshold_calibration"]["actions"]
        bundle["thresholds"] = {n: calibration[n]["threshold"] for n in vocab.NAMES}
        entries += [("buttons", buttons), ("buttons_evaluation", buttons_evaluation)]
    for key, file in entries:
        bundle["files"][key] = {"path": file, "sha256": _sha256(directory / file)}
    (directory / "bundle.json").write_text(json.dumps(bundle, indent=2) + "\n")
    return bundle


def load_encoder_checkpoint(path, sha256):
    """An H1 encoder-head checkpoint (EXPLORATORY or CONFIRM tag) from the chunk trainer."""
    import torch
    from policy.range_bc.explore_chunks_train import FORMAT
    from policy.range_bc.explore_encoder import EncoderPolicy
    from policy.range_bc.model import Config
    if _sha256(path) != sha256:
        raise ValueError(f"{path}: checkpoint hash differs from bundle.json")
    payload = torch.load(path, map_location="cpu", weights_only=True, mmap=True)
    recipe = payload["recipe"]
    if payload["format"] != FORMAT or recipe["horizon"] != 1:
        raise ValueError("expected an H1 range-chunks checkpoint")
    model = EncoderPolicy(Config.from_dict(recipe["config"]), horizon=1)
    model.load_state_dict(payload["model"], strict=True)
    return model.eval(), recipe


class LivePolicy:
    def __init__(self, bundle_dir, *, device="cuda", thresholds="train", resize=True, preprocess="torch",
                 camera_decode=None, cuda_graph=True):
        """thresholds: "train" (per-action, TRAIN-calibrated to human press counts) or a float for all actions.
        resize: scale frames that are not 2560x1440 to it (area) first, so the crop view keeps its training field
        of view. Otherwise a different size is refused.
        preprocess: "torch" computes the cache views on the model's device (area scaling is exact average pooling
        at 2560x1440, so it stays off the CPU the game needs); "ffmpeg" runs the exact cache graph on the CPU."""
        from policy.range_bc import vocab
        from policy.range_bc.live_inference import EncoderPredictor, InProcessCachePreprocessor
        root = Path(bundle_dir)
        self.bundle = json.loads((root / "bundle.json").read_text())
        files = {k: (root / v["path"], v["sha256"]) for k, v in self.bundle["files"].items()}
        if preprocess not in ("torch", "ffmpeg"):
            raise ValueError("preprocess is torch or ffmpeg")
        self.kind, self.preprocess = self.bundle.get("kind", "encoder_h1"), preprocess
        if self.kind == "bc2":
            import torch
            from policy.bc2.features import load_tower
            from policy.bc2.model import Config, Policy2
            if preprocess != "torch":
                raise ValueError("bc2 bundles run with preprocess='torch'")
            for key in ("checkpoint", "vision", "vision_config"):
                if _sha256(files[key][0]) != files[key][1]:
                    raise ValueError(f"{files[key][0]}: hash differs from bundle.json")
            payload = torch.load(files["checkpoint"][0], map_location="cpu", weights_only=True)
            self.model = Policy2(Config(**payload["config"]))
            self.model.load_state_dict(payload["model"], strict=True)
            self.model.to(device).eval()
            self.tower = load_tower(files["vision"][0], files["vision_config"][0], device)
            self.predict = None
            self.buttons = None
            if "buttons" in files:
                self.buttons = load_encoder_checkpoint(*files["buttons"])[0].to(device).eval()
        else:
            model, self.recipe = load_encoder_checkpoint(*files["checkpoint"])
            # Training cache frames were full-range RGB decoded from YUV; the capture is already full-range BGR.
            self.predict = EncoderPredictor(model, InProcessCachePreprocessor(compact_bgr=True)
                                            if preprocess == "ffmpeg" else None, vision_path=files["vision"][0],
                                            vision_sha256=files["vision"][1], config_path=files["vision_config"][0],
                                            config_sha256=files["vision_config"][1], device=device)
        self.names = vocab.NAMES
        self.mask = tuple(bool(self.bundle["live"][n]) for n in self.names)
        self.levels = tuple(float(self.bundle["thresholds"][n]) if thresholds == "train" else float(thresholds)
                            for n in self.names)
        self.resize, self.device = resize, device
        # bc2 on CUDA replays one captured CUDA graph per decision (captured on the first frame).
        self.graph = {} if (cuda_graph and self.kind == "bc2" and str(device).startswith("cuda")) else None
        self.camera_decode = camera_decode or self.bundle.get("camera_decode", "median")
        if self.camera_decode not in ("median", "mean"):
            raise ValueError("camera_decode is median or mean")
        self.reset()

    def reset(self):
        """Start a new episode: clear the recurrent state and the held-action memory."""
        from policy.range_bc import vocab
        if self.predict is not None:
            self.predict.state = None
        self.state, self.gray_prev, self.buttons_state, self.t_prev = None, None, None, None
        if getattr(self, "graph", None):
            import torch
            with torch.inference_mode():         # the graph's buffers are inference tensors
                for tensor in (*self.graph["state"], self.graph["prev_g"], self.graph["prev_c"]):
                    if tensor is not None:
                        tensor.zero_()
        self.prev = {"held": [0] * vocab.N, "press": [0] * vocab.N, "release": [0] * vocab.N,
                     "known": [True] * vocab.N, "cy": vocab.ZERO_CLASS, "cp": vocab.ZERO_CLASS}
        self.index = 0

    @staticmethod
    def _check(frame):
        import numpy as np
        if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("uint8 HxWx3 BGR frame required")
        return frame if frame.flags.c_contiguous else np.ascontiguousarray(frame)

    def _frame(self, frame):
        frame = self._check(frame)
        h, w = frame.shape[:2]
        if (w, h) == TRAIN_SIZE:
            return frame
        if not self.resize:
            raise ValueError(f"frame {w}x{h} differs from training {TRAIN_SIZE}; pass resize=True")
        import cv2
        return cv2.resize(frame, TRAIN_SIZE, interpolation=cv2.INTER_AREA if w > TRAIN_SIZE[0] else cv2.INTER_LINEAR)

    def _views(self, frame):
        """The cache's global (144x256) and crop (128x128) views: RGB float [1, 3, H, W] holding uint8 values."""
        import torch
        from policy.bc2.features import views_from_bgr
        if frame.shape[:2] != TRAIN_SIZE[::-1] and not self.resize:
            raise ValueError(f"frame {frame.shape[:2]} differs from training {TRAIN_SIZE[::-1]}")
        return views_from_bgr(torch.from_numpy(frame).to(self.device, non_blocking=True))

    def _bc2_core(self, frame_u8, prev_g, prev_c, use_prev, dt, tgt, h, c, bh=None, bc=None):
        """One bc2 step on device tensors, free of host syncs and host-to-device copies, so the same code runs
        eagerly and inside a CUDA graph. use_prev: 0-dim bool (False = no usable previous frame: no motion).
        tgt: [1, 1, TARGET_DIM] explicit target input (zeros when the model has none; see _target).
        Returns action probs [3, N], camera probs [2, C], new LSTM state, this frame's gray views, and the hybrid
        action head's state."""
        import torch
        from policy.bc2.features import tower_features, views_from_bgr
        from policy.bc2.model import gray_full, gray_small, green_profile
        rgb = [v.permute(0, 2, 3, 1).to(torch.uint8) for v in views_from_bgr(frame_u8)]
        feats = tower_features(self.tower, rgb)[None, None]           # both views in one tower batch
        gg = gray_full(rgb[0]) if self.model.config.hires else gray_small(rgb[0])
        gc = gray_small(rgb[1])
        pg, pc = torch.where(use_prev, prev_g, gg), torch.where(use_prev, prev_c, gc)
        green = green_profile(rgb[0]).to(torch.float16)[None] if self.model.config.use_green else None
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=frame_u8.is_cuda):
            acts, cams, (h1, c1) = self.model(feats, pg[None], gg[None], pc[None], gc[None], (h, c), green, dt,
                                              target=tgt)
        acts, cams = acts.float(), cams.float()
        if self.buttons is not None:          # hybrid: incumbent action head on the same tower features
            from policy.range_bc import steps
            zero = torch.zeros(1, 1, steps.PREV_DIM, device=feats.device)
            acts, _, (bh, bc) = self.buttons(feats[:, :, 0], feats[:, :, 1], None, zero, (bh, bc))
        return torch.sigmoid(acts[0, 0]), torch.softmax(cams[0, 0], -1), h1, c1, gg, gc, bh, bc

    def _bc2_inputs(self, t):
        """Per-step scalar inputs from the capture clock: (use previous frame?, frame interval in steps)."""
        now = time.perf_counter() if t is None else t
        gap = None if self.t_prev is None else now - self.t_prev
        use_prev = gap is not None and gap <= MAX_GAP_S and self.gray_prev is not None
        self.t_prev = now
        return use_prev, min(3., max(1., (gap or STEP_S) / STEP_S))

    def _zero_state(self):
        import torch
        cfg = self.model.config
        z = lambda: torch.zeros(cfg.layers, 1, cfg.hidden, device=self.device)
        bz = None
        if self.buttons is not None:
            bz = lambda: torch.zeros(1, 1, self.buttons.core.hidden_size, device=self.device)
        return z(), z(), (bz() if bz else None), (bz() if bz else None)

    def _target(self, frame):
        """The explicit target input for this frame: policy.bc2.target_features.extract on the full captured frame,
        the same guarded call the training extraction makes (zeros, i.e. unknown, when the model has no target
        input). The last vector and its reason are kept for diagnostics."""
        import numpy as np
        from policy.bc2.model import TARGET_DIM
        if not getattr(self.model.config, "use_target", False):
            return np.zeros(TARGET_DIM, np.float32)
        from policy.bc2.target_features import extract_with_reason
        vec, self.last_target_reason = extract_with_reason(frame, source_kind="range")
        self.last_target = vec
        return vec

    def _bc2_predict(self, frame, t=None):
        """policy.bc2: tower features of both views plus motion observed since the previous step's frame."""
        import torch
        use_prev, dt = self._bc2_inputs(t)
        tgt = self._target(frame)
        with torch.inference_mode():
            if self.graph is not None:
                return self._graph_step(frame, use_prev, dt, tgt)
            x = self._device_frame(frame)
            if self.state is None:
                self.state = self._zero_state()
            prev = self.gray_prev or (torch.zeros(1, 72, 128, dtype=torch.uint8, device=x.device),
                                      torch.zeros(1, 64, 64, dtype=torch.uint8, device=x.device))
            acts, cams, h, c, gg, gc, bh, bc = self._bc2_core(
                x, prev[0], prev[1], torch.tensor(use_prev, device=x.device),
                torch.full((1, 1), dt, device=x.device), torch.from_numpy(tgt)[None, None].to(x.device),
                *self.state)
            self.state, self.gray_prev = (h, c, bh, bc), (gg, gc)
            if not (bool(torch.isfinite(acts).all()) and bool(torch.isfinite(cams).all())):
                raise ValueError("nonfinite model outputs")
            return acts.tolist(), cams.tolist()

    def _device_frame(self, frame):
        import torch
        if frame.shape[:2] != TRAIN_SIZE[::-1] and not self.resize:
            raise ValueError(f"frame {frame.shape[:2]} differs from training {TRAIN_SIZE[::-1]}")
        return torch.from_numpy(frame).to(self.device, non_blocking=True)

    def _graph_step(self, frame, use_prev, dt, tgt):
        """CUDA-graph replay of _bc2_core: one launch per decision instead of hundreds, which matters when the
        game time-slices the GPU. Captured on the first frame (per frame size); inputs copied into static
        buffers, outputs copied back into the recurrent state."""
        import torch
        g = self.graph
        if g.get("shape") != frame.shape:
            self._capture(frame)
            g = self.graph
        g["host"].copy_(torch.from_numpy(frame))
        g["frame"].copy_(g["host"], non_blocking=True)
        g["use_prev"].fill_(bool(use_prev))
        g["dt"].fill_(dt)
        g["target"].copy_(torch.from_numpy(tgt)[None, None])
        g["graph"].replay()
        acts, cams, h, c, gg, gc, bh, bc = g["out"]
        for dst, src in zip(g["state"], (h, c, bh, bc)):
            if dst is not None:
                dst.copy_(src)
        g["prev_g"].copy_(gg)
        g["prev_c"].copy_(gc)
        self.gray_prev = True                  # marks that a previous frame exists (its grays live in the graph)
        acts, cams = acts.cpu(), cams.cpu()
        if not (bool(torch.isfinite(acts).all()) and bool(torch.isfinite(cams).all())):
            raise ValueError("nonfinite model outputs")
        return acts.tolist(), cams.tolist()

    def _capture(self, frame):
        import torch
        from policy.bc2.model import TARGET_DIM
        dev = self.device
        g = {"shape": frame.shape,
             "host": torch.empty(frame.shape, dtype=torch.uint8).pin_memory(),
             "frame": torch.zeros(frame.shape, dtype=torch.uint8, device=dev),
             "prev_g": torch.zeros(1, 72, 128, dtype=torch.uint8, device=dev),
             "prev_c": torch.zeros(1, 64, 64, dtype=torch.uint8, device=dev),
             "use_prev": torch.zeros((), dtype=torch.bool, device=dev),
             "dt": torch.ones(1, 1, device=dev),
             "target": torch.zeros(1, 1, TARGET_DIM, device=dev),
             "state": self._zero_state()}
        if self.model.config.hires:
            g["prev_g"] = torch.zeros(1, 144, 256, dtype=torch.uint8, device=dev)
        g["host"].copy_(torch.from_numpy(frame))
        g["frame"].copy_(g["host"])
        args = lambda: (g["frame"], g["prev_g"], g["prev_c"], g["use_prev"], g["dt"], g["target"], *g["state"])
        side = torch.cuda.Stream()
        side.wait_stream(torch.cuda.current_stream())
        with torch.inference_mode(), torch.cuda.stream(side):
            for _ in range(3):                   # warm-up (cuDNN/cuFFT plans, allocator) before capture
                self._bc2_core(*args())
        torch.cuda.current_stream().wait_stream(side)
        graph = torch.cuda.CUDAGraph()
        with torch.inference_mode(), torch.cuda.graph(graph):
            g["out"] = self._bc2_core(*args())
        g["graph"] = graph
        self.graph = g

    def _torch_predict(self, frame):
        """EncoderPredictor.__call__ with the cache views computed on the device."""
        import torch
        from torch.nn import functional as F
        from policy.range_bc import steps
        from policy.range_bc.explore_encoder import pool_tokens
        p = self.predict
        with torch.inference_mode():
            pixels = []
            for v in self._views(frame):
                v = F.interpolate(v, (256, 256), mode="bilinear", align_corners=False, antialias=True)
                pixels.append((v / 127.5 - 1).to(p.tower_dtype))
            tokens = p.tower(pixel_values=torch.cat(pixels)).last_hidden_state
            features = pool_tokens(tokens).to(torch.float16)
            feats = features[0:1, None], features[1:2, None], torch.zeros(1, 1, 1, device=p.device)
            prev = torch.tensor(steps.prev_vector(self.prev), dtype=torch.float32, device=p.device)[None, None]
            acts, cams, p.state = p.model(*feats, prev, p.state, regime=p.regime)
            if not (bool(torch.isfinite(acts).all()) and bool(torch.isfinite(cams).all())):
                raise ValueError("nonfinite model outputs")
            return torch.sigmoid(acts[0, 0]).tolist(), torch.softmax(cams[0, 0], -1).tolist()

    def step(self, frame_bgr, t=None):
        """t: the frame's capture time in seconds (any monotonic clock); default the call time. bc2 models use the
        interval between consecutive frames (clamped to 1-3 steps of 33 ms); after MAX_GAP_S they see no motion."""
        from policy.range_bc import executor, vocab
        started = time.perf_counter()
        if self.kind == "bc2":
            probs, cameras = self._bc2_predict(self._check(frame_bgr), t)
        elif self.preprocess == "torch":
            probs, cameras = self._torch_predict(self._check(frame_bgr))
        else:
            probs, cameras = self.predict(self._frame(frame_bgr), self.prev)
        held_p, press_p, release_p = (probs[i * vocab.N:(i + 1) * vocab.N] for i in range(3)) \
            if len(probs) == 3 * vocab.N else probs
        held, press, release = [], [], []
        for i, level in enumerate(self.levels):
            h, p, r = executor.decode_step(held_p, press_p, release_p, self.prev["held"], self.mask, threshold=level)
            held.append(h[i]), press.append(p[i]), release.append(r[i])
        yaw_p, pitch_p = cameras if len(cameras) == 2 else (cameras[:vocab.CAMERA_CLASSES], cameras[vocab.CAMERA_CLASSES:])
        cy, cp = vocab.median_class(yaw_p), vocab.median_class(pitch_p)
        if self.camera_decode == "mean":      # expectation: commits to the likelier side at turn onsets
            reps = [vocab.class_degrees(k) for k in range(vocab.CAMERA_CLASSES)]
            yaw, pitch = (sum(p * r for p, r in zip(axis, reps)) for axis in (yaw_p, pitch_p))
            cy, cp = vocab.camera_class(yaw), vocab.camera_class(pitch)
        else:
            yaw, pitch = vocab.class_degrees(cy), vocab.class_degrees(cp)
        self.prev = {"held": held, "press": press, "release": release, "known": [True] * vocab.N, "cy": cy, "cp": cp}
        self.index += 1
        named = lambda bits: {n: bool(b) for n, b in zip(self.names, bits)}
        return Step(held=named(held), press=named(press), release=named(release), yaw_deg=yaw, pitch_deg=pitch,
                    yaw_deg_s=yaw / STEP_S, pitch_deg_s=pitch / STEP_S,
                    probs={n: (held_p[i], press_p[i], release_p[i]) for i, n in enumerate(self.names)},
                    latency_ms=(time.perf_counter() - started) * 1000, index=self.index - 1)

    def close(self):
        if self.predict is not None and self.predict.preprocess is not None:
            self.predict.close()


def main(argv=None):
    """Bundle writing and a latency benchmark on recorded or synthetic frames."""
    import argparse
    p = argparse.ArgumentParser(description=main.__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("bundle")
    w.add_argument("dir")
    w.add_argument("--name", required=True)
    w.add_argument("--notes", default="")
    b = sub.add_parser("bench")
    b.add_argument("dir")
    b.add_argument("--device", default="cuda")
    b.add_argument("--frames", nargs="*", help="image files; default synthetic noise")
    b.add_argument("--n", type=int, default=100)
    b.add_argument("--out")
    a = p.parse_args(argv)
    if a.cmd == "bundle":
        print(json.dumps(write_bundle(a.dir, checkpoint="epoch-26.pt", vision="vision.safetensors",
                                      vision_config="siglip2-large-config.json", evaluation="evaluation.json",
                                      name=a.name, notes=a.notes), indent=2))
        return 0
    import numpy as np
    policy = LivePolicy(a.dir, device=a.device)
    if a.frames:
        import cv2
        frames = [cv2.imread(f) for f in a.frames]
    else:
        rng = np.random.default_rng(0)
        frames = [rng.integers(0, 256, (1440, 2560, 3), dtype=np.uint8) for _ in range(4)]
    for i in range(5):
        policy.step(frames[i % len(frames)])
    policy.reset()
    times, steps = [], []
    for i in range(a.n):
        s = policy.step(frames[i % len(frames)])
        times.append(s.latency_ms)
        steps.append(s)
    q = lambda x: float(np.percentile(times, x))
    result = {"device": a.device, "n": a.n, "p50_ms": q(50), "p95_ms": q(95), "max_ms": max(times),
              "gpu": __import__("torch").cuda.get_device_name() if a.device == "cuda" else None,
              "last": steps[-1].as_dict()}
    print(json.dumps(result, indent=2))
    if a.out:
        Path(a.out).write_text(json.dumps(result, indent=2) + "\n")
    policy.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
