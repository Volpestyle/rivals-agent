"""Summarise an rl.scan run into reward events, and pair KO rings with kill-feed arrivals for hand checking.

  python -m rl.audit SCAN.jsonl [--window 2.0]

Prints per-minute hit, KO and kill-feed rates, the KO events, and every kill-feed arrival with no KO ring within
--window seconds (and vice versa). Those unpaired events are what a hand check must look at first.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rl.rewards import RewardTracker  # noqa: E402


def load(path):
    return [json.loads(line) for line in open(path, encoding='utf-8') if line.strip()]


def feed_arrivals(rows, hold=2):
    """Times the kill feed turns on after at least `hold` frames off (is_killfeed; None is ignored)."""
    out, off = [], hold
    for r in rows:
        if r['feed'] is True:
            if off >= hold:
                out.append(r['t'])
            off = 0
        elif r['feed'] is False:
            off += 1
    return out


def summarise(rows, window=2.0):
    tr = RewardTracker()
    steps = [tr.update(r['t'], r['hit'], r['ko'], r['hp'], r['max_hp'], r.get('own')) for r in rows]
    minutes = (rows[-1]['t'] - rows[0]['t']) / 60 if len(rows) > 1 else 0
    kos = [s.t for s in steps if s.ko]
    hits = [s.t for s in steps if s.hit]
    feeds = feed_arrivals(rows)
    return {
        'minutes': round(minutes, 2), 'hits': len(hits), 'kos': len(kos), 'feed_arrivals': len(feeds),
        'hits_per_min': round(len(hits) / minutes, 1) if minutes else None,
        'kos_per_min': round(len(kos) / minutes, 2) if minutes else None,
        'hp_lost': sum(s.hp_lost or 0 for s in steps), 'deaths': sum(s.death for s in steps),
        'ko_times': kos,
        'ko_without_feed': [t for t in kos if not any(abs(t - f) <= window for f in feeds)],
        'feed_without_ko': [f for f in feeds if not any(abs(t - f) <= window for t in kos)],
        'hp_unread_share': round(sum(r['hp'] is None for r in rows) / len(rows), 3),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('scan')
    ap.add_argument('--window', type=float, default=2.0)
    a = ap.parse_args(argv)
    print(json.dumps(summarise(load(a.scan), a.window), indent=1))


if __name__ == '__main__':
    main()
