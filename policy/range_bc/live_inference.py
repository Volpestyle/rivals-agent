"""Inference-only building blocks. No capture, pad, corpus or downloads.

Persistent FFmpeg preserves cache.GRAPH exactly. Device selection is explicit;
the caller still owns every live guard, review receipt and scheduling decision.
"""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import subprocess
import threading


class InProcessCachePreprocessor:
    """Execute the exact cache graph via PyAV/libavfilter, without a raw pipe.

    The small parser accepts only the simple labelled chains used by cache.GRAPH.
    No image operators are approximated or reimplemented. Installed FFmpeg build
    parity must be checked; changing libraries invalidates that evidence.
    """
    def __init__(self, *, compact_bgr=False):
        import av
        from policy.range_bc import cache
        self.av = av
        self.graph = cache.GRAPH.format(select="null")
        if compact_bgr:
            # BGR input is already full range; channel permutation commutes with
            # the per-channel area scales. Convert only the small stacked output.
            # This variant requires its own exact-pixel parity evidence.
            self.graph = self.graph.replace("null,showinfo," + cache.CONVERT + ",", "null,") + ",format=rgb24"
        self.version = {"pyav": av.__version__, "libraries": av.library_versions}
        self.filter_graph, self.shape, self.index, self.closed = None, None, 0, False
        self.lock = threading.Lock()

    def _start(self, frame):
        import re
        graph = self.av.filter.Graph()
        graph.threads = 1
        source = graph.add_buffer(template=frame)
        labels = {}
        last = None
        for chain in self.graph.split(";"):
            inputs = []
            while chain.startswith("["):
                label, chain = chain[1:].split("]", 1)
                inputs.append(labels[label])
            outputs = re.findall(r"\[([^]]+)\]", chain)
            chain = chain.split("[", 1)[0]
            previous = None
            for spec in chain.split(","):
                name, _, args = spec.partition("=")
                node = graph.add(name, args or None)
                if previous is None:
                    for port, (parent, output) in enumerate(inputs or [(source, 0)]):
                        parent.link_to(node, output_idx=output, input_idx=port)
                else:
                    previous.link_to(node)
                previous = node
            for port, label in enumerate(outputs):
                labels[label] = (previous, port)
            last = previous
        sink = graph.add("buffersink")
        last.link_to(sink)
        graph.configure()
        self.filter_graph, self.source, self.sink = graph, source, sink

    def __call__(self, frame):
        from fractions import Fraction
        import numpy as np
        if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3 or min(frame.shape[:2]) < 256:
            raise ValueError("native uint8 BGR frame >=256x256 required")
        if not self.lock.acquire(blocking=False):
            raise RuntimeError("concurrent preprocessing refused")
        try:
            if self.closed:
                raise RuntimeError("preprocessor is closed")
            video = self.av.VideoFrame.from_ndarray(frame, format="bgr24")
            video.time_base, video.pts = Fraction(1, 30), self.index
            self.index += 1
            if self.filter_graph is None:
                self._start(video)
                self.shape = frame.shape
            if frame.shape != self.shape:
                raise ValueError("capture geometry changed")
            self.source.push(video)
            result = self.sink.pull()
            if result.pts != video.pts:
                self.close()
                raise ValueError("preprocessor returned a stale frame")
            stack = result.to_ndarray(format="rgb24")
            if stack.shape != (352, 256, 3):
                raise ValueError("wrong cache output geometry")
            return stack[:144].copy(), stack[144:272, :128].copy(), stack[272:, :200].copy()
        finally:
            self.lock.release()

    def close(self):
        self.closed = True
        self.filter_graph = None
        self.source = self.sink = None


