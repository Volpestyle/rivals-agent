# admission-owner decision request: 203745 contains ~91.5 s of "Timed Practice" inside gameplay seg-015

**Session:** `20260925T203745-207Z-49728-2` (train, 48.0 min). Intake has run through evidence, from
`code-snapshot-b7d4592`, with the motor record citing `fbe6693`.
- `segments-evidence.json` `7b8a6118…`: 18 segments, five gameplay candidates totalling **47.50 provisional min**.
- Every edge passes E1, and the recorder check is clean (345,522 frames matched, 1 tail packet).
- The regime is normal, with 556 intervals `normal_depletion_observed` and 20 `no_evidence`.
- Owner verdicts are **not written yet**, because of the following.

## What I found

The owner inspection covered 314 review frames, all of them. Review frames f268214–f276597 (2,235–2,305 s) show the
top-left banner **"TIMED PRACTICE"** instead of "PRACTICE RANGE":
- a scored challenge with a "TOTAL SCORE" counter and a 60 s countdown (00:55 at 2,255 s, 00:05 at ~2,305 s);
- static green humanoid targets on a 20 m / 40 m lane, not Galacta bots;
- it ends in a teleport effect (f277795, 2,315 s).

The **one G press** (2,245.69 s, held 0.14 s) falls inside it.

**The span, measured on the original:** I decoded the banner every 0.5 s from 2,215 to 2,340 s (CPU, 4 threads;
`scratchpad/arrivals-0925/timed/banner-tile.png`).
- "PRACTICE RANGE" up to **2,228.0 s**, "TIMED PRACTICE" from **2,228.5 s** through **2,319.5 s**, and "PRACTICE RANGE"
  again from **2,320.0 s**.
- So about **91.5 s** (1.53 min), all inside seg-015 (2,095.51–2,873.92 s, 778.4 s).
- Times are logger time (file time + 0.0785 s), to ±0.5 s. I would refine them to native frames before any cut.

**The live range guard disagrees with itself there.** `in_range` is **False** on 2 of the 9 review frames in the span
(f270610 at 2,255.18 s and f277795 at 2,315.06 s), and True on the other 7.
- These are the only in-range failures on any interior review frame of a gameplay segment in this take. That covers
  293 frames. It is also true for val (103), 021320 (215) and 232304 (56).
- The live loop would stop there, and the edge rule would not place an edge on those frames.
- The guard is intermittent here, so it cannot delimit the span. The banner is the reliable signal.

**Earlier sessions:** a timed round runs at least 60 s, and the review frames sample about every 10 s. Since every
interior review frame of the admitted sessions passes `in_range`, a round there is unlikely. I have not checked their
banners directly.

## Options

**A. Accept seg-015 whole.**
- Timed Practice is a room of the practice range: same hero, kit, HUD and regime; James playing.
- Cost: the fit learns 91.5 s of a scored static-target task with no tag for it. The span includes frames the live
  guard rejects, which the agent would never act on.
- No code change.

**B. Cut the span (recommended).**
- A new machine cut, `timed_practice`, over the banner-measured span refined to native frames. It would enter the
  proposer beside capture gaps and other-regime spans, as an explicit list of spans with their native evidence.
  Nothing is inferred.
- seg-015 becomes two gameplay segments, 2,095.5–~2,228 s and ~2,320–2,873.9 s, and the edge rule places both new edges
  on proven frames.
- Cost: about 1.6 counted minutes, plus a small change to the intake code (`propose_segments` takes the spans, and the
  evidence step reads the banner at the brackets), with tests. The per-session independent review covers the change,
  as it did for the edge rule.
- The session goes review-ready after that, with evidence re-emitted with `--supersedes`. The seg-015 split also
  renumbers the later segments.

**C. Reject seg-015 whole** (−12.97 min). Not recommended.

A banner reader for the whole corpus (a perception change) is out of scope for this intake. The concrete need is one
span, measured by hand on the original.

**Without the span, everything else is ordinary.**
- Four deaths, all falls (at 824.7, 1,477.9, 1,660.5 and 2,092.1 s), same shape as val's; one is a black-fade respawn
  with no SPECTATING card.
- Two Tab cuts: 2,092.85 s while spectating, and 2,873.93 s before the closing Alt. The second shows the scoreboard
  (f345003).
- The focus settle at 13.88 s.
- The other 288 gameplay review frames show ordinary Galacta-bot range play.
- Provisional under B: about 45.97 counted min. Under A: 47.50.

Artefacts are in my scratchpad, `…/51f6344f-…/scratchpad/arrivals-0925/`: `sheets-203745/` (20 sheets),
`edges-203745-{a,b}.jpg` (every edge and death frame, in time order), and `timed/banner-tile.png`, with `part0-2.jpg`
as readable crops.
