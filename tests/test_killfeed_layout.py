"""New layout classifier: synthetic controls and DEVELOPMENT-grade crop composites.

No corpus/validation decode. The competitive regression is deliberately a
counterfactual composite, NOT an inspected competitive frame or accuracy result.
"""
from dataclasses import replace
from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

from perception import killfeed_layout as K
from perception import match_timer as M

ROOT = Path(__file__).resolve().parent.parent
DEV = ROOT / "docs/evidence/gate2-revalidation-20260926/code/fixtures_gate2_readers"


def crop(name):
    image = cv2.imread(str(DEV / name))
    assert image is not None
    return image


def blank():
    return np.zeros((1440, 2560, 3), np.uint8)


def paste(frame, box, pixels):
    x0, y0, x1, y1 = box
    assert pixels.shape == (y1 - y0, x1 - x0, 3)
    frame[y0:y1, x0:x1] = pixels
    return frame


def live(name="kf_live_light.png"):
    frame = paste(blank(), K.LIVE_BOX, crop(name))
    return paste(frame, M.CENTRE.box, crop("centre_white_mmss.png"))


def replay():
    frame = paste(blank(), K.SPECTATOR_BOX, crop("kf_spec_entry.png"))
    return paste(frame, K.PROMPT_BOX, crop("prompt_viewer.png"))


def checked_live(frame):
    # A one-frame synthetic recording, not a native match-coverage claim.
    guard = K.inspect_match([(0, frame)], source_id="synthetic", start=0, stop=1)
    return K.recognise_layout(frame, match_evidence=guard, source_id="synthetic", frame_index=0)


@pytest.mark.parametrize("name", ["kf_live_light.png", "kf_live_dark.png"])
def test_live_requires_positive_development_feed_and_timer(name):
    decision = checked_live(live(name))
    assert decision.layout == "live_quick_match"
    assert decision.live_score >= K.POSITIVE_NCC and decision.centre_timer


def test_spectator_requires_both_positive_cues_without_requiring_team_clock():
    decision = K.recognise_layout(replay())
    assert decision.layout == "replay_spectator"
    assert not decision.team_clock


def test_spectator_with_a_team_clock_still_needs_positive_replay_cues():
    frame = paste(replay(), M.TEAM_B.box, crop("team_b.png"))
    decision = K.recognise_layout(frame)
    assert decision.layout == "replay_spectator" and decision.team_clock


@pytest.mark.parametrize("channel, name", [(M.TEAM_A, "team_a.png"), (M.TEAM_B, "team_b.png")])
def test_live_competitive_team_clock_failure_is_refused_from_dev_material(channel, name):
    # Actual live QM feed/centre crops + actual DEVELOPMENT spectator clock crop.
    # This models the failure mechanism without reopening 22-48-05 or pretending
    # that a competitive development frame exists.
    frame = paste(live(), channel.box, crop(name))
    assert M.read_frame(frame)[channel.name] is not None
    decision = K.recognise_layout(frame)
    assert decision.layout is None
    assert decision.reason == "competitive_unsupported"
    assert decision.team_clock and decision.live_score >= K.POSITIVE_NCC


def test_clock_alone_and_no_viewer_prompt_never_imply_replay_or_live():
    frame = paste(blank(), M.TEAM_B.box, crop("team_b.png"))
    assert K.recognise_layout(frame).reason == "unsupported_team_clock_layout"
    assert K.recognise_layout(blank()).layout is None


@pytest.mark.parametrize("box,name", [
    (K.LIVE_BOX, "kf_live_light.png"), (K.SPECTATOR_BOX, "kf_spec_entry.png"),
    (K.PROMPT_BOX, "prompt_viewer.png"), (M.CENTRE.box, "centre_white_mmss.png"),
])
def test_single_positive_cue_cannot_choose_a_layout(box, name):
    assert K.recognise_layout(paste(blank(), box, crop(name))).layout is None


def test_conflicting_positive_layouts_abstain():
    frame = live()
    paste(frame, K.SPECTATOR_BOX, crop("kf_spec_entry.png"))
    paste(frame, K.PROMPT_BOX, crop("prompt_viewer.png"))
    assert K.recognise_layout(frame).reason == "conflicting_layout_evidence"