class PersistentCachePreprocessor:
    """One FFmpeg process per frame geometry, bounded to one request at a time.

    A timeout or short read poisons the instance and kills its child. Never retry
    or reuse output from a failed request. close() must be called by its owner.
    """
    def __init__(self, ffmpeg="ffmpeg", timeout=2.):
        from agent.live_range_bc import CachePreprocessor
        reference = CachePreprocessor(ffmpeg, timeout)
        self.ffmpeg, self.timeout = ffmpeg, timeout
        self.graph, self.version = reference.graph, reference.version
        self.process, self.shape = None, None
        self.lock, self.closed = threading.Lock(), False
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cache-pipe")

    def _start(self, shape):
        h, w, _ = shape
        # Input probe must not wait for future observations; rawvideo output must
        # flush one frame immediately. Both codec and filter threads are bounded.
        cmd = [self.ffmpeg, "-v", "error", "-nostdin", "-threads", "1", "-filter_complex_threads", "1",
               "-probesize", "32", "-analyzeduration", "0", "-f", "rawvideo", "-pix_fmt", "bgr24",
               "-s", f"{w}x{h}", "-i", "pipe:0", "-filter_complex", self.graph,
               "-threads", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", "-flush_packets", "1", "pipe:1"]
        self.process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, bufsize=0)
        self.shape = shape

    def _exchange(self, raw):
        import numpy as np
        view = memoryview(raw)
        while view:
            n = self.process.stdin.write(view)
            if not n:
                raise OSError("FFmpeg input closed")
            view = view[n:]
        remaining, chunks = 352 * 256 * 3, []
        while remaining:
            chunk = self.process.stdout.read(remaining)
            if not chunk:
                raise OSError("FFmpeg output truncated")
            chunks.append(chunk)
            remaining -= len(chunk)
        stack = np.frombuffer(b"".join(chunks), np.uint8).reshape(352, 256, 3)
        return stack[:144].copy(), stack[144:272, :128].copy(), stack[272:, :200].copy()

    def __call__(self, frame):
        import numpy as np
        if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3 or min(frame.shape[:2]) < 256:
            raise ValueError("native uint8 BGR frame >=256x256 required")
        if not self.lock.acquire(blocking=False):
            raise RuntimeError("concurrent preprocessing refused")
        try:
            if self.closed:
                raise RuntimeError("preprocessor is closed")
            if self.process is None:
                self._start(frame.shape)
            if frame.shape != self.shape:
                raise ValueError("capture geometry changed")
            future = self.worker.submit(self._exchange, frame.tobytes())
            try:
                return future.result(timeout=self.timeout)
            except BaseException as exc:
                self.close()
                if isinstance(exc, TimeoutError):
                    raise TimeoutError("persistent FFmpeg timed out; instance closed") from exc
                raise
        finally:
            self.lock.release()

    def close(self):
        self.closed = True
        if self.process is not None:
            if self.process.poll() is None:
                self.process.kill()
            self.process.wait(timeout=2)
            self.process.stdin.close()
            self.process.stdout.close()
        self.worker.shutdown(wait=True, cancel_futures=True)


class DevicePredictor:
    """FP32 recurrent predictor with explicit CPU/CUDA placement and batched DINO.

    Model and preprocessing dimensions remain checkpoint-defined. No stale-frame
    caching, approximate image resize, lower precision or threshold changes.
    """
    def __init__(self, model, preprocessor, *, cooldowns, backbone=None, device="cpu"):
        import torch
        from agent.live_range_bc import require
        require(device in ("cpu", "cuda"), "device must be cpu or cuda")
        require(cooldowns in ("normal", "off"), "unknown cooldown regime")
        require(getattr(model.config, "arm", "I") == "I" or backbone is not None,
                "CM3 H/W needs DINO")
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but unavailable; no silent fallback")
        self.device, self.preprocess = torch.device(device), preprocessor
        self.model = model.to(self.device).eval()
        self.backbone = backbone.to(self.device).eval() if backbone is not None else None
        self.regime = torch.tensor([[float(cooldowns == "off")]], device=self.device)
        self.state = None

    def __call__(self, frame, previous):
        import torch
        from agent.live_range_bc import require
        from policy.range_bc import steps
        with torch.inference_mode():
            rgb = [torch.from_numpy(x) for x in self.preprocess(frame)]
            if self.backbone is not None:
                from policy.range_bc.cm3_features import preprocess
                pixels = torch.cat((preprocess(rgb[0][None], "global"), preprocess(rgb[1][None], "crop")))
                features = self.backbone(pixels.to(self.device))
                views = features[0:1, None], features[1:2, None], torch.zeros(1, 1, 1, device=self.device)
            else:
                views = tuple(x.permute(2, 0, 1)[None, None].to(self.device) for x in rgb)
            prev = torch.tensor(steps.prev_vector(previous), dtype=torch.float32, device=self.device)[None, None]
            acts, cams, self.state = self.model(*views, prev, self.state, regime=self.regime)
            require(bool(torch.isfinite(acts).all()) and bool(torch.isfinite(cams).all()), "nonfinite model outputs")
            return torch.sigmoid(acts[0, 0]).tolist(), torch.softmax(cams[0, 0], -1).tolist()

    def close(self):
        close = getattr(self.preprocess, "close", None)
        if close is not None:
            close()


