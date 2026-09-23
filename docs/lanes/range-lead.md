# Range lane index

This page covers the practice-range work as it stands, plus an index of the range notes. It was rewritten on
2026-09-23 at the lead's direction. The 2026-09-22 integration diary that used to be this file is kept verbatim at
[docs/archive/range-lead-20260922.md](../archive/range-lead-20260922.md). Acceptance and results live in Linear
(VUH-1311, VUH-1319, VUH-1346, VUH-1347, VUH-1351).

## Present state (2026-09-23)

- **Direction.** Whole-session recording feeds one end-to-end policy that outputs semantic actions plus camera
  degrees, executed by the pad ([recording protocol](../recording-protocol.md), [end-to-end fit](end-to-end-fit.md)).
  The web-start timing head below proved the pipe (3 accepted starts, 3 hits in pilot 2), but it is not the product.
- **Live caller.** `python -m agent.loop --live --brain range-skill`. It takes:
  - `--game-pid <PID>`, `--max-s` in (0, 20] and `--cooldowns normal`;
  - the reviewed checkpoint's `--range-checkpoint`, `--range-sha256`, `--range-identity`, `--range-runtime` and
    `--range-deployment`;
  - `--collect-episode` (and optionally `--stop-on-feed`) for scored trials.

  Pilot 2 launched it through `data/runtime/galacta-pilot-20260923-preflight/launch_slot.ps1`. The legacy Idle/Engage
  head (`--live --brain range`) is refused by `agent/loop.py`; it stays loadable offline.
- **Checkpoint.** `698d8831`, the admitted two-session request cohort fit
  ([evidence](../evidence/range-request-cohort-fit-20260923/README.md)). Its deployment binding and the 16-file code
  freeze are under `data/runtime/galacta-pilot-20260923-preflight/`. Editing any frozen file, even whitespace, forces
  a re-freeze before the checkpoint runs again.
