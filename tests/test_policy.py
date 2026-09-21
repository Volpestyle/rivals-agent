"""The policy lane's offline checks: provenance, the recorded normalization, and the cache.

Stdlib-only tests run in the default suite. The ones that need numpy/mlx/ffmpeg or recorded
media are skipped there and run under `uv run --group policy pytest tests/test_policy.py`.
"""
import dataclasses
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from policy import corpus as corpus_mod  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = sorted((ROOT / "data" / "demos" / "samples").glob("*.mp4"))


def _has(module):
    try:
        __import__(module)
        return True
    except ImportError:
        return False


needs_numpy = pytest.mark.skipif(not _has("numpy"), reason="numpy: the policy group")
needs_mlx = pytest.mark.skipif(not (_has("mlx") and _has("mlxim")), reason="mlx and mlx-image: the policy group")
needs_data = pytest.mark.skipif(not (ROOT / "data" / "l1" / "tagrun0" / "frames.jsonl").exists(),
                                reason="recorded runs are not on this machine")


# --- provenance: the regime is never guessed --------------------------------------------

def test_a_run_that_nobody_recorded_a_regime_for_is_unknown_not_assumed(tmp_path):
    (tmp_path / "l1" / "newrun").mkdir(parents=True)
    (tmp_path / "l1" / "newrun" / "frames.jsonl").write_text('{"t": 0.0, "file": "000000.jpg"}\n')
    found = corpus_mod.runs(tmp_path)
    assert [s.cooldowns for s in found] == [corpus_mod.UNKNOWN]


def test_our_recordings_from_before_the_baseline_are_the_cooldown_free_regime(tmp_path):
    for name in ("tagrun", "tagrun0", "tagrun1"):
        (tmp_path / "l1" / name).mkdir(parents=True)
        (tmp_path / "l1" / name / "frames.jsonl").write_text('{"t": 0.0, "file": "000000.jpg"}\n')
    assert {s.cooldowns for s in corpus_mod.runs(tmp_path)} == {corpus_mod.OFF}


def test_guides_never_claim_a_regime_and_match_footage_says_what_its_claim_rests_on():
    sources = corpus_mod.corpus()
    if not sources:
        pytest.skip("no media on this machine")
    for s in sources:
        if s.kind == "guide":
            assert s.cooldowns == corpus_mod.UNKNOWN
        assert s.cooldowns_evidence, f"{s.id} states a regime with no evidence"


def test_a_full_youtube_upload_is_marked_edited_and_kept_out_of_every_split():
    """An upload id is not an independent session: they are edited and may overlap the Twitch cuts."""
    uploads = [s for s in corpus_mod.corpus() if s.kind == "upload"]
    if not uploads:
        pytest.skip("no YouTube uploads on this machine")
    for s in uploads:
        assert s.edited and not s.splittable and s.upload_date


@needs_mlx
def test_the_trainer_refuses_a_source_that_is_not_cleared_for_splitting(monkeypatch):
    import policy.train as train
    cleared = [s for s in corpus_mod.corpus(kinds=("run",)) if s.splittable]
    monkeypatch.setattr(corpus_mod, "corpus", lambda *a, **k: [dataclasses.replace(s, splittable=False)
                                                               for s in cleared])
    monkeypatch.setattr(train.corpus_mod, "corpus", corpus_mod.corpus)
    with pytest.raises(ValueError, match="splittable"):
        train.windows(regime="off", recorder=None)


def test_every_source_carries_a_split_group_so_nothing_is_split_within_a_recording():
    for s in corpus_mod.corpus():
        assert s.group and (s.kind == "run" or ":" in s.group)


# --- the recorded normalization ---------------------------------------------------------