def load_explore_checkpoint(path, sha256, *, encoder=False):
    """Explicit exploratory H1 loader; does not promote it to a live checkpoint."""
    import torch
    from agent.live_range_bc import require, sha256 as digest
    from policy.range_bc.model import Config
    from policy.range_bc.explore_chunks import ChunkPolicy
    from policy.range_bc.explore_chunks_train import FORMAT
    require(digest(path) == sha256, "checkpoint hash mismatch")
    payload = torch.load(path, map_location="cpu", weights_only=True, mmap=True)
    require(payload["format"] == FORMAT and payload["tag"] == "EXPLORATORY", "wrong checkpoint format")
    recipe = payload["recipe"]
    require(recipe["horizon"] == 1, "only H1 inference is supported")
    config = Config.from_dict(recipe["config"])
    require(config.frames and not config.hud, "no-HUD pixel policy required")
    cls = ChunkPolicy
    if encoder:
        from policy.range_bc.explore_encoder import EncoderPolicy
        cls = EncoderPolicy
    model = cls(config, horizon=1)
    model.load_state_dict(payload["model"], strict=True)
    require(all(bool(torch.isfinite(t).all()) for t in model.state_dict().values()), "nonfinite weights")
    require(digest(path) == sha256, "checkpoint changed during loading")
    return model.eval(), recipe


class EncoderPredictor(DevicePredictor):
    """Completed SigLIP/NitroGen two-view tower + recurrent policy.

    CUDA uses the training bf16 tower and float16 cache rounding. CPU uses an
    explicitly reported FP32 tower fallback. The trained projection/core/heads
    stay FP32. No downloaded or custom model code is executed.
    """
    def __init__(self, model, preprocessor, *, vision_path, vision_sha256, config_path,
                 config_sha256, device="cpu"):
        import json
        from pathlib import Path
        import torch
        from safetensors.torch import load_file
        from transformers import SiglipVisionConfig, SiglipVisionModel
        from agent.live_range_bc import require, sha256
        super().__init__(model, preprocessor, cooldowns="normal", device=device)
        require(sha256(config_path) == config_sha256, "vision config hash mismatch")
        require(sha256(vision_path) == vision_sha256, "vision weight hash mismatch")
        config = SiglipVisionConfig(**json.loads(Path(config_path).read_text())["vision_config"])
        require((config.hidden_size, config.num_hidden_layers, config.num_attention_heads,
                 config.intermediate_size, config.image_size, config.patch_size) == (1024, 24, 16, 4096, 256, 16),
                "unexpected vision tower")
        # Meta construction plus assign avoids a second 1.26 GB random tower.
        with torch.device("meta"):
            self.tower = SiglipVisionModel(config)
        self.tower.load_state_dict(load_file(str(vision_path)), strict=True, assign=True)
        # The nonpersistent position index is absent from state_dict by design.
        embeddings = self.tower.vision_model.embeddings
        embeddings.position_ids = torch.arange(embeddings.num_positions).expand((1, -1))
        self.tower_dtype = torch.bfloat16 if device == "cuda" else torch.float32
        self.tower.to(device=self.device, dtype=self.tower_dtype).eval().requires_grad_(False)

    def __call__(self, frame, previous):
        import torch
        from torch.nn import functional as F
        from agent.live_range_bc import require
        from policy.range_bc import steps
        from policy.range_bc.explore_encoder import pool_tokens
        with torch.inference_mode():
            rgb = self.preprocess(frame)
            pixels = []
            for x in rgb[:2]:
                x = torch.from_numpy(x).permute(2, 0, 1)[None].to(self.device).float()
                x = F.interpolate(x, (256, 256), mode="bilinear", align_corners=False, antialias=True)
                pixels.append((x / 127.5 - 1).to(self.tower_dtype))
            # Same spatial pooling and cache precision as extraction; batching
            # the two independent views removes dispatch, not a temporal step.
            tokens = self.tower(pixel_values=torch.cat(pixels)).last_hidden_state
            features = pool_tokens(tokens).to(torch.float16)
            views = features[0:1, None], features[1:2, None], torch.zeros(1, 1, 1, device=self.device)
            prev = torch.tensor(steps.prev_vector(previous), dtype=torch.float32, device=self.device)[None, None]
            acts, cams, self.state = self.model(*views, prev, self.state, regime=self.regime)
            require(bool(torch.isfinite(acts).all()) and bool(torch.isfinite(cams).all()), "nonfinite model outputs")
            return torch.sigmoid(acts[0, 0]).tolist(), torch.softmax(cams[0, 0], -1).tolist()
