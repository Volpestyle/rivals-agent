"""Read-only pure-function probe of semantic decoding versus pad snapshots.

Does not construct Live, a controller, a pad, a capture object or a model.
No recordings are opened. Snapshot edges assume consecutive sample-and-hold
delivery without interstitial neutral writes; game registration is not modeled.
"""

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from policy.range_bc import executor, vocab


def trace(symbols):
    index = vocab.INDEX["web_cluster"]
    live_mask = [False] * vocab.N
    live_mask[index] = True
    previous = [0] * vocab.N
    records = []
    previous_lt = 0
    for symbol in symbols:
        held_p, press_p, release_p = ([0.] * vocab.N for _ in range(3))
        if symbol == "tap":
            press_p[index] = release_p[index] = 1.
        elif symbol == "hold":
            held_p[index] = 1.
        elif symbol != "idle":
            raise ValueError(symbol)
        held, press, release = executor.decode_step(
            held_p, press_p, release_p, previous, live_mask
        )
        pad = executor.pad_state(held, press, 0., 0.)
        lt = int(pad["lt"] > 0)
        records.append({
            "request": symbol,
            "decoded_hold_press_release": [held[index], press[index], release[index]],
            "pad_lt": lt,
            "snapshot_rise": int(lt and not previous_lt),
            "snapshot_fall": int(previous_lt and not lt),
        })
        previous, previous_lt = held, lt
    return records


def main():
    taps = trace(("tap", "tap", "idle"))
    hold = trace(("hold", "hold", "idle"))
    spaced = trace(("tap", "idle", "tap", "idle"))
    taps_then_tap = trace(("tap", "tap", "tap", "idle"))
    hold_then_tap = trace(("hold", "hold", "tap", "idle"))
    assert [r["pad_lt"] for r in taps] == [r["pad_lt"] for r in hold] == [1, 1, 0]
    assert sum(r["decoded_hold_press_release"][1] for r in taps) == 2
    assert sum(r["decoded_hold_press_release"][1] for r in hold) == 1
    assert sum(r["snapshot_rise"] for r in taps) == 1
    assert sum(r["snapshot_rise"] for r in spaced) == 2
    assert taps[0]["decoded_hold_press_release"] == [0, 1, 1]
    assert taps[0]["pad_lt"] == 1
    # Identical snapshot prefixes are not equivalent decoder states. A common
    # next tap request is accepted after semantic taps, but decoded as a fall
    # after a semantic hold. Keeping only physical snapshot history loses this.
    assert [r["pad_lt"] for r in taps_then_tap] == [1, 1, 1, 0]
    assert [r["pad_lt"] for r in hold_then_tap] == [1, 1, 0, 0]
    paths = ("policy/range_bc/executor.py", "policy/range_bc/train.py", "agent/pad_bindings.py")
    print(json.dumps({
        "kind": "pure_executor_snapshot_contract_probe_not_live_evidence",
        "source_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in paths
        },
        "adjacent_taps": taps,
        "continuous_hold": hold,
        "separated_taps": spaced,
        "common_next_tap_after_taps": taps_then_tap,
        "common_next_tap_after_hold": hold_then_tap,
        "different_decoded_histories_same_pad_snapshots": True,
        "same_snapshot_prefix_different_decoder_continuation": True,
        "assumption": "consecutive sample-and-hold snapshots; no intermediate neutral writes",
        "physical_delivery_or_casts_verified": False,
    }, indent=2))


if __name__ == "__main__":
    main()