- **Latest result.** Galacta pilot 2 ([evidence](../evidence/galacta-pilot-20260923/README.md)) stopped at 3 of 20
  slots, because placing Spider-Man between slots needed a human. The learned near slot made 3 accepted web starts
  (+90 damage, no KO), and the scripted mid slot killed its designated bot.
  - The 2026-09-22 runs are in the [learning plan](../learning-plan.md#first-visible-learned-range-milestone-2026-09-22).
  - The evidence folders are indexed in [docs/evidence/README.md](../evidence/README.md).

## The range-skill caller contract in one place

Seven accepted notes define the live caller. Each is a frozen review packet, and together they say:

1. **Decisions** ([range-decision-timing](range-decision-timing.md)). In each fixed 100 ms phase slot, the first
   eligible source acquisition decides, within a tolerance in [0, 0.025] s. Slots are terminal, with no retry.
2. **Request expiry** ([range-request-expiry](range-request-expiry.md)). An expired request is a cancellation
   (`InputExpired`), not range loss, and observation continues. A failed neutral release or record write still
   ends play.
3. **Pulse lifetime** ([range-request-pulse-lifetime](range-request-pulse-lifetime.md), `request-start-owned-pulse-v1`).
   The pulse starts at controller acceptance A. Its nominal end is E = A + 33 ms, and its effective end H is E capped
   by the phase and session bounds. The first send must pass the locked actuator check before the request deadline D
   and before H. Delay consumes the pulse; it never restarts.
4. **Scope** ([range-owned-pulse-loop](range-owned-pulse-loop.md)). Loop and LiveIO carry `scope_not_after`, so H is
   enforced at the actuator. A return after H releases.
5. **Focus** ([range-live-focus](range-live-focus.md)). `--live --brain range-skill` requires `--game-pid` and a
   foreground proof, and a bounded runtime, before the pad attaches.
6. **Trace** ([range-failed-send-trace](range-failed-send-trace.md)). A failed or refused send still writes its
   originating decision row.
7. **Episode collection** ([range-episode-collection](range-episode-collection.md)). A native baseline board is read
   before any offense, then a fresh phase-origin frame is recorded; the phase is at most 20 s.

## Index of the range notes

**Frozen** means a review receipt or freeze manifest pins the file's current bytes. Never edit or move a frozen note,
even to fix a link; its "not yet accepted" status line is stale on purpose, because acceptance is recorded where it is
pinned (`AGENTS.md`, "Frozen review packets").

| Note | Conclusion | Acceptance / pinned by | Frozen |
|---|---|---|---|
| [range-decision-timing](range-decision-timing.md) | One decision per fixed 100 ms phase slot; slots are terminal | `evidence/range-request-runtime-20260922/scheduler-software-review.md` and two `caller-review.md` files | yes |
| [range-request-expiry](range-request-expiry.md) | An expired request cancels; it does not stop play | `evidence/range-request-expiry-20260922/README.md` | yes |
| [range-request-pulse-lifetime](range-request-pulse-lifetime.md) | `request-start-owned-pulse-v1`: the pulse is owned from controller acceptance | `evidence/range-owned-pulse-software-20260922/review-receipt.json` | yes |
| [range-owned-pulse-loop](range-owned-pulse-loop.md) | `scope_not_after` carries H to the actuator | `evidence/range-owned-pulse-software-20260922/review-receipt.json` | yes |
| [range-live-focus](range-live-focus.md) | `--game-pid` foreground proof before the pad attaches | `evidence/range-request-runtime-20260922/preflight/caller-review.md` | yes |
| [range-failed-send-trace](range-failed-send-trace.md) | Failed or refused sends keep their decision row | `evidence/range-request-runtime-20260922/failed-send-software-review.md` | yes |
| [range-episode-collection](range-episode-collection.md) | `--collect-episode`: baseline board, phase-origin frame, at most 20 s | `evidence/episode-collection-review-20260922/independent-review.md` | yes |
| [learned-range-skills](learned-range-skills.md) | API and handoff for `policy/range_skill_policy.py`: visual-onset and received-request heads | `evidence/range-request-human-fit-20260922/software-review.json` | yes |
| [range-hud-performance](range-hud-performance.md) | `_masks` computes channel minimum and morphology once per call; outputs equal, cold medians 0.7-3.7 ms faster | `evidence/range-hud-performance-20260922/README.md`; `data/diagnostics/range-hud-performance-20260922/freeze-sha256.json` | yes |
| [range-hud-countdown-performance](range-hud-countdown-performance.md) | `_countdown_char` candidate filtering vectorized; identical outputs on 23 frames. Landed in `67a7e31`; the lead records its acceptance on Linear | `evidence/range-hud-countdown-performance-20260922/freeze-sha256.json` | yes |
| [range-hud](range-hud.md) | VUH-1294: countdown ink is not "ready"; a zero badge or a positive countdown on an uncharged slot means unavailable | in the note (its final section) | no |
| [range-perception](range-perception.md) | VUH-1346 source diagnosis (the M&K layout fixes ammo, not readiness) and the VUH-1314 filled-health-strip outline repair; `outline.py` has changed since (VUH-1355) | in the note (its final section) | no |
| [range-policy-reframe](range-policy-reframe.md) | Design of the web-start event head and the `RangeSkill` controller boundary; implemented, and its direction was superseded on 2026-09-23 | implemented in `agent/intents.py` and `policy/range_skill_policy.py` | no |
| [range-skill-controller](range-skill-controller.md) | `RangeSkill` controller: independent movement and aim plus one requested Web-Cluster pulse. A fused two-bot box can't be refused by its shape (VUH-1356, 2026-09-23) | landed `33303c0` | no |
| [range-cast-probe](range-cast-probe.md) | Runbook for `scripts/range_cast_probe.py`, the scripted Web-Cluster calibration probe. Run D: 2 confirmed casts, 1 refused | `evidence/range-cast-calibration-d-20260922` | no |
| [range-benchmark](range-benchmark.md) | VUH-1319 offline encounter scorer (`agent/episodes.py`, `scripts/range_benchmark.py`). The gate is at least 8 of 10 audited designated completions within 20 s, with zero scope breaches | landed `f841527` | no |
| [learned-range](learned-range.md) | The legacy v1 Idle/Engage GRU candidate (`policy/range_policy.py`, `agent/learned_range.py`); offline only now | superseded by the event contract | no |
| [galacta-pilot](galacta-pilot.md) | Pilot 1's 20-slot schedule and pilot 2's predeclaration for `698d8831` | `data/benchmarks/galacta-pilot-2026092{2,3}/` | no (pinned at `93dc9f1`, since appended) |

Owners edit their own notes. This page is the one place that states the range work's present state; update it when
that state changes.
