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
import re
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
KIT = ROOT / "docs" / "spiderman-kit.md"

OFF, NORMAL, UNKNOWN = "off", "normal", "unknown"


class RegimeConflict(ValueError):
    """A run's own metadata and the legacy fallback table disagree about its resource regime."""

# Balance patches change Spider-Man's cooldowns, damage and mechanics every few weeks (VUH-1324),
# so the patch is a recorded fact beside the regime, and training stays inside one patch.
# docs/spiderman-kit.md is the single place the current patch is stated; it is read, never copied.
_PATCH = re.compile(r"\*\*Patch reflected:\s*(.+?)\s*\(.*?live\s*(\d{4}-\d{2}-\d{2})\)")


def current_patch(kit=KIT):
    """(name, live date) as docs/spiderman-kit.md states it, or (UNKNOWN, None) if it does not."""
    found = _PATCH.search(kit.read_text()) if kit.exists() else None
    return (found.group(1), found.group(2)) if found else (UNKNOWN, None)


def patch_on(date, kit=KIT):
    """(patch, evidence) for a source recorded or uploaded on `date` (YYYYMMDD or YYYY-MM-DD).

    A source from on or after the stated patch's live date is that patch. One from before it is
    `unknown`: older patches are not enumerated here, and the kit says only which one is current.
    """
    name, live = current_patch(kit)
    if not date or live is None:
        return UNKNOWN, "no date recorded for this source" if not date else "docs/spiderman-kit.md states no patch"
    iso = date if "-" in date else f"{date[:4]}-{date[4:6]}-{date[6:8]}"
    if iso >= live:
        return name, f"dated {iso}, on or after the {live} live date docs/spiderman-kit.md states"
    return UNKNOWN, f"dated {iso}, before the {live} live date of the only patch docs/spiderman-kit.md states"

# **The run's own metadata is the authority on its regime.** This name-keyed table is a
# documented fallback for legacy runs recorded before the loop wrote `cooldowns` into meta.json,
# and nothing else: a run whose metadata states a regime uses that, a run listed here and stating
# a DIFFERENT one is an error (RegimeConflict), and `cooldowns_source` says which spoke. Training
# takes only runs whose own metadata states it, so the fallback never quietly feeds a model.
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
    kind: str          # run | sample | vod | guide | upload
    path: Path         # the media: a run directory, or an mp4
    creator: str       # us | reqmr | daymr | day | req | matchuxd | ...
    group: str         # split unit: whole VOD / whole session. Never split within one
    cooldowns: str     # off | normal | unknown
    cooldowns_evidence: str
    patch: str = UNKNOWN          # the balance patch in force; never mixed with another in training
    patch_evidence: str = ""
    cooldowns_source: str = "none"   # metadata (the run's own) | fallback_table | derived | none
    fps: float | None = None
    duration_s: float | None = None
    index: Path | None = None   # a run's frames.jsonl
    recorder: str = "trial"     # loop: agent/loop.py (intents.py vocabulary). trial: scripts/l4_trial.py's own four symbols
    proxy: Path | None = None   # a run's proxy video: video frame k is its k-th saved frame, in order
    upload_date: str | None = None
    edited: bool = False        # an edited upload: cuts across maps, black openings, outros, spectated heroes
    splittable: bool = True     # False until something establishes it is not a duplicate of another source

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
        listed = RUNS.get(name)
        stated = (json.loads(meta.read_text()) or {}).get("cooldowns") if meta.exists() else None
        if stated and listed and listed[0] != stated:
            raise RegimeConflict(f"{name}: meta.json says cooldowns={stated!r} but corpus.RUNS says {listed[0]!r}; "
                                 "the run's own metadata is the authority, so remove or correct the table entry")
        if stated:
            regime, evidence, whose = stated, "stated by the recorder in meta.json", "metadata"
        elif listed:
            regime, evidence, whose = listed[0], listed[1] + " (corpus.RUNS fallback, not the run's own metadata)", "fallback_table"
        else:
            regime, evidence, whose = UNKNOWN, "not listed in corpus.RUNS and the recorder stated none", "none"
        # Newer runs ship a 720p proxy video instead of the jpgs: one video frame per logged frame.
        written = json.loads(meta.read_text()) if meta.exists() else {}
        proxy = (written.get("proxy") or {}).get("file")
        # Only the live loop writes a `brain` into meta.json; L4's trial logs carry their own
        # four-symbol vocabulary and are a different recorder, never pooled with the loop's runs.
        recorder = "loop" if written.get("brain") else "trial"
        # The patch, like the regime: the recorder's word when it states one, else the day the
        # recording was written, which is a fact about the file rather than an assumption.
        if written.get("patch"):
            patch, patch_why = written["patch"], "stated by the recorder in meta.json"
        else:
            recorded = time.strftime("%Y-%m-%d", time.localtime(index.stat().st_mtime))
            patch, patch_why = patch_on(recorded)
            patch_why += "; the recorder stated no patch, so this is frames.jsonl's own mtime"
        out.append(Source(id=f"run:{name}", kind="run", path=index.parent, creator="us",
                          group=f"run:{name}", cooldowns=regime, cooldowns_evidence=evidence, index=index,
                          proxy=(index.parent / proxy) if proxy else None, recorder=recorder,
                          patch=patch, patch_evidence=patch_why, cooldowns_source=whose))
    return out


