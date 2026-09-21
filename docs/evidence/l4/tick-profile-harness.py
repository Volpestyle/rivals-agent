"""Tick-cost profile of agent.loop on the PC. NO pad is opened and NO input is sent: Live gets a fake pad and a replay
capture that serves data/l1/postfreeze30's native frames at 60 Hz (each recorded frame six times, a fresh array per grab,
as dxcam does). Everything else is the real code: default_perception, Tracker, Controller, the threaded Decider, Live's
commit path, RunLog with native JPEG saving. Usage: python data\\l4\\profile_tick.py [inline]"""
import glob, json, sys, threading, time
from collections import defaultdict
from dataclasses import replace
sys.path.insert(0, "."); sys.path.insert(0, "scripts")
import cv2, numpy as np
import agent.loop as L
from agent.controller import Live
import record

RUN = r"data\l1\postfreeze30"
files = sorted(glob.glob(RUN + r"\0*.jpg"))
frames = [cv2.imread(f) for f in files]
print("frames", len(frames), frames[0].shape, flush=True)

T = defaultdict(list)          # component -> [(tick, ms)]
tick_no = [0]
worker_busy = []               # (start, end, what)
def timed(name, fn, worker=False):
    def w(*a, **k):
        t0 = time.perf_counter()
        try:
            return fn(*a, **k)
        finally:
            t1 = time.perf_counter()
            (worker_busy.append((t0, t1, name)) if worker else T[name].append((tick_no[0], (t1 - t0) * 1000)))
    return w

