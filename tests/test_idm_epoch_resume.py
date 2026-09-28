"""Real tiny IDM fit: full vs epoch-boundary interruption, synthetic pixels only."""
import json
from pathlib import Path
import random

import pytest

torch = pytest.importorskip("torch")
np = pytest.importorskip("numpy")

from policy.idm import epoch_resume as E, train as TR
from test_idm_model import TINY, examples, prov


@pytest.fixture
def rig(tmp_path):
    old = torch.get_num_threads()
    torch.set_num_threads(2)
    ex, target, store = examples(tmp_path, n=17)
    dummy = TR.IDM(TINY)
    dummy.support = TR.support_set(ex.supported)
    meta = prov(dummy, target, tmp_path / "a.idm.jsonl", store)
    stats = TR.train_statistics(ex)
    base_inputs = ex.inputs
    seen = []
    def noisy_inputs(idx):
        seen.extend(idx)
        motion, hud = base_inputs(idx)
        # Exercise all three persisted RNGs, even though production has no augmentation.
        return motion + (random.random() + np.random.random() + torch.rand(())) * .001, hud
    ex.inputs = noisy_inputs
    def journal(root, **kwargs):
        return E.EpochJournal(root, identity={"inputs": "a"*64, "recipe": "b"*64},
                              provenance=meta, commit=lambda: None, **kwargs)
    def fit(j):
        return TR.fit(ex, TINY, stats, seed=7, epochs=3, batch_size=5, epoch_journal=j)
    yield ex, stats, journal, fit, seen
    torch.set_num_threads(old)


def identical(a, b):
    if isinstance(a, torch.Tensor):
        assert torch.equal(a, b)
    elif isinstance(a, dict):
        assert a.keys() == b.keys()
        for k in a:
            identical(a[k], b[k])
    elif isinstance(a, (tuple, list)):
        assert len(a) == len(b)
        for x, y in zip(a, b):
            identical(x, y)
    else:
        assert a == b


