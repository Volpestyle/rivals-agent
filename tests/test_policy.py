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
def test_a_masked_frame_and_a_cache_miss_are_different_facts():
    """Finding 2: blank video must not be able to pass as a hidden scene."""
    from policy.train import layout
    at = layout(384)
    assert at["emb_present"] != at["scene_masked"], "one bit cannot say both"


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
