"""The sealed denylist v2 (2026-09-26 test take, VUH-1359): every consumer pins it, and a registry row naming either
new sealed session outside split test is refused. Reads only the pinned denylist and synthetic registries."""
import hashlib
import json
from pathlib import Path

import pytest

from agent import human_intake as hi
from agent.human_demos import DemoError

ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT / "data/human/sealed-denylist.json"
V2 = ROOT / "data/human/sealed-denylist.v2.json"
V1_SHA = "57cfe01f29f6e1a55293f968ec697aa293c268bd87d7cf247ef648279e2fba7c"
TEST_TAKE = "20260926T153835-237Z-111496-2"
HELD = "20260926T153812-936Z-111496-1"
OLD = "20260923T053616-779Z-33696-2"
PAIR1, PAIR2 = "gate2-20260925-central-park-1928", "gate2-20260925-hall-of-djalia-1949"
GATE2 = {"20260926T002109-428Z-63684-2": ("gate2", PAIR1), "20260926T044958-507Z-63684-15": ("gate2", PAIR1),
         "20260926T002851-659Z-63684-3": ("gate2", PAIR2), "20260926T155737-285Z-116800-1": ("gate2", PAIR2)}
SEALED = [(OLD, "test", None), (TEST_TAKE, "test", None), (HELD, "test", None),
          *[(sid, "gate2", grp) for sid, (_, grp) in GATE2.items()]]


def lf_sha(p):
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def v2():
    from policy.range_bc import steps
    return steps.load_denylist()          # the fit's own pinned default


def test_v1_is_unchanged_and_v2_is_a_superset_of_it():
    assert lf_sha(V1) == V1_SHA           # every admitted freeze pins v1 by path and sha256
    old, new = json.loads(V1.read_text()), json.loads(V2.read_text())
    assert new["sessions"][:len(old["sessions"])] == old["sessions"]
    assert new["supersedes"] == {"path": "data/human/sealed-denylist.json", "sha256": V1_SHA}
    rows = {r["session_id"]: r for r in new["sessions"]}
    assert set(rows) == {OLD, TEST_TAKE, HELD, *GATE2}
    for sid in (TEST_TAKE, HELD, *GATE2):
        assert len(rows[sid]["media_sha256"]) == 64 and rows[sid]["hashed_at"] and rows[sid]["reason"]
    assert "allowed_split" not in rows[OLD]                     # v1's row, unchanged: absent means test
    assert {sid: rows[sid]["allowed_split"] for sid in (TEST_TAKE, HELD)} == {TEST_TAKE: "test", HELD: "test"}
    assert {sid: (rows[sid]["allowed_split"], rows[sid]["session_group"]) for sid in GATE2} == GATE2


