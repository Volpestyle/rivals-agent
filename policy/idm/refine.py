"""Label-quality pass v2-cd-r1 over the IDM's per-span outputs (VUH-1353; lane note "v2-cd-r1").

Applied at export (policy.idm.labels export --refine CONFIG.json), from the saved per-interval probabilities and a
10 Hz HUD scan of each span (D:/rivals-agent-local/idm-labels-work/r1/hudscan.py); no model inference.

- Admission: a sampled frame showing the scoreboard rule (perception.scoreboard, >= SCOREBOARD_OPEN), no HUD or a
  dead hero (perception.replay_hud.abstain_reason) rejects the rows within `margin_s` of it (the model's context
  reaches 0.2 s either side). Rows stay in the table with suitability "rejected" and an admission_reason.
- Holds: per-action hysteresis on the held probability (on, off, gap fill), tuned on James's -11 and checked on -12.
  A filled gap is a modelling choice, not an observed hold; held_p carries the raw probability.
- Presses: per-action onset thresholds (tuned likewise); press_p carries the raw step maximum as a soft target.
- HUD evidence: a cast seen on the HUD (ammo or charge drop, cooldown start, ult spent) with no IDM onset in its
  window adds one at the most probable interval there; an IDM onset for that ability inside HUD coverage with no
  cast nearby becomes unknown (null), since a physical press can fail to cast. The HUD dates the cast, not the key
  edge: the added onset's timing is the IDM's, and is only as good as its probabilities.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

# HUD ability (perception.replay_hud events) -> IDM action
HUD_ACTION = {"web_cluster": "web_cluster", "swing": "web_swing", "uppercut": "amazing_combo",
              "get_over_here": "get_over_here", "teamup": "team_up", "ult": "ultimate"}
# Evidence kind per HUD ability. All are patch-independent: drops of ammo/charges, a cooldown numeral appearing
# (any value; durations are NOT used), the ult spent. Cooldown and recharge durations change with patches and the
# expert sources' patches are unknown, so none is assumed (lead/James 2026-09-30); docs/spiderman-kit.md owns them.
HUD_KIND = {"web_cluster": "ammo", "swing": "charges", "uppercut": "charges", "get_over_here": "cooldown_start",
            "teamup": "cooldown_start", "ult": "ult_spent"}
HUD_REASONS = ("no HUD drawn", "dead (hp 0)")
SCOREBOARD_OPEN = 0.85                 # perception.scoreboard.SCOREBOARD_OPEN
SCAN_PERIOD_S = 0.1


def hysteresis(p, on, off, gap=0):
    """Rows held: on at p >= on, kept while p >= off; then off-runs of at most `gap` rows between two held runs are
    filled. Vectorised; p is one contiguous sequence."""
    p = np.asarray(p, float)
    mark = np.where(p >= on, 1, np.where(p < off, -1, 0))
    idx = np.where(mark != 0, np.arange(len(p)), -1)
    last = np.maximum.accumulate(idx) if len(p) else idx
    out = (last >= 0) & (mark[np.maximum(last, 0)] == 1)
    if gap and out.any():
        d = np.diff(np.r_[1, out.astype(np.int8), 1])
        starts, ends = np.flatnonzero(d == -1), np.flatnonzero(d == 1)      # off-runs [s, e)
        for s, e in zip(starts, ends):
            if 0 < s and e < len(out) and e - s <= gap:
                out[s:e] = True
    return out


def load_scan(path):
    path = Path(path)
    if not path.exists():
        return None
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def no_hud_share(scans):
    """Share of a source's scanned frames read as no HUD or dead. Admitted spans are gameplay, so a high share means
    the readers cannot read this source's HUD (layout or scale), not that it is missing."""
    recs = [r for scan in scans for r in scan]
    return sum(r.get("why") in HUD_REASONS for r in recs) / max(len(recs), 1)


def bad_windows(scan, margin_s=0.2, hud_reasons=True):
    """[(lo, hi, reason)] in span-relative seconds, merged per reason. hud_reasons=False keeps only the scoreboard
    rule (for a source whose HUD the readers cannot read)."""
    out = []
    reasons = ("scoreboard", *HUD_REASONS) if hud_reasons else ("scoreboard",)
    for rec in scan:
        why = "scoreboard" if rec.get("sb", 0) >= SCOREBOARD_OPEN else rec.get("why")
        if why in reasons:
            lo, hi = rec["t"] - SCAN_PERIOD_S / 2 - margin_s, rec["t"] + SCAN_PERIOD_S / 2 + margin_s
            if out and out[-1][2] == why and lo <= out[-1][1]:
                out[-1] = (out[-1][0], hi, why)
            else:
                out.append((lo, hi, why))
    return out


