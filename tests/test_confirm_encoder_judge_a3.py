"""The historical judge stays frozen; every active-version hash must be valid."""
import ast
import hashlib
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'policy/range_bc/confirm_encoder_judge.py'
NEW = ROOT / 'policy/range_bc/confirm_encoder_judge_a3.py'


def canonical(path):
    return path.read_bytes().replace(b'\r\n', b'\n')


def test_a3_is_exactly_one_constant_correction_and_history_is_untouched():
    old, new = canonical(OLD), canonical(NEW)
    assert hashlib.sha256(old).hexdigest() == '6f2187dd974befedbaf656470d7b153f3a5ca7be0a62a3954a67670ab726aa32'
    wrong = b'aec08c08e247e3743ddeb1eec49dd880e1c0f62039c375932cab31dfccb91e22d'
    assert old.count(wrong) == 1
    assert new == old.replace(wrong, wrong[:-1])
    assert hashlib.sha256(new).hexdigest() == '66830ce6eb302f4b9052b99f0f6ee31836121dd524e7eb1ddabd5a32915ef6c8'


def test_every_pinned_hash_in_active_judge_is_64_hex_characters():
    tree = ast.parse(canonical(NEW))
    pins = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and ('SHA' in target.id or 'HASH' in target.id):
                    pins[target.id] = ast.literal_eval(node.value)
    assert set(pins) == {'INPUT_SHA', 'VISION_SHA'}
    for name, pin in pins.items():
        assert isinstance(pin, str) and re.fullmatch(r'[0-9a-f]{64}', pin), name
    # Also catch a long hex literal hidden outside a named hash assignment.
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and re.fullmatch(r'[0-9a-f]{50,}', node.value):
            assert len(node.value) == 64


def test_corrected_input_pin_matches_preserved_actual_manifest_bytes():
    from policy.range_bc import confirm_encoder_judge_a3 as judge
    path = ROOT / 'docs/evidence/nitrogen-nohistory-confirm-20260927/verified-model-input-manifest.json'
    # Manifest is LF JSON; canonical bytes reproduce the preserved Mac artifact on Windows.
    assert hashlib.sha256(canonical(path)).hexdigest() == judge.INPUT_SHA