def demos(data=DATA):
    """Expert footage from the acquisition lanes' manifests: samples, vods, guides."""
    out = []
    samples = data / "demos" / "samples" / "manifest.json"
    if samples.exists():
        for e in json.loads(samples.read_text()):
            fps, duration = _probe(e)
            clip = samples.parent / e["clip"]
            patch, patch_why = patch_on(e.get("retrieved"))
            out.append(Source(id=clip.stem, kind="sample", path=clip, creator=e["creator"].lower(),
                              group=f"twitch:{e['vod_id']}", cooldowns=NORMAL, cooldowns_evidence=VOD_EVIDENCE,
                              fps=fps, duration_s=duration, patch=patch, patch_evidence=patch_why,
                              cooldowns_source="derived"))
    vods = data / "demos" / "vods" / "manifest.json"
    if vods.exists():
        for e in json.loads(vods.read_text()):
            fps, duration = _probe(e)
            patch, patch_why = patch_on(e.get("upload_date") or e.get("retrieved"))
            out.append(Source(id=e["id"], kind="vod", path=vods.parent / e["media"], creator=e["creator"].lower(),
                              group=e.get("group") or f"twitch:{e['vod_id']}", cooldowns=NORMAL,
                              cooldowns_evidence=VOD_EVIDENCE, fps=fps, duration_s=duration,
                              patch=patch, patch_evidence=patch_why, cooldowns_source="derived"))
    # Full YouTube uploads. An upload id is NOT an independent session: these are edited (cuts
    # across maps, black openings, outros, scoreboards, spectated heroes), the September ones may
    # overlap the retained Twitch sections, and the April-May ones predate several balance
    # patches. Embedding them is cheap and fine; `splittable=False` keeps every one of them out of
    # any train/val/test split until cross-source deduplication has run.
    uploads = data / "demos" / "youtube"
    for manifest in sorted(uploads.glob("*/manifest.json")) if uploads.exists() else []:
        for e in json.loads(manifest.read_text()):
            fps, duration = _probe(e)
            patch, patch_why = patch_on(e.get("upload_date"))
            out.append(Source(id=e["id"], kind="upload", path=manifest.parent / e["media"],
                              creator=e["creator"].lower(), group=f"youtube:{e['id']}", cooldowns=NORMAL,
                              cooldowns_evidence=VOD_EVIDENCE, fps=fps, duration_s=duration,
                              upload_date=e.get("upload_date"), edited=True, splittable=False,
                              patch=patch, patch_evidence=patch_why, cooldowns_source="derived"))
    guides = data / "demos" / "guides" / "manifest.json"
    if guides.exists():
        for e in json.loads(guides.read_text()):
            fps, duration = _probe(e)
            patch, patch_why = patch_on(e.get("upload_date"))
            out.append(Source(id=e["id"], kind="guide", path=guides.parent / e["media"], creator=e["creator"].lower(),
                              group=f"guide:{e['id']}", cooldowns=UNKNOWN, cooldowns_evidence=GUIDE_EVIDENCE,
                              fps=fps, duration_s=duration, patch=patch, patch_evidence=patch_why,
                              cooldowns_source="derived"))
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