def hud_rows(scan):
    """perception.replay_hud.Row objects from a compact scan (withheld frames keep their reason)."""
    from perception import replay_hud as rh
    rows = []
    for rec in scan:
        t = rec["t"]
        if "f" not in rec:
            rows += [rh.Row(t, n, "unknown", None, 0.0, rec.get("why") or "no HUD drawn") for n in rh.FIELDS]
            continue
        f = rec["f"]
        for n in rh.FIELDS:
            state, num = f.get(n, ("unknown", None))
            rows.append(rh.Row(t, n, state, num, 0.0 if state == "unknown" else 1.0, "" if state != "unknown"
                               else "unread"))
    return rows


def hud_evidence(scan, max_gap_s=0.21):
    """(events, coverage) from a scan, span-relative; flagged events are dropped (not claimed casts)."""
    from perception import replay_hud as rh
    # cooldowns None: a cast is dated by the first countdown read after a read without one ("transition"), never
    # by a duration; max_gap_s caps coverage below any recharge time, so recharge durations do not matter either
    events, coverage, _ = rh.cast_events(hud_rows(scan), cooldowns={"get_over_here": None, "teamup": None},
                                         max_gap_s=max_gap_s)
    return [e for e in events if e.basis != "flagged" and e.ability in HUD_ACTION], coverage


def apply_hud(onset, prob, t_rel, actions, events, coverage, *, lead_s=0.6, lag_s=0.1, quiet_s=0.8, use=None,
              contradict=None):
    """Onsets (bool [n, actions]) corrected by HUD casts; returns (onset, basis) where basis[k, c] is one of
    "hud_added:<kind>" | "hud_confirmed:<kind>" | "hud_contradicted" | "" per interval (kind from HUD_KIND). A cast in (t_lo, t_hi] confirms an IDM
    onset in [t_lo - lead_s, t_hi + lag_s], else adds one at that window's most probable interval. An onset whose
    following `quiet_s` lies inside the ability's coverage with no cast is contradicted (made unknown by the caller).
    Abilities with no coverage keep their onsets untouched. `use` ({action: lead_s}) limits the evidence to those
    actions with their own lead; `contradict` (actions) limits contradiction (None: every covered action)."""
    onset = onset.copy()
    basis = np.full(onset.shape, "", dtype=object)
    used = np.zeros(onset.shape, bool)
    for e in events:
        a = HUD_ACTION[e.ability]
        if a not in actions or (use is not None and a not in use):
            continue
        c = actions.index(a)
        lead = lead_s if use is None else use[a]
        w = np.flatnonzero((t_rel >= e.t_lo - lead) & (t_rel <= e.t_hi + lag_s))
        if not len(w):
            continue
        hit = w[onset[w, c] & ~used[w, c]]
        if len(hit):
            k = hit[np.argmin(np.abs(t_rel[hit] - e.t_lo))]
            basis[k, c] = "hud_confirmed:" + HUD_KIND[e.ability]
        else:
            k = w[np.argmax(prob[w, c])]
            onset[k, c] = True
            basis[k, c] = "hud_added:" + HUD_KIND[e.ability]
        used[k, c] = True
    for hud_name, action in HUD_ACTION.items():
        if action not in actions or (contradict is not None and action not in contradict):
            continue
        c = actions.index(action)
        pairs = sorted(s for key, v in coverage.items() if key == hud_name or key.split(".")[0] == hud_name
                       for s in v)
        if not pairs:
            continue
        spans = [list(pairs[0])]                        # coverage comes as consecutive read pairs: join them
        for a, b in pairs[1:]:
            if a <= spans[-1][1] + 1e-6:
                spans[-1][1] = max(spans[-1][1], b)
            else:
                spans.append([a, b])
        for k in np.flatnonzero(onset[:, c] & ~used[:, c]):
            t = t_rel[k]
            if any(a <= t and t + quiet_s <= b for a, b in spans):
                basis[k, c] = "hud_contradicted"
    return onset, basis
