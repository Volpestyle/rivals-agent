"""Metadata only: the cache loader refuses one more sealed identity, never fewer."""
import hashlib
import json
from pathlib import Path

import pytest

from policy.range_bc import steps

OLD = "439c80df6cd5d6daa60b48e0acb2d3a3fa833134ff14edddc4121348c2dceb20"
NEW = "09e8b9d350c89eb41c1581e1bce47548bfb855bca5805cf2e65955b9b23597b5"
APPENDED = "20260927T195110-265Z-152960-1"
ROOT = Path(__file__).resolve().parents[1]


def test_current_denylist_is_byte_preserving_strict_superset_of_previous_pin():
    # Read only the denylist document, never any named path or source payload.
    raw = (ROOT / steps.DENYLIST).read_bytes().replace(b"\r\n", b"\n")
    assert steps.DENYLIST_SHA256 == NEW == hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8")
    decoder = json.JSONDecoder()
    start = text.index("[", text.index('"sessions"')) + 1
    spans = []
    while True:
        while text[start].isspace() or text[start] == ",":
            start += 1
        if text[start] == "]":
            break
        row, end = decoder.raw_decode(text, start)
        spans.append((row, start, end))
        start = end
    assert len(spans) == 8
    assert spans[-1][0]["session_id"] == APPENDED
    assert spans[-1][0]["allowed_split"] == "test"
    assert APPENDED not in {row["session_id"] for row, _, _ in spans[:-1]}
    # Remove ONLY the last comma and appended object, without reserializing.
    # The remaining full document must hash to the previous exact byte pin.
    # This proves every prior entry (including whitespace/key order) and all
    # non-session metadata are byte-equal to 439c80df, not merely equivalent JSON.
    previous = (text[:spans[-2][2]] + text[spans[-1][2]:]).encode("utf-8")
    assert hashlib.sha256(previous).hexdigest() == OLD
    assert json.loads(previous)["sessions"] == json.loads(raw)["sessions"][:-1]


def test_default_loader_refuses_every_old_identity_and_the_appended_one():
    denylist = steps.load_denylist()
    assert len(denylist["sessions"]) == 8
    for row in denylist["sessions"]:
        with pytest.raises(steps.StepError, match="sealed"):
            steps.check_sealed(row["session_id"], "0"*64, denylist)
        with pytest.raises(steps.StepError, match="sealed"):
            steps.check_sealed("synthetic-unrelated", row["media_sha256"], denylist)
    steps.check_sealed("synthetic-unrelated", "0"*64, denylist)