class ReplayCap:
    def __init__(self): self.i, self.next_t = 0, 0.0
    def grab(self):
        now = time.perf_counter()
        if now < self.next_t: return None
        if self.i >= len(frames) * 6: return None
        f = frames[self.i // 6].copy(); self.i += 1; self.next_t = max(self.next_t + 1 / 60, now - 0.005)
        return f

class FakePad:
    def reset(self): pass
    def press_button(self, button): pass
    def left_joystick_float(self, x, y): pass
    def right_joystick_float(self, x, y): pass
    def left_trigger_float(self, v): pass
    def right_trigger_float(self, v): pass
    def update(self): pass

live = Live(pad_factory=FakePad, capture=ReplayCap(), guard=timed("live.range_proof", record.in_range), settle_s=0)
live._apply = timed("live._apply", live._apply)
live.fresh = timed("capture.fresh(replay)", live.fresh)
p = L.default_perception()
p = replace(p, in_range=timed("loop.in_range", p.in_range), idle=timed("loop.idle", p.idle), aim=timed("aim_finder", p.aim),
            wide=timed("worker.wide", p.wide, True), hud=timed("worker.hud", p.hud, True), tag=timed("worker.tag", p.tag, True))
io = L.LiveIO(live=live)
threaded = "inline" not in sys.argv
import tempfile, pathlib
out = pathlib.Path(tempfile.mkdtemp(prefix="proftick-")) / "run"
loop = L.Loop(io, io, p, L.make_brain("scripted"), threaded=threaded, log=L.RunLog(out, 10.0), max_s=len(frames) * 6 / 60 - 1.0,
              scoreboard=False, cooldowns="normal")
nobox_ticks = set()
_tr = timed("tracker.update", loop.track)
def track(dets, t, size=None):
    if threading.current_thread() is threading.main_thread() and not dets: nobox_ticks.add(tick_no[0])
    return _tr(dets, t, size)
loop.track = track
loop.ctrl.step = timed("controller.step", loop.ctrl.step)
loop.decider.offer = timed("decider.offer", loop.decider.offer)
loop._log = timed("loop._log", loop._log)
real_tick = loop._tick
def _tick(frame, t):
    tick_no[0] += 1
    t0 = time.perf_counter()
    try: return real_tick(frame, t)
    finally: T["TICK(total incl. log)"].append((tick_no[0], (time.perf_counter() - t0) * 1000)); tick_spans.append((tick_no[0], t0, time.perf_counter()))
tick_spans = []
loop._tick = _tick
try:
    summary = loop.run()
finally:
    io.close()
def pct(v, q): v = sorted(v); return v[min(len(v) - 1, int(q * len(v)))]
res = {"threaded": threaded, "stop": summary["stop"], "reflex_hz": summary["reflex_hz"], "tick_ms": summary["tick_ms"], "period_ms": summary["period_ms"],
       "over_budget": summary["over_budget"], "decide_ms": summary["decide_ms"], "components": {}}
for name, rows in T.items():
    v = [ms for _, ms in rows]
    res["components"][name] = {"n": len(v), "p50": round(pct(v, .5), 2), "p95": round(pct(v, .95), 2), "max": round(max(v), 2)}
# over-budget ticks: loop.tick_ms[i] belongs to tick i+1
over = {i + 1 for i, ms in enumerate(loop.tick_ms) if ms > 16.67}
per_tick = defaultdict(dict)
for name, rows in T.items():
    for k, ms in rows: per_tick[k][name] = per_tick[k].get(name, 0.0) + ms
med = {name: pct([ms for _, ms in rows], .5) for name, rows in T.items()}
explain = defaultdict(int); excess = defaultdict(list)
for k in over:
    worst = max((n for n in per_tick[k] if not n.startswith(("TICK", "loop._log", "capture"))), key=lambda n: per_tick[k][n] - med[n])
    explain[worst] += 1
    for n, ms in per_tick[k].items(): excess[n].append(ms - med[n])
res["over_budget_ticks"] = len(over)
res["over_budget_biggest_excess_component"] = dict(explain)
res["over_budget_mean_excess_ms"] = {n: round(sum(v) / len(v), 2) for n, v in excess.items()}
# what was the worker doing during over-budget ticks?
def overlap(k):
    _, a, b = next(s for s in tick_spans if s[0] == k)
    return {w for (s, e, w) in worker_busy if s < b and e > a}
res["over_budget_worker_overlap"] = {w: sum(w in overlap(k) for k in over) for w in ("worker.wide", "worker.hud", "worker.tag")}
allt = [s[0] for s in tick_spans]
res["all_ticks_worker_overlap"] = {w: sum(w in overlap(k) for k in allt[::5]) * 5 for w in ("worker.wide", "worker.hud", "worker.tag")}
wb = defaultdict(list)
for s, e, w in worker_busy: wb[w].append((e - s) * 1000)
res["worker_ms"] = {w: {"n": len(v), "p50": round(pct(v, .5), 2), "p95": round(pct(v, .95), 2)} for w, v in wb.items()}
nobox = {i + 1 for i in range(len(loop.tick_ms))}
res["ticks"] = len(loop.tick_ms)
res["over_budget_rescued_if_live_proof_free"] = sum(1 for k in over if loop.tick_ms[k - 1] - per_tick[k].get("live.range_proof", 0.0) <= 16.67)
res["over_budget_rescued_if_both_predicates_cost_0.3ms"] = sum(1 for k in over if loop.tick_ms[k - 1] - per_tick[k].get("live.range_proof", 0.0) - per_tick[k].get("loop.in_range", 0.0) + 0.6 <= 16.67)
res["over_budget_with_no_box"] = sum(1 for k in over if not getattr(loop, "_nobox", {}).get(k, True))
nb = [k for k in range(1, len(loop.tick_ms) + 1) if k in nobox_ticks]
res["no_box_ticks"] = len(nb); res["over_budget_no_box"] = len(over & nobox_ticks)
res["aim_ms_p50_while_worker_wide_running_vs_not"] = [round(pct([per_tick[k]["aim_finder"] for k in allt if k in per_tick and "aim_finder" in per_tick[k] and ("worker.wide" in overlap(k)) == flag] or [0], .5), 2) for flag in (True, False)]
open(r"data\l4\profile_tick%s.json" % ("" if threaded else "_inline"), "w").write(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