def test_partial_rival_cue_blocks_a_live_decision():
    frame = paste(live(), K.PROMPT_BOX, crop("prompt_viewer.png"))
    assert K.recognise_layout(frame).layout is None


def test_occluded_viewer_prompt_cannot_reuse_a_previous_replay_decision():
    frame = replay()
    assert K.recognise_layout(frame).layout == "replay_spectator"
    x0, y0, x1, y1 = K.PROMPT_BOX
    frame[y0:y1, x0:x1] = 0
    assert K.recognise_layout(frame).layout is None


def test_known_feed_cannot_pass_with_an_illegible_centre_clock():
    frame = paste(live(), M.CENTRE.box, crop("centre_blurred.png"))
    assert not K.recognise_layout(frame).centre_timer
    assert K.recognise_layout(frame).layout is None


def test_real_development_empty_feed_and_live_prompt_do_not_nominate_live():
    frame = paste(blank(), K.LIVE_BOX, crop("kf_live_empty.png"))
    paste(frame, K.PROMPT_BOX, crop("prompt_live.png"))
    paste(frame, M.CENTRE.box, crop("centre_white_mmss.png"))
    assert K.recognise_layout(frame).layout is None
    frame = paste(replay(), K.SPECTATOR_BOX, crop("kf_spec_empty.png"))
    assert K.recognise_layout(frame).layout is None


@pytest.mark.parametrize("value", [0, 64, 255])
def test_flat_or_occluded_frames_abstain(value):
    assert K.recognise_layout(np.full((1440, 2560, 3), value, np.uint8)).layout is None


def test_unfamiliar_textured_frame_and_wrong_geometry_abstain():
    rng = np.random.default_rng(1353)
    frame = rng.integers(0, 256, (1440, 2560, 3), dtype=np.uint8)
    assert K.recognise_layout(frame).layout is None
    frame = live()
    x0, y0, x1, y1 = K.LIVE_BOX
    pixels = frame[y0:y1, x0:x1].copy()
    frame[y0:y1, x0:x1] = 0
    frame[y0 + 80:y1 + 80, x0:x1] = pixels
    assert K.recognise_layout(frame).layout is None


@pytest.mark.parametrize("frame", [None, np.zeros((720, 1280, 3), np.uint8),
                                        np.zeros((1440, 2560), np.uint8),
                                        np.full((1440, 2560, 3), np.nan, np.float32)])
def test_invalid_frame_has_explicit_refusal(frame):
    assert K.recognise_layout(frame).reason == "invalid_native_frame"


def test_missing_or_corrupt_template_refuses_instead_of_using_a_fallback(tmp_path, monkeypatch):
    K._templates.cache_clear()
    monkeypatch.setattr(K, "ASSETS", tmp_path)
    assert K.recognise_layout(live()).reason == "template_unavailable"
    (tmp_path / "kf_live_light.png").write_bytes(b"corrupt")
    assert K.recognise_layout(live()).reason == "template_unavailable"
    K._templates.cache_clear()


def test_interval_never_votes_through_unknown_or_layout_changes():
    frame = live()
    guard = K.inspect_match(enumerate([frame] * 21), source_id="synthetic", start=0, stop=21)
    one = K.recognise_layout(frame, match_evidence=guard, source_id="synthetic", frame_index=0)
    other = K.recognise_layout(replay())

    def interval(decisions):
        return K.consistent_layout(enumerate(decisions), start=0, stop=len(decisions),
                                   match_evidence=guard, source_id="synthetic")

    assert interval([one] * 20).layout == "live_quick_match"
    assert interval([one] * 20 + [K.Decision(None, "occluded")]).layout is None
    assert interval([one, other]).reason == "interval_changes_layout"
    assert interval([]).reason == "invalid_interval_bounds"
    # Unsupported competitive stays closed even if a future caller fabricates it.
    assert interval([replace(one, layout="live_competitive")]).layout is None


def test_another_genuine_entry_does_not_match_a_single_entry_bank(monkeypatch):
    light, dark, spectator, prompt = K._templates()
    # Both genuine entries are in the production bank. Hold dark OUT so this
    # measures cross-entry generalisation rather than its trivial self-match.
    score = K._score(crop("kf_live_dark.png"), light)
    assert -0.2 < score < 0.0  # review measured approximately -0.12
    monkeypatch.setattr(K, "_templates", lambda: (light, light, spectator, prompt))
    assert checked_live(live("kf_live_light.png")).layout == "live_quick_match"
    assert checked_live(live("kf_live_dark.png")).layout is None