@needs_numpy
def test_the_hud_band_and_each_creators_permanent_graphics_are_painted_out():
    import numpy as np

    from policy.frames import FILL, SIZE, mask
    for creator in ("us", "reqmr", "daymr"):
        painted = mask(np.zeros((1, SIZE, SIZE, 3), np.uint8), creator)
        assert (painted[0, int(0.93 * SIZE), SIZE // 2] == FILL).all(), "the bottom HUD band is not masked"
        assert (painted[0, int(0.05 * SIZE), int(0.1 * SIZE)] == FILL).all(), "the objective banner is not masked"
        assert (painted[0, SIZE // 2, SIZE // 2] == 0).all(), "the middle of the scene was painted over"
    day = mask(np.zeros((1, SIZE, SIZE, 3), np.uint8), "daymr")
    req = mask(np.zeros((1, SIZE, SIZE, 3), np.uint8), "reqmr")
    assert (day[0, int(0.75 * SIZE), int(0.66 * SIZE)] == FILL).all(), "DayMR's avatar is not masked"
    assert (req[0, int(0.75 * SIZE), int(0.66 * SIZE)] == 0).all(), "Req is masked where only DayMR has a graphic"


@needs_numpy
def test_an_unknown_creator_gets_the_game_chrome_and_nothing_invented():
    from policy.frames import DEFAULT_OVERLAYS, GAME_CHROME, rects
    assert rects("nobody") == GAME_CHROME + DEFAULT_OVERLAYS


@needs_numpy
def test_the_mask_leaves_most_of_the_scene_and_the_sidecar_can_say_how_much():
    from policy.frames import visible_fraction
    for creator in ("us", "reqmr", "daymr"):
        assert 0.55 < visible_fraction(creator) < 0.85, creator


# --- decoding: a row is never given a time that is not its own ---------------------------

@needs_numpy
@pytest.mark.skipif(not SAMPLES, reason="no sample clip on this machine")
def test_decoded_timestamps_come_from_the_media_not_from_a_nominal_grid():
    import numpy as np

    from policy.frames import Decoded
    decoded = Decoded(SAMPLES[0], "reqmr", hz=5, src_fps=60, batch=16)
    frames = sum(len(b) for b in decoded)
    times = decoded.check()
    assert len(times) == frames > 10
    assert (np.diff(times) > 0).all(), "timestamps must increase"


@needs_numpy
def test_a_frame_count_that_disagrees_with_the_timestamps_is_refused():
    from policy.frames import Decoded
    decoded = Decoded("nowhere.mp4", "us", hz=10, src_fps=60)
    decoded.frames, decoded.times = 5, [0.0, 0.1]
    with pytest.raises(ValueError, match="time that is not its own"):
        decoded.check()


@needs_numpy
def test_jpgs_are_refused_when_the_index_does_not_name_exactly_what_is_on_disk(tmp_path):
    from policy.frames import DecodedJpegs
    for name in ("000000.jpg", "000001.jpg"):
        (tmp_path / name).write_bytes(b"")
    with pytest.raises(ValueError, match="row i would not be frame i"):
        DecodedJpegs(tmp_path, ["000000.jpg"], "us")


# --- the cache --------------------------------------------------------------------------

@needs_numpy
def test_thinning_a_run_to_the_cache_rate_never_takes_two_frames_inside_one_period():
    from policy.frames import thin
    times = [i / 30 for i in range(60)]
    keep = thin(times, 10)
    gaps = [times[b] - times[a] for a, b in zip(keep, keep[1:])]
    assert all(g >= 1 / 10 - 1e-9 for g in gaps) and len(keep) >= 19


@needs_mlx
@needs_data
def test_a_cached_source_is_skipped_and_its_sidecar_says_what_the_pixels_went_through(tmp_path):
    from policy.encode import Encoder, cache_dir, encode_source
    from policy.frames import NORM
    source = next(s for s in corpus_mod.corpus(kinds=("run",)) if s.id == "run:tagrun1")
    encoder = Encoder(batch=32)
    out = tmp_path / cache_dir(encoder, 10.0).name
    out.mkdir(parents=True)
    written = encode_source(source, encoder, 10.0, out)
    assert written and written[0] > 0
    assert encode_source(source, encoder, 10.0, out) is None, "a cached source must not be encoded twice"
    meta = json.loads((out / "run-tagrun1.json").read_text())
    assert meta["cooldowns"] == "off" and meta["norm"] == NORM and meta["encoder"] == encoder.name
    assert meta["masks"] and meta["frames"] == written[0]


@needs_mlx
@needs_data
def test_the_cache_holds_one_embedding_per_timestamp_and_nothing_later_is_implied(tmp_path):
    import numpy as np

    from policy.encode import Encoder, encode_source, load
    source = next(s for s in corpus_mod.corpus(kinds=("run",)) if s.id == "run:tagrun1")
    encoder = Encoder(batch=32)
    encode_source(source, encoder, 10.0, tmp_path)
    (meta, emb, t), = load(tmp_path)
    assert emb.shape == (meta["frames"], meta["dim"]) and len(t) == len(emb)
    assert emb.dtype == np.float16 and (np.diff(t) > 0).all()


@needs_mlx
def test_an_interrupted_write_leaves_no_file_that_looks_complete(tmp_path):
    """Both files land by rename, so a crash between them can only leave a .tmp."""
    import policy.encode as enc
    assert "tmp_npz.rename(npz)" in Path(enc.__file__).read_text()
    assert not list(tmp_path.glob("*.npz"))


def test_only_one_opencv_distribution_is_ever_installed():
    """opencv-python and opencv-python-headless both provide cv2; installed together, cv2 breaks.

    mlx-image depends on opencv-python, which is why the policy group once broke `import cv2`
    for every perception lane. The override in pyproject.toml drops it; this fails if it comes back.
    """
    import importlib.metadata as md
    providers = sorted({d.metadata["Name"] for d in md.distributions()
                        if (d.metadata["Name"] or "").lower().startswith("opencv")})
    assert len(providers) <= 1, f"two cv2 providers in one environment: {providers}"
    if _has("cv2"):
        import cv2
        assert cv2.__version__


def test_the_dependency_overrides_are_what_keep_the_project_on_numpy_2_and_one_cv2():
    """mlx-image pins numpy==1.26.2 and pulls opencv-python; both would break the perception group."""
    text = (ROOT / "pyproject.toml").read_text()
    assert "override-dependencies" in text and "numpy>=2.0" in text
    assert "opencv-python; sys_platform == 'never'" in text, "the transitive opencv-python must stay dropped"
    if _has("numpy"):
        import numpy
        assert int(numpy.__version__.split(".")[0]) >= 2


def test_third_party_derived_data_stays_out_of_git():
    ignored = subprocess.run(["git", "check-ignore", "data/embeddings", "data/demos"],
                             cwd=ROOT, capture_output=True, text=True)
    assert "data/embeddings" in ignored.stdout and "data/demos" in ignored.stdout


# --- step 2: the temporal head ------------------------------------------------------------

@needs_mlx
def test_a_missing_modality_is_zero_with_its_bit_clear_never_filled():
    import numpy as np

    from policy.train import _event_features, _state_features
    feat, present = _state_features(None)
    assert not present and not feat.any()
    feat, present = _event_features(None, 10.0)
    assert not present and not feat.any()


@needs_mlx
def test_an_unknown_state_field_never_reads_as_a_value():
    """hp unknown must not arrive as 0.0 hp: the value is zero and its known-bit is clear."""
    from policy.train import _state_features
    feat, present = _state_features({"hp": None, "max_hp": 250, "webs": None, "abilities": {}, "detections": None})
    assert present, "the State itself was there"
    assert feat[0] == 0.0 and feat[1] == 0.0, "hp unknown must leave its known-bit clear"
    assert feat[3] == 0.0 and feat[12] == 0.0


@needs_mlx
def test_the_two_recorders_notes_map_to_one_vocabulary_without_inventing_equivalences():
    from policy.train import vocab_of
    assert vocab_of("engage:enemy") == vocab_of("Engage") == "engage"
    assert vocab_of("combo:burst") == "combo"
    assert vocab_of("stand") != vocab_of("idle"), "a scripted pause and a stood-down loop are not the same label"


@needs_mlx
@pytest.mark.skipif(not SAMPLES, reason="no sample clip on this machine")
def test_the_live_path_reproduces_the_cached_embedding_for_the_same_frame():
    """Train/serve skew: the cache decodes with ffmpeg, the loop resizes with cv2.

    If the two normalizations disagreed, the head would be fed vectors unlike the ones it was
    trained on and nothing downstream would say so.
    """
    cv2 = pytest.importorskip("cv2")
    import numpy as np

    from policy.encode import Encoder
    from policy.frames import SIZE, Decoded, mask
    decoded = Decoded(SAMPLES[0], "us", hz=1, src_fps=60, batch=1)
    cached_pixels = next(iter(decoded))[0]                     # ffmpeg: scale then mask

    raw = subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-i", str(SAMPLES[0]),
                          "-frames:v", "1", "-pix_fmt", "bgr24", "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    native = np.frombuffer(raw, np.uint8).reshape(1080, 1920, 3)
    live_pixels = mask(cv2.cvtColor(cv2.resize(native, (SIZE, SIZE), interpolation=cv2.INTER_AREA),
                                    cv2.COLOR_BGR2RGB)[None, ...].copy(), "us")

    encoder = Encoder(batch=1)
    a, b = encoder(cached_pixels[None, ...]).astype(np.float32)[0], encoder(live_pixels).astype(np.float32)[0]
    cosine = float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))
    assert cosine > 0.99, f"live and cached embeddings disagree (cosine {cosine:.4f}): the head would be fed skewed input"


@needs_mlx
@needs_data
def test_the_sticky_guess_is_what_was_already_in_force_and_never_the_answer():
    """`prev` must come from an input at or before t, so it is available at decision time."""
    from policy.train import windows
    x, y, sessions, prev, classes = windows(regime="normal", decision_hz=1.0)
    assert len(prev) == len(y)
    assert (prev == y).mean() > 0.5, "intents are sticky: the previous one should usually still hold"
    assert (prev == y).mean() < 1.0, "if it always matched, the label would be the observation"


@needs_mlx
def test_l4s_trial_logs_are_a_different_recorder_and_are_not_pooled_with_the_loops_runs():
    runs = {s.id: s.recorder for s in corpus_mod.corpus(kinds=("run",))}
    if not runs:
        pytest.skip("no runs on this machine")
    assert all(r in ("loop", "trial") for r in runs.values())
    assert runs.get("run:tagrun0", "trial") == "trial"


@needs_mlx
def test_the_learned_brain_runs_the_scripted_gate_first_and_never_adopts_an_illegal_intent():
    """The gate and the kit checks are imported from brain/jev, not reimplemented here."""
    import inspect

    import policy.live as live
    source = inspect.getsource(live.LearnedBrain.__call__)
    assert "brain.gate(state, memory)" in source, "the scripted gate must run before the head"
    assert "jev.legal(" in source and "jev.adopt(" in source, "legality and adoption are jev's, reused"
    assert live.TO_JEV["combo"] == "burst" and live.TO_JEV["webstrike"] == "web_strike"


@needs_mlx
def test_the_runtime_and_the_trainer_read_one_feature_layout():
    """The live path once derived the offsets itself and fed the head a vector a column out."""
    from policy.train import EVENT_F, STATE_F, emb_dim_of, layout
    at = layout(384)
    assert at["emb_present"] == 384 and at["scene_masked"] == 385
    assert at["state"] == 386 and at["state_present"] == 386 + STATE_F
    assert at["events_present"] == at["events"] + EVENT_F
    assert emb_dim_of(at["width"]) == 384




@needs_mlx
def test_the_transition_weight_on_the_command_line_reaches_the_trainer(monkeypatch):
    """It once did not: a weighted run recorded weight 1.0 and matched the unweighted one exactly."""
    import policy.train as train
    seen = {}

    def spy(regime, mode, transition_weight=1.0, k=3, **kw):
        seen.update(transition_weight=transition_weight, k=k)
        return {}, []
    monkeypatch.setattr(train, "leave_one_session_out", spy)
    train.main(["--regime", "normal", "--transition-weight", "8", "--k", "5"])
    assert seen == {"transition_weight": 8.0, "k": 5}


@needs_mlx
def test_near_change_marks_only_windows_whose_label_changes_ahead_in_the_same_session():
    import numpy as np

    from policy.train import near_change
    y = np.array([0, 0, 0, 1, 1, 2, 2])
    sessions = np.array(["a", "a", "a", "a", "b", "b", "b"])
    flag = near_change(y, sessions, k=1)
    assert flag.tolist() == [False, False, True, False, True, False, False], \
        "a change must be seen only inside its own session, never across the boundary"


# --- review re-check (VUH-1326): Cache.at, masks, and the regression tests that never landed ----------

def _cache():
    from policy.encode import DEFAULT, cache_dir
    from policy.train import Cache, _Tag
    return Cache(cache_dir(_Tag(DEFAULT), 10.0))


def _probes(times):
    """On the grid and between it, at the start, middle and end of a source."""
    picks = [0, 1, len(times) // 2, len(times) - 2, len(times) - 1]
    out = []
    for i in picks:
        out += [times[i], times[i] + 0.001, times[i] + 0.027, times[i] + 0.05, times[i] + 0.099]
    return out


@needs_mlx
@needs_data
def test_every_cached_source_resolves_at_or_before_and_within_one_step():
    """Finding 1 lived in a gap no test covered: argmin(|t - times|) returned a frame 27 ms AFTER t.

    On every real cached source, video and run, on and between the grid: the resolved row's time
    is at or before the moment asked for, and no staler than one step plus jitter (MATCH_S).
    """
    from policy.train import MATCH_S
    cache = _cache()
    checked = 0
    for clip, (times, _) in cache.by_clip.items():
        if len(times) < 5:
            continue
        for want in _probes(times):
            i = cache.index_at(clip, want)
            assert i is not None, f"{clip}: {want:.3f} lies inside the clip and must resolve"
            assert times[i] <= want + 1e-9, f"{clip}: asked {want:.3f}, got a frame at {times[i]:.3f}, AFTER it"
            assert want - times[i] <= MATCH_S, f"{clip}: asked {want:.3f}, got {times[i]:.3f}, staler than a step"
            checked += 1
    assert checked > 100, f"only {checked} lookups exercised"


@needs_mlx
@needs_data
def test_the_source_whose_origin_is_not_zero_resolves_on_the_loaders_clock():
    """The reviewer's reproduction: on daymr-2879354299-21660-900s every decoded PTS is grid + 27 ms,
    and at(src, 30.0) returned the 30.027 s frame. Rebased by t_origin it must resolve to +0 ms."""
    import json

    from policy.encode import DEFAULT, cache_dir
    from policy.train import _Tag
    out = cache_dir(_Tag(DEFAULT), 10.0)
    side = out / "daymr-2879354299-21660-900s.json"
    if not side.exists():
        pytest.skip("that section is not cached on this machine")
    meta = json.loads(side.read_text())
    assert meta["clock"] == "media_pts" and meta["t_origin"] > 0.02, "the reproduction needs its nonzero origin"
    cache = _cache()
    times, _ = cache.by_clip[meta["id"]]
    i = cache.index_at(meta["id"], 30.0)
    assert i is not None, "an offset origin must not make every lookup miss"
    assert abs(times[i] - 30.0) < 1e-6, f"30.0 must resolve to the frame AT 30.0, got {times[i]:.4f}"
    assert cache.index_at(meta["id"], 29.999) == i - 1, "just before a frame must give the one before it"


@needs_mlx
@needs_data
def test_a_time_past_the_clip_or_before_its_first_frame_misses():
    cache = _cache()
    for clip, (times, _) in list(cache.by_clip.items())[:8]:
        assert cache.index_at(clip, times[-1] + 1.0) is None, f"{clip}: 1 s past the last frame must miss"
        assert cache.index_at(clip, times[0] - 0.05) is None, f"{clip}: before the first frame must miss"
        assert cache.at("not-a-cached-clip", times[0]) is None


@needs_mlx
@needs_data
def test_a_window_is_built_only_from_frames_at_or_before_its_decision():
    """Restored for real: the resolution chain windows() uses, checked by timestamps.

    Every frame the loader puts in an observation is at or before the decision, and the cache row it
    resolves to is at or before that frame and within one step of it.
    """
    from agent.demos import Demos
    from policy.train import FRAME_HZ, HISTORY_S, MATCH_S, TRAINABLE
    runs = [s for s in corpus_mod.corpus(kinds=("run",)) if s.cooldowns == "normal"
            and s.cooldowns_source == "metadata"][:2]
    if not runs:
        pytest.skip("no normal-regime run with its own metadata on this machine")
    cache, demos = _cache(), Demos.load(*[str(s.path) for s in runs])
    checked = 0
    for split in TRAINABLE:
        if split not in set(demos.splits.values()):
            continue
        for sample in demos.samples(split, history_s=HISTORY_S, frame_hz=FRAME_HZ, hz=1.0, label_s=0.5,
                                    cooldowns="normal"):
            obs = sample.observation
            times = cache.by_clip[obs.clip][0]
            for frame in obs.frames:
                assert frame.t <= obs.t + 1e-9, f"{obs.clip}: a frame at {frame.t} inside a window decided at {obs.t}"
                i = cache.index_at(obs.clip, frame.t)
                if i is None:
                    continue
                assert times[i] <= frame.t + 1e-9, f"{obs.clip}: frame {frame.t} resolved to a later row {times[i]}"
                assert frame.t - times[i] <= MATCH_S
                checked += 1
    assert checked > 500, f"only {checked} frame lookups exercised"


@needs_mlx
def test_a_mask_hiding_one_hud_slot_keeps_the_scene_and_drops_only_that_slot():
    """The reviewer's reproduction for finding C: a mask hiding ONE HUD slot threw away the whole
    384-d embedding of a frame whose scene was fully visible, and told the head the scene was hidden."""
    import numpy as np

    from agent.demos import Mask
    from policy.train import STATE_COLS, layout, step_row
    at = layout(384)
    vec = np.full(384, 0.5, np.float32)
    state = {"hp": 200, "max_hp": 250, "webs": 4,
             "abilities": {"swing": {"ready": True}, "pull": {"ready": True}, "uppercut": {"ready": False}}}
    mask = Mask(reasons=("chat", "partial_chat_overlay"), hidden=("swing",))
    row, has_emb, scene_hidden = step_row(384, vec, mask, state, None, 10.0)
    assert has_emb and not scene_hidden, "a hidden slot is not a hidden scene"
    assert row[at["emb_present"]] == 1.0 and row[at["scene_masked"]] == 0.0
    assert (row[:384] == 0.5).all(), "the scene's embedding must survive"
    s = at["state"]
    for c in STATE_COLS["swing"]:
        assert row[s + c] == 0.0, "the hidden slot's value and known-bit are both cleared"
    assert row[s + STATE_COLS["pull"][1]] == 1.0, "an unhidden slot keeps its known-bit"
    assert row[s + STATE_COLS["hp"][1]] == 1.0 and row[s + STATE_COLS["ammo"][1]] == 1.0


@needs_mlx
def test_a_mask_hiding_the_scene_drops_the_embedding_and_scene_derived_state():
    import numpy as np

    from agent.demos import Mask
    from policy.train import SCENE_DERIVED, STATE_COLS, layout, step_row
    at = layout(384)
    state = {"hp": 200, "max_hp": 250, "detections": [{}], "on_target": True, "abilities": {}}
    row, has_emb, scene_hidden = step_row(384, np.ones(384, np.float32), Mask(reasons=("scoreboard",),
                                                                              hidden=("scene",)), state, None, 1.0)
    assert scene_hidden and not has_emb
    assert row[at["scene_masked"]] == 1.0 and row[at["emb_present"]] == 0.0 and not row[:384].any()
    for c in SCENE_DERIVED:
        assert row[at["state"] + c] == 0.0, "detections and crosshair come from the hidden pixels"
    assert row[at["state"] + STATE_COLS["hp"][1]] == 1.0, "hiding the scene alone leaves the HUD readable"


@needs_mlx
def test_a_mask_hiding_the_whole_hud_drops_every_hud_field_but_not_the_scene():
    import numpy as np

    from agent.demos import Mask
    from policy.train import HUD_FIELDS, STATE_COLS, layout, step_row
    at = layout(384)
    state = {"hp": 200, "max_hp": 250, "webs": 4, "on_target": True,
             "abilities": {"swing": {"ready": True}, "pull": {"ready": True}, "uppercut": {"ready": True}}}
    row, has_emb, scene_hidden = step_row(384, np.ones(384, np.float32), Mask(reasons=("x",), hidden=("hud",)),
                                          state, None, 1.0)
    assert has_emb and not scene_hidden
    for field in HUD_FIELDS:
        for c in STATE_COLS[field]:
            assert row[at["state"] + c] == 0.0, f"{field} survived a hidden HUD"
    assert row[at["state"] + 12] == 1.0, "the crosshair reading is scene-derived and stays"


@needs_mlx
def test_a_masked_frame_and_a_cache_miss_are_different_facts():
    """Finding 2, by behaviour: a hidden scene is accounted for; a miss is neither present nor masked."""
    from agent.demos import Mask
    from policy.train import layout, step_row
    at = layout(384)
    masked, has_emb, scene_hidden = step_row(384, None, Mask(reasons=("scoreboard",), hidden=("hud", "scene")),
                                             None, None, 1.0)
    assert scene_hidden and not has_emb and masked[at["scene_masked"]] == 1.0
    miss, has_emb, scene_hidden = step_row(384, None, None, None, None, 1.0)
    assert not scene_hidden and not has_emb
    assert miss[at["scene_masked"]] == 0.0 and miss[at["emb_present"]] == 0.0, "a miss must not look masked"


# --- the five regression tests the earlier batch claimed and never wrote ----------------------------

@needs_mlx
def test_a_source_that_was_never_encoded_fails_the_run_instead_of_training_on_blank_video():
    """A reviewer found a whole held-out fold of 1,500 windows with embedding-present 0.000."""
    import policy.train as train
    real = [s for s in corpus_mod.corpus(kinds=("run",)) if s.cooldowns == "normal" and s.cooldowns_source == "metadata"]
    if not real:
        pytest.skip("no normal-regime run on this machine")
    # The realistic case: the cache exists and holds other runs, but not this one (baseline3 then).
    ghost = dataclasses.replace(real[0], id="run:never-encoded")
    with pytest.raises(train.CacheMiss, match="not in the embedding cache: run:never-encoded"):
        _windows_with(train, real + [ghost])
    with pytest.raises(train.CacheMiss, match="nothing cached"):
        train.windows(regime="normal", encoder="a-model-nobody-cached")


def _windows_with(train, sources):
    """windows() over exactly these sources."""
    import unittest.mock as mock
    with mock.patch.object(train.corpus_mod, "corpus", lambda *a, **k: sources):
        return train.windows(regime="normal")


@needs_mlx
def test_inspection_only_can_never_yield_a_training_row():
    import policy.train as train
    assert train.TRAINABLE == ("train", "val", "test"), "an allow-list, not a deny-list"


@needs_mlx
def test_an_event_is_counted_only_once_the_step_itself_could_know_it():
    """A reviewer found no upper bound: an early step counted events confirmed seconds later."""
    from agent.demos import Event
    from policy.train import _event_features
    later = Event(kind="hp_lost", t_from=9.0, t_to=10.0, amount=1)
    feat, present = _event_features([later], t=6.0)
    assert present and not feat.any(), "a step at t=6 must not see an event confirmed at t=10"
    feat, _ = _event_features([later], t=10.0)
    assert feat.any(), "the step that can know it must count it"
    feat, _ = _event_features([later], t=11.5)
    assert not feat.any(), "and it leaves the one-second window again"


def test_the_runs_own_metadata_outranks_the_legacy_name_table(tmp_path):
    (tmp_path / "l1" / "tagrun0").mkdir(parents=True)
    (tmp_path / "l1" / "tagrun0" / "frames.jsonl").write_text('{"t": 0.0, "file": "000000.jpg"}\n')
    (tmp_path / "l1" / "tagrun0" / "meta.json").write_text(json.dumps({"cooldowns": "off", "brain": "scripted"}))
    source, = corpus_mod.runs(tmp_path)
    assert source.cooldowns == "off" and source.cooldowns_source == "metadata"


def test_metadata_and_the_legacy_table_disagreeing_is_an_error(tmp_path):
    (tmp_path / "l1" / "tagrun0").mkdir(parents=True)
    (tmp_path / "l1" / "tagrun0" / "frames.jsonl").write_text('{"t": 0.0, "file": "000000.jpg"}\n')
    (tmp_path / "l1" / "tagrun0" / "meta.json").write_text(json.dumps({"cooldowns": "normal"}))
    with pytest.raises(corpus_mod.RegimeConflict):
        corpus_mod.runs(tmp_path)