def test_every_consumer_pins_v2():
    import importlib.util
    from policy import idm_targets
    from policy.range_bc import steps
    pin = lf_sha(V2)
    assert (Path(steps.DENYLIST).as_posix().endswith("sealed-denylist.v2.json") and steps.DENYLIST_SHA256 == pin)
    assert idm_targets.DENYLIST == V2 and idm_targets.DENYLIST_SHA256 == pin
    for rel in ("scripts/transcode_recording.py", "data/human/sessions/assemble_session.py",
                "data/human/sessions/intake_session.py", "data/human/sessions/relocate_session.py",
                "data/human/sessions/tally.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert f'DENYLIST_SHA256 = "{pin}"' in text and "sealed-denylist.v2.json" in text, rel
        assert V1_SHA not in text and '"data/human/sealed-denylist.json"' not in text, rel


def _registry(tmp_path, **row):
    base = dict(session_id="x", session_group="x", split="train", video_path="x.mkv")
    path = tmp_path / "reg.json"
    path.write_text(json.dumps(dict(schema_version=1, sessions=[{**base, **row}])))
    return path


@pytest.mark.parametrize("sid", [TEST_TAKE, HELD])
@pytest.mark.parametrize("by", ["id", "media_path", "media_sha256"])
@pytest.mark.parametrize("split", ["train", "val", "gate2"])
def test_a_row_naming_a_new_sealed_session_outside_test_is_refused(tmp_path, sid, by, split):
    den = v2()
    row = next(r for r in den["sessions"] if r["session_id"] == sid)
    named = {"id": dict(session_id=sid, session_group=sid),
             "media_path": dict(video_path=row["media_path"]),
             "media_sha256": dict(recorded_video_path="y.mkv", expected_media_sha256=row["media_sha256"])}[by]
    extra = dict(sealed=True) if split == "gate2" else {}
    with pytest.raises(DemoError, match="denylisted session outside test"):
        hi.check_registry(_registry(tmp_path, split=split, **extra, **named), denylist=den)


@pytest.mark.parametrize("sid", [TEST_TAKE, HELD])
def test_the_same_rows_as_test_are_accepted_and_sealed(tmp_path, sid):
    den = v2()
    row = next(r for r in den["sessions"] if r["session_id"] == sid)
    reg = hi.check_registry(_registry(tmp_path, session_id=sid, session_group=sid, split="test", sealed=True,
                                      video_path=row["media_path"], recorded_video_path=row["media_path"],
                                      expected_media_sha256=row["media_sha256"]), denylist=den)
    assert reg[sid].split == "test"
    with pytest.raises(DemoError, match="sealed"):
        hi.assert_not_sealed(sid, "0" * 64, den)
    with pytest.raises(DemoError, match="sealed"):
        hi.assert_not_sealed("other", row["media_sha256"], den)


def test_the_live_registry_passes_v2_with_train_and_val_unchanged():
    reg = hi.check_registry(ROOT / "data/human/session-splits.corpus.json", denylist=v2())
    assert {s: p.split for s, p in reg.items() if s in (TEST_TAKE, HELD, OLD)} == {TEST_TAKE: "test", HELD: "test", OLD: "test"}
    assert sum(p.split == "val" for p in reg.values()) == 1


# ---- review B1 and B2 (review-admission-test-take-20260926.md): every list, authoritative sealed splits ----------

HARMLESS = dict(session_id="harmless", session_group="harmless", split="train", video_path="harmless.mkv")


def _probe(sealed_row, by):
    return {"id": dict(session_id=sealed_row["session_id"]),
            "media_path": dict(session_id="probe", video_path=sealed_row["media_path"]),
            "media_sha256": dict(session_id="probe", video_path="probe.mkv",
                                 expected_media_sha256=sealed_row["media_sha256"])}[by]


def _write(tmp_path, sessions, **lists):
    path = tmp_path / "reg.json"
    path.write_text(json.dumps(dict(schema_version=1, sessions=sessions, **lists)))
    return path


def _row(sid):
    return next(r for r in v2()["sessions"] if r["session_id"] == sid)


@pytest.mark.parametrize("sid,allowed,group", SEALED)
@pytest.mark.parametrize("by", ["id", "media_path", "media_sha256"])
@pytest.mark.parametrize("where", ["calibration_sessions", "evaluation_sessions"])
def test_b1_a_sealed_identity_in_an_excluded_list_is_refused(tmp_path, sid, allowed, group, by, where):
    probe = {**_probe(_row(sid), by), "session_group": "probe"}
    if where == "evaluation_sessions":
        probe["kind"] = "reader_development"
    with pytest.raises(DemoError, match=f"denylisted session .* in {where}"):
        hi.check_registry(_write(tmp_path, [HARMLESS], **{where: [probe]}), denylist=v2())


@pytest.mark.parametrize("sid,allowed,group,split", [(sid, a, g, sp) for sid, a, g in SEALED
                                                     for sp in ("train", "val", "test", "gate2") if sp != a])
@pytest.mark.parametrize("by", ["id", "media_path", "media_sha256"])
def test_b2_a_sealed_identity_in_a_split_other_than_its_own_is_refused(tmp_path, sid, allowed, group, by, split):
    probe = dict(_probe(_row(sid), by), session_group="probe", split=split)
    if split in ("test", "gate2"):
        probe["sealed"] = True
    with pytest.raises(DemoError, match=f"denylisted session outside {allowed}"):
        hi.check_registry(_write(tmp_path, [HARMLESS, probe]), denylist=v2())


@pytest.mark.parametrize("sid", sorted(GATE2))
def test_b2_a_gate2_identity_outside_its_pair_is_refused(tmp_path, sid):
    r = _row(sid)
    probe = dict(session_id=sid, session_group="another-pair", split="gate2", sealed=True, video_path=r["media_path"])
    with pytest.raises(DemoError, match="gate2 session outside its pair"):
        hi.check_registry(_write(tmp_path, [HARMLESS, probe]), denylist=v2())


@pytest.mark.parametrize("sid,allowed,group", SEALED)
def test_valid_controls_each_sealed_identity_in_its_own_split_and_unrelated_excluded_rows(tmp_path, sid, allowed, group):
    r = _row(sid)
    own = dict(session_id=sid, session_group=group or sid, split=allowed, sealed=True, video_path=r["media_path"],
               recorded_video_path=r["media_path"], expected_media_sha256=r["media_sha256"])
    reg = hi.check_registry(_write(tmp_path, [HARMLESS, own],
                                   calibration_sessions=[dict(session_id="cal", video_path="cal.mkv")],
                                   evaluation_sessions=[dict(session_id="ev", kind="reader_development",
                                                             video_path="ev.mkv")]), denylist=v2())
    assert reg[sid].split == allowed and set(reg) == {"harmless", sid}


def test_the_refusals_depend_on_the_guard(tmp_path, monkeypatch):
    """With the denylist matching removed, the B1 and B2 probes are accepted: the tests above fail without the guard."""
    r = _row("20260926T002851-659Z-63684-3")
    relabel = _write(tmp_path, [HARMLESS, dict(session_id=r["session_id"], session_group="x", split="train",
                                                video_path="elsewhere.mkv")])
    excluded = tmp_path / "excluded"
    excluded.mkdir()
    in_list = _write(excluded, [HARMLESS], evaluation_sessions=[dict(session_id=TEST_TAKE, kind="match_dev",
                                                                      video_path="e.mkv")])
    for path in (relabel, in_list):
        with pytest.raises(DemoError):
            hi.check_registry(path, denylist=v2())
    monkeypatch.setattr(hi, "sealed_matches", lambda *a, **k: [])
    for path in (relabel, in_list):
        assert hi.check_registry(path, denylist=v2())       # accepted: only the guard refused them