def test_epoch_resume_matches_uninterrupted_and_epoch1_is_scoreable(tmp_path, rig):
    ex, _, journal, fit, seen = rig
    np.random.seed(123)
    full = journal(tmp_path / "full")
    model, history, _ = fit(full)
    order = list(seen)
    seen.clear()
    np.random.seed(123)
    interrupted = journal(tmp_path / "interrupted")
    save = interrupted.save
    def stop_after_epoch1(*args):
        save(*args)
        raise InterruptedError("after durable epoch one")
    interrupted.save = stop_after_epoch1
    with pytest.raises(InterruptedError):
        fit(interrupted)
    receipt = next(interrupted.root.glob("*.complete.json"))
    payload = json.loads(receipt.read_bytes())
    score_model, _ = TR.load_checkpoint(receipt.parent / payload["artifact"]["path"])
    with torch.no_grad():
        scores = score_model(*ex.inputs([0]))
    assert all(bool(torch.isfinite(x).all()) for x in scores)
    seen.pop()  # scoring is not a training step
    # New output root models fresh-app relaunch from a pinned prior receipt.
    resumed = journal(tmp_path / "resumed", resume_from=receipt, resume_sha256=E.digest(receipt.read_bytes()))
    random.seed(999)
    np.random.seed(999)
    torch.manual_seed(999)
    restored, restored_history, _ = fit(resumed)
    assert seen == order
    identical(model.state_dict(), restored.state_dict())
    assert [h["train_loss"] for h in history] == [h["train_loss"] for h in restored_history]
    a, _ = full.read(next(full.root.glob("epoch-0003*.complete.json")))
    b, _ = resumed.read(next(resumed.root.glob("epoch-0003*.complete.json")))
    identical(a["resume"]["optimizer"], b["resume"]["optimizer"])
    identical(a["resume"]["rng"], b["resume"]["rng"])
    assert b["resume"]["step_count"] == 3 * ((len(ex) + 4)//5)
    # Complete final checkpoint re-entry does zero further updates.
    seen.clear()
    fit(journal(resumed.root))
    assert not seen


def test_partial_without_complete_refuses(tmp_path, rig):
    _, _, journal, fit, _ = rig
    root = tmp_path / "partial"
    root.mkdir()
    (root / "epoch-0001-partial.pt").write_bytes(b"incomplete")
    with pytest.raises(ValueError, match="partial epoch"):
        fit(journal(root))


@pytest.mark.parametrize("failure", ["hash", "identity", "rows", "pin", "steps"])
def test_resume_refusals(tmp_path, rig, failure):
    ex, _, journal, fit, _ = rig
    j = journal(tmp_path / "source")
    fit(j)
    receipt = next(j.root.glob("epoch-0003*.complete.json"))
    data = json.loads(receipt.read_bytes())
    source = j.root / data["artifact"]["path"]
    if failure == "hash":
        source.write_bytes(source.read_bytes() + b"corrupt")
    if failure == "identity":
        j.identity["inputs"] = "c"*64
    if failure == "rows":
        ex.items.reverse()
    if failure == "pin":
        j.resume_from, j.resume_sha256 = receipt, "0"*64
    if failure == "steps":
        state = torch.load(source, weights_only=True)
        state["resume"]["next_batch"] = 1
        torch.save(state, source)
        raw = source.read_bytes()
        data["artifact"].update(bytes=len(raw), sha256=E.digest(raw))
        receipt.write_bytes(E.canonical(data))
    with pytest.raises(ValueError):
        fit(j)


def test_payload_committed_before_receipt_and_partial_later_epoch_ignored(tmp_path, rig):
    _, _, journal, fit, _ = rig
    j = journal(tmp_path / "source")
    calls = []
    def commit():
        calls.append((len(list(j.root.glob("*.pt"))), len(list(j.root.glob("*.complete.json")))))
    j.commit = commit
    fit(j)
    assert calls == [(1, 0), (1, 1), (2, 1), (2, 2), (3, 2), (3, 3)]
    (j.root / "epoch-0004-partial.pt").write_bytes(b"partial never loaded")
    fit(j)


def test_same_output_reentry_replays_interrupted_epoch_in_same_order(tmp_path, rig):
    ex, _, journal, fit, seen = rig
    np.random.seed(10)
    uninterrupted, history, _ = fit(journal(tmp_path / "full"))
    expected_order = list(seen)
    seen.clear()
    np.random.seed(10)
    root = tmp_path / "resume"
    inputs = ex.inputs
    calls = 0
    batches = (len(ex) + 4) // 5
    def interrupted(idx):
        nonlocal calls
        calls += 1
        if calls == batches + 2:
            raise InterruptedError("mid epoch two")
        return inputs(idx)
    ex.inputs = interrupted
    with pytest.raises(InterruptedError):
        fit(journal(root))
    assert len(list(root.glob("*.complete.json"))) == 1
    ex.inputs = inputs
    seen.clear()
    resumed, actual_history, _ = fit(journal(root))
    assert seen == expected_order[len(ex):]
    identical(uninterrupted.state_dict(), resumed.state_dict())
    assert [h["train_loss"] for h in history] == [h["train_loss"] for h in actual_history]


def test_v2_validator_pins_completed_epoch_and_refuses_partial(tmp_path, rig):
    _, _, journal, fit, _ = rig
    root = tmp_path / "fit"
    root.mkdir()
    identity = {"inputs": "a"*64, "recipe": "b"*64}
    with pytest.raises(ValueError, match="no completed epoch"):
        E.validate_resume(root, scientific_identity=identity)
    j = journal(root / "epochs")
    fit(j)
    state = E.validate_resume(root, scientific_identity=identity)
    assert state["completed_epochs"] == 3
    assert E.digest(Path(state["receipt"]).read_bytes()) == state["sha256"]
    with pytest.raises(ValueError, match="scientific identity"):
        E.validate_resume(root, scientific_identity={"inputs": "wrong"})
    with pytest.raises(ValueError, match="read-only mount"):
        E.validate_resume(root, scientific_identity=identity,
                          source_ref={"path": state["receipt"], "sha256": state["sha256"]})


def test_guard_stage_reentry_resumes_complete_epoch(tmp_path, rig):
    from cloud.modal_guard import stages
    _, _, journal, fit, _ = rig
    root = tmp_path / "fit"
    identity = {"attempt_id": "synthetic", "inputs_sha256": "a"*64, "recipe_sha256": "b"*64,
                "code_sha256": "c"*64, "output_volume_id": "vo-synthetic"}
    scientific = {"inputs": "a"*64, "recipe": "b"*64}
    seen = []
    def compute(path, resume_state=None):
        j = journal(path / "epochs")
        seen.append(resume_state)
        if len(seen) == 1:
            save = j.save
            def interrupt(*args):
                save(*args)
                raise InterruptedError("epoch one persisted")
            j.save = interrupt
        elif resume_state:
            j.resume_from = Path(resume_state["receipt"])
            j.resume_sha256 = resume_state["sha256"]
        fit(j)
        (path / "fit.json").write_text('{}')
        return 0
    def run():
        return stages.run(root, "fit", identity, ["fit.json"], compute,
                          commit=lambda: None, reload=lambda: None,
                          resume=lambda p: E.validate_resume(p, scientific_identity=scientific))
    with pytest.raises(InterruptedError):
        run()
    result = run()
    assert seen[0] is None and seen[1]["completed_epochs"] == 1
    assert run() == result and len(seen) == 2


def test_torn_new_checkpoint_retains_previous_verified_epoch(tmp_path, rig):
    _, _, journal, fit, _ = rig
    root = tmp_path / "interrupted"
    j = journal(root)
    commits = 0
    def failed_commit():
        nonlocal commits
        commits += 1
        if commits == 3:
            raise OSError("lost connection publishing epoch two")
    j.commit = failed_commit
    with pytest.raises(OSError):
        fit(j)
    receipts = list(root.glob("*.complete.json"))
    assert len(receipts) == 1 and json.loads(receipts[0].read_bytes())["completed_epochs"] == 1
    assert len(list(root.glob("*.pt"))) == 2  # Partial publication is retained, never loaded.
    _, history, _ = fit(journal(root))
    assert len(history) == 3


def test_training_progress_and_log_failure_cannot_abort_fit(tmp_path, rig):
    ex, stats, journal, _, _ = rig
    def broken(*args, **kwargs):
        raise OSError("telemetry failure")
    model, history, _ = TR.fit(ex, TINY, stats, seed=7, epochs=3, batch_size=5,
                              epoch_journal=journal(tmp_path / "epochs"), progress=broken, log=broken)
    assert len(history) == 3 and all(bool(torch.isfinite(v).all()) for v in model.state_dict().values())