@pytest.mark.parametrize("name", ["kf_live_light.png", "kf_live_dark.png"])
@pytest.mark.parametrize("shift", [1, 2])
def test_one_or_two_pixel_shift_of_genuine_entry_refuses(name, shift):
    pixels = crop(name)
    shifted = np.zeros_like(pixels)
    shifted[:, shift:] = pixels[:, :-shift]
    decision = checked_live(paste(live(), K.LIVE_BOX, shifted))
    assert decision.live_score < K.POSITIVE_NCC
    assert decision.layout is None


def test_live_requires_complete_match_guard_and_cannot_borrow_another_source():
    frame = live()
    assert K.recognise_layout(frame).reason == "complete_match_scan_required"
    guard = K.inspect_match([(0, frame)], source_id="first", start=0, stop=1)
    assert K.recognise_layout(frame, match_evidence=guard, source_id="other",
                              frame_index=0).reason == "match_evidence_mismatch"
    assert K.recognise_layout(frame, match_evidence=guard, source_id="first",
                              frame_index=1).reason == "match_evidence_mismatch"


@pytest.mark.parametrize("channel,name", [(M.TEAM_A, "team_a.png"), (M.TEAM_B, "team_b.png")])
@pytest.mark.parametrize("clock_at", [0, 2])
def test_readable_clock_anywhere_vetoes_hidden_clock_live_frame(channel, name, clock_at):
    # The clock-bearing frame deliberately has NO known feed. A later readable
    # clock still vetoes an earlier hidden-clock event after the complete scan.
    frames = [live(), live(), live()]
    frames[clock_at] = paste(blank(), channel.box, crop(name))
    guard = K.inspect_match(enumerate(frames), source_id="competitive-composite", start=0, stop=3)
    assert guard.complete and guard.team_clock_seen
    hidden = K.recognise_layout(frames[1], match_evidence=guard,
                                source_id="competitive-composite", frame_index=1)
    assert hidden.reason == "match_team_clock_veto" and hidden.layout is None
    candidate = K.Decision("live_quick_match", "fabricated")
    assert K.consistent_layout([(1, candidate)], start=1, stop=2, match_evidence=guard,
                               source_id="competitive-composite").reason == "match_team_clock_veto"


@pytest.mark.parametrize("indices", [[], [0], [1, 2], [0, 2], [0, 0, 1, 2], [0, 2, 1], [0, 1, 2, 3]])
def test_match_scan_and_event_interval_require_every_index_once_in_order(indices):
    frame = live()
    guard = K.inspect_match(((i, frame) for i in indices), source_id="synthetic", start=0, stop=3)
    assert not guard.complete
    assert K.recognise_layout(frame, match_evidence=guard, source_id="synthetic",
                              frame_index=0).layout is None
    decision = K.recognise_layout(replay())
    interval = K.consistent_layout(((i, decision) for i in indices), start=0, stop=3)
    assert interval.reason == "incomplete_or_unordered_interval"


def test_complete_nonzero_interval_and_invalid_bounds():
    decision = K.recognise_layout(replay())
    assert K.consistent_layout([(8, decision), (9, decision)], start=8, stop=10).layout == "replay_spectator"
    for start, stop in [(-1, 1), (3, 3), (3, 2), (False, 2), (0, 1.5)]:
        assert K.consistent_layout([], start=start, stop=stop).reason == "invalid_interval_bounds"
        assert not K.inspect_match([], source_id="synthetic", start=start, stop=stop).complete


def test_invalid_frame_or_missing_source_cannot_complete_match_scan():
    assert not K.inspect_match([(0, None)], source_id="synthetic", start=0, stop=1).complete
    assert not K.inspect_match([(0, live())], source_id="", start=0, stop=1).complete


def test_live_interval_cannot_bypass_guard_even_with_positive_decisions():
    decision = checked_live(live())
    assert K.consistent_layout([(0, decision)], start=0, stop=1).reason == "complete_match_scan_required"
