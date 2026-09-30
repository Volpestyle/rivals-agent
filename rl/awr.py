"""Offline advantage-weighted regression (AWR) step 0 on the bc2 policy, from pixel reward labels (VUH-1321).

James's steps get a reward from the readers' events (rl/labels/range_rewards_*.json: KO +10, hit +1, fall death -10),
a discounted return inside each eligible run (half-life HALF_LIFE_S), and an advantage against a value head fitted on
the frozen bc2 policy's recurrent state. The policy is then fine-tuned from the bc2 checkpoint with each step's BC loss
weighted by exp(A / beta) (clipped, mean 1) plus a KL term to the frozen bc2 outputs.

Arms (same epochs, same KL): awr (beta = 1 std of A), awr-hot (beta = 0.5 std), uniform (all weights 1: fine-tuning
alone), shuffled (the awr weights permuted within each session: same weight distribution, no advantage signal).

Evaluation, dev (selection pair) and val (212646): the bc2 metrics (policy.bc2.train.evaluate, thresholds calibrated
on train predictions, as bc2 does), and the shift toward high-return behaviour: per step, the change in log-likelihood
of James's actual actions versus bc2, by advantage quintile. AWR should raise the likelihood of high-advantage steps
relative to low-advantage ones; the controls should not.

Pure parts (rewards, returns, weights, quintile table) are numpy and tested in tests/test_rl_awr.py; the torch parts
run on Modal (rl/awr_modal.py).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

REWARD = {"ko": 10.0, "hit": 1.0, "death": -10.0}
HALF_LIFE_S = 2.0
STEP_S = 1 / 30
GAMMA = 0.5 ** (STEP_S / HALF_LIFE_S)
W_CLIP = 20.0


# --- pure: rewards, returns, weights --------------------------------------------------------------
def anchors(steps_jsonl):
    """{row i: anchor_ns} and step_ns from a step table (header line, then one row per anchor)."""
    out, step_ns = {}, None
    with open(steps_jsonl, encoding="utf-8") as f:
        for n, line in enumerate(f):
            j = json.loads(line)
            if n == 0:
                step_ns = j["step_ns"]
                continue
            out[j["i"]] = j["anchor_ns"]
    return out, step_ns


def step_rewards(anchor_ns, step_ns, labels, reward=REWARD):
    """Per-step reward for rows with these anchors [n] (ascending within runs). An event at logger time e belongs to
    the step whose bin [anchor, anchor + step_ns) holds it; events outside every step (gaps, ineligible rows) are
    dropped and counted."""
    a = np.asarray(anchor_ns, np.int64)
    order = np.argsort(a, kind="stable")
    sa = a[order]
    r = np.zeros(len(a), np.float64)
    kept = dropped = 0
    for kind, w in reward.items():
        for t in labels.get(kind, []):
            e = labels["t0_composition_ns"] + int(round(t * 1e9))
            k = np.searchsorted(sa, e, side="right") - 1
            if k >= 0 and e - sa[k] < step_ns:
                r[order[k]] += w
                kept += 1
            else:
                dropped += 1
    return r, {"kept": kept, "dropped": dropped}


def discounted_returns(r, run_start, gamma=GAMMA):
    """G_t = r_t + gamma G_{t+1} inside each run (run_start marks each run's first row); no bootstrap past a run."""
    g = np.zeros(len(r), np.float64)
    acc = 0.0
    ends = np.zeros(len(r), bool)
    ends[:-1] = run_start[1:]
    ends[-1:] = True
    for k in range(len(r) - 1, -1, -1):
        if ends[k]:
            acc = 0.0
        acc = r[k] + gamma * acc
        g[k] = acc
    return g


def awr_weights(adv, beta, clip=W_CLIP, valid=None):
    """exp(A / beta) clipped at `clip`, normalised to mean 1 over valid steps."""
    w = np.minimum(np.exp(np.clip(adv / beta, -50, 50)), clip)
    v = np.ones(len(w), bool) if valid is None else valid
    return w / w[v].mean()


def quintile_table(adv, delta, valid):
    """Mean change in log-likelihood (arm minus bc2) of James's actions by advantage quintile, plus the top-minus-bottom
    gap and the rank correlation between A and the change."""
    a, d = adv[valid], delta[valid]
    edges = np.quantile(a, [0, .2, .4, .6, .8, 1])
    q = np.clip(np.searchsorted(edges, a, side="right") - 1, 0, 4)
    rows = [{"quintile": k + 1, "adv_lo": float(edges[k]), "adv_hi": float(edges[k + 1]), "steps": int((q == k).sum()),
             "mean_delta_logp": float(d[q == k].mean()) if (q == k).any() else None} for k in range(5)]
    ra, rd = np.argsort(np.argsort(a)), np.argsort(np.argsort(d))
    rho = float(np.corrcoef(ra, rd)[0, 1]) if len(a) > 2 else math.nan
    gap = rows[4]["mean_delta_logp"] - rows[0]["mean_delta_logp"]
    return {"quintiles": rows, "top_minus_bottom": gap, "spearman": rho}


def session_rewards(targets_rows, run_start, steps_jsonl, labels):
    anc, step_ns = anchors(steps_jsonl)
    a = np.array([anc[int(k)] for k in targets_rows], np.int64)
    r, counts = step_rewards(a, step_ns, labels)
    return r, discounted_returns(r, np.asarray(run_start, bool)), counts


def load_labels(paths):
    out = {}
    for p in paths:
        out.update(json.loads(Path(p).read_text(encoding="utf-8"))["sessions"])
    return out


def bootstrap_gap(adv, delta, valid, block=300, n=1000, seed=0):
    """95% interval of the top-minus-bottom quintile gap by resampling contiguous blocks of `block` steps (10 s at
    30 Hz), which keeps the within-engagement correlation that a per-step bootstrap would ignore. Quintile edges are
    fixed from the full sample."""
    a, d = adv[valid], delta[valid]
    edges = np.quantile(a, [.2, .8])
    top, bot = a >= edges[1], a <= edges[0]
    nb = max(1, len(a) // block)
    blocks = [slice(k * block, (k + 1) * block if k < nb - 1 else len(a)) for k in range(nb)]
    st = np.array([[d[b][top[b]].sum(), top[b].sum(), d[b][bot[b]].sum(), bot[b].sum()] for b in blocks])
    rng = np.random.default_rng(seed)
    gaps = []
    for _ in range(n):
        s = st[rng.integers(0, nb, nb)].sum(0)
        if s[1] and s[3]:
            gaps.append(s[0] / s[1] - s[2] / s[3])
    lo, hi = np.percentile(gaps, [2.5, 97.5])
    return float(lo), float(hi)
