"""What the embedding cache covers, and what each source is evidence of.

One `Source` per media file: our own range recordings under `data/l1/`, and the expert
footage under `data/demos/` (samples, vods, guides). Nothing here reads pixels; it reads
the acquisition lanes' manifests and says where the media is, who made it, and under which
rules it was played.

**Regime (`cooldowns`) is part of a source's identity, not a detail.** Every practice-range
recording made before tonight's baseline was made with Practice Settings "No Ability
Cooldown" ON: infinite ammo, the ult relit in seconds, no cooldown numbers. That is a
different game from normal-resource play, and the two are never mixed in one training or
evaluation set (the co-lead's reward contract). `off` is our cooldown-free range work,
`normal` is play with real resources, `unknown` is anything not established. A run states
its own regime in `meta.json` when the recorder writes one; otherwise it falls to RUNS
below, and an unlisted run is `unknown` rather than assumed.

Third-party media never leaves `data/`; this module holds paths and provenance, not pixels.
"""
import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

OFF, NORMAL, UNKNOWN = "off", "normal", "unknown"

# Our own range runs, by directory name: (regime, what that rests on). Every range run made
# before L4 disables the Practice Settings toggle is cooldown-free. A run whose meta.json states
# `cooldowns` overrides this, which is how runs recorded afterwards arrive as `normal`;
# rivals-brain is adding a required --cooldowns flag to the live loop so meta.json states it.
BEFORE_BASELINE = "recorded before the 2026-09-20 baseline"
LEAD_STATED = "lead, 2026-09-20: Practice Settings default not yet changed"
RUNS = {"tagrun": (OFF, BEFORE_BASELINE), "tagrun0": (OFF, BEFORE_BASELINE), "tagrun1": (OFF, BEFORE_BASELINE),
        "loop30a": (OFF, LEAD_STATED), "loop30b": (OFF, LEAD_STATED), "loop30c": (OFF, LEAD_STATED)}

# Matchmade VOD footage is normal-resource play: these are ranked matches, and the HUD lane's
# event stream reads cooldown countdowns and web-ammo reloads off them. Recorded as an
# inference from the footage, not a screen-by-screen check of a settings menu.
VOD_EVIDENCE = "matchmade match footage; the HUD event stream shows cooldowns running and web ammo reloading"
# Guides mix range demonstrations (often cooldown-free) with match clips in one video, so the
# regime is per-segment and not established: unknown until someone reads it off the screen.
GUIDE_EVIDENCE = "guide videos mix range demonstrations and match clips; regime not read off the screen"


@dataclass(frozen=True)
class Source:
    """One media file to embed, with the provenance the trainer must keep it separable by."""
    id: str
    kind: str          # run | sample | vod | guide
    path: Path         # the media: a run directory, or an mp4
    creator: str       # us | reqmr | daymr | day | req | matchuxd | ...
    group: str         # split unit: whole VOD / whole session. Never split within one
    cooldowns: str     # off | normal | unknown
    cooldowns_evidence: str
    fps: float | None = None
    duration_s: float | None = None
    index: Path | None = None   # a run's frames.jsonl

    @property
    def is_video(self):
        return self.kind != "run"


def _probe(entry):
    """(fps, duration_s) from an acquisition manifest's ffprobe block, or (None, None)."""
    probe = entry.get("probe") or {}
    video = next((s for s in probe.get("streams", []) if s.get("width")), {})
    rate = video.get("r_frame_rate") or ""
    fps = None
    if "/" in rate:
        num, den = rate.split("/")
        fps = float(num) / float(den) if float(den) else None
    duration = (probe.get("format") or {}).get("duration")
    return fps, (float(duration) if duration else None)


def runs(data=DATA):
    """Our own recordings: a directory with a frames.jsonl the loop or L4's trials wrote."""
    out = []
    for index in sorted((data / "l1").glob("*/frames.jsonl")):
        name = index.parent.name
        meta = index.parent / "meta.json"
        regime, evidence = RUNS.get(name, (UNKNOWN, "not listed in corpus.RUNS and the recorder stated none"))
        if meta.exists():
            stated = (json.loads(meta.read_text()) or {}).get("cooldowns")
            if stated:
                regime, evidence = stated, "stated by the recorder in meta.json"
        out.append(Source(id=f"run:{name}", kind="run", path=index.parent, creator="us",
                          group=f"run:{name}", cooldowns=regime, cooldowns_evidence=evidence, index=index))
    return out


def demos(data=DATA):
    """Expert footage from the acquisition lanes' manifests: samples, vods, guides."""
    out = []
    samples = data / "demos" / "samples" / "manifest.json"
    if samples.exists():
        for e in json.loads(samples.read_text()):
            fps, duration = _probe(e)
            clip = samples.parent / e["clip"]
            out.append(Source(id=clip.stem, kind="sample", path=clip, creator=e["creator"].lower(),
                              group=f"twitch:{e['vod_id']}", cooldowns=NORMAL, cooldowns_evidence=VOD_EVIDENCE,
                              fps=fps, duration_s=duration))
    vods = data / "demos" / "vods" / "manifest.json"
    if vods.exists():
        for e in json.loads(vods.read_text()):
            fps, duration = _probe(e)
            out.append(Source(id=e["id"], kind="vod", path=vods.parent / e["media"], creator=e["creator"].lower(),
                              group=e.get("group") or f"twitch:{e['vod_id']}", cooldowns=NORMAL,
                              cooldowns_evidence=VOD_EVIDENCE, fps=fps, duration_s=duration))
    guides = data / "demos" / "guides" / "manifest.json"
    if guides.exists():
        for e in json.loads(guides.read_text()):
            fps, duration = _probe(e)
            out.append(Source(id=e["id"], kind="guide", path=guides.parent / e["media"], creator=e["creator"].lower(),
                              group=f"guide:{e['id']}", cooldowns=UNKNOWN, cooldowns_evidence=GUIDE_EVIDENCE,
                              fps=fps, duration_s=duration))
    return out


def corpus(data=DATA, kinds=None):
    """Every source on this machine, ours first. `kinds` filters by kind."""
    found = [s for s in runs(data) + demos(data) if s.path.exists()]
    return [s for s in found if kinds is None or s.kind in kinds]


if __name__ == "__main__":
    import collections
    hours = collections.Counter()
    for s in corpus():
        hours[(s.kind, s.cooldowns)] += (s.duration_s or 0)
        print(f"{s.id:<34} {s.kind:<7} {s.creator:<9} cooldowns={s.cooldowns:<7} "
              f"{(s.duration_s or 0)/60:6.1f} min  fps={s.fps}")
    for (kind, regime), seconds in sorted(hours.items()):
        print(f"  {kind:<7} cooldowns={regime:<7} {seconds/60:7.1f} min")
