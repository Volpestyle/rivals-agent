# Jev (frozen baseline)

Lead-owned. Request shape, measurements and findings for TypeSafe's Jev as a decision
layer. Frozen: see `docs/plan.md`, "Direction".

## Findings

`typesafe/jev-1.13` through OpenRouter. `decide_jev(state, memory)` has `decide`'s
signature. The scripted `gate` runs first, so retreat, holds and a flickering target
never wait on the network. Jev then makes the choice `policy` would make. A timeout,
HTTP error, unparseable answer or out-of-vocabulary answer runs `policy` for that
tick and is counted per reason (`timeout`, `http`, `parse`, `vocab`) in
`Jev.stats.fallbacks`.

**Request shape.** Jev is a "decisions" model. `POST /api/v1/chat/completions`
answers HTTP 400 (`typesafe/jev-1.13 is a decisions model and cannot be used with the
chat/completions endpoint. Use the /api/alpha/decisions endpoint instead.`), so
`tool_choice` and `response_format` never apply. What works is
`POST https://openrouter.ai/api/alpha/decisions` with `Authorization: Bearer <key>` and
TypeSafe's native body (their own endpoint is `POST https://api.typesafe.ai/v1/systemone`;
docs at `docs.typesafe.ai`, index at `/llms.txt`). `state` is a string or a JSON object;
each question is a `choice` over up to 255 named options:

```json
{"model": "typesafe/jev-1.13",
 "state": {"hp": "high", "web_ammo": 3, "ready": {"swing": true, "pull": true, "uppercut": true},
           "crosshair_on_hostile": true,
           "targets": [{"i": 0, "cls": "enemy", "range": "mid", "tagged": false, "under_crosshair": true}],
           "anchors": 0},
 "questions": {
  "intent": {"type": "choice", "instructions": "Which single intent should the Spider-Man fighter play next?",
             "criteria": {"engage": "Aim at the target, close in ...", "pull": "Get Over Here! on an UNTAGGED target ...",
                          "search": "...", "idle": "...", "disengage": "..."}},
  "target": {"type": "choice", "instructions": "Which target should that intent act on?",
             "criteria": {"0": "enemy, mid range, tag False"}}}}
```

Response (from a probe, id trimmed). Every option gets a probability, `choice` is the
most probable, `confidence` is higher the more peaked the distribution:

```json
{"model": "typesafe/jev-1.13-20260917",
 "answers": {
  "intent": {"type": "choice", "choice": "pull",
             "probabilities": {"engage": 0.12, "web_strike": 0, "disengage": 0, "pull": 0.82, "search": 0.04, "idle": 0, "burst": 0.01},
             "confidence": 0.78},
  "target": {"type": "choice", "choice": "0", "probabilities": {"0": 0.86, "1": 0.14}, "confidence": 0.71}},
 "usage": {"input_tokens": 555, "output_tokens": 99, "cost": 2.331e-05},
 "provider": "TypeSafe"}
```

Also true of the route: several questions share one request and one round trip;
errors are HTTP 400 with `error.message` (missing `state`, unknown model, a choice with
no criteria, an unknown question type); input is billed at $0.042 per million tokens
and output is free. `~typesafe/jev-latest` is not used: the model is pinned. TypeSafe's
jev-1.13 notes say it reads criteria literally and is weak at arithmetic, so the code
sends categories (range, hp bucket, tag) instead of raw numbers.

**How the choice is made.** The `intent` question offers only intents some visible
target can execute now (`jev.legal`: the kit preconditions `policy` also enforces; an
unknown ability or tag offers nothing). The target is the option Jev gave the most
probability among the targets that intent allows, so a pull is never aimed at a tagged
enemy however likely Jev thinks it. `intent`, `target` and `anchor` go in one request.

**Transport.** Standard library only. One kept-alive connection, and each call runs on
a worker thread so the caller stops waiting at the per-call deadline (`TIMEOUT_S`, 0.2 s)
even if DNS or a reply hangs. A timed-out call finishes in the background, so the next
call finds a warm connection; while it is still in flight a new call fails at once
instead of queueing. The key is read from `OPENROUTER_API_KEY` or the gitignored `.env`
and never appears in a repr, error or log.

**Measured from the dev Mac, 2026-09-20** (synthetic States, `uv run python -m agent.jev
-n 60 --timeout T --hz H`; round trip is answered calls only, so short budgets truncate it):

| Budget, pacing | Fallbacks | Round trip p50 / p95 / max | `decide_jev` wall, max |
|----------------|-----------|----------------------------|------------------------|
| 2 s, back to back, run 1 | 0 / 60 | 250 / 393 / 712 ms | 713 ms |
| 2 s, back to back, run 2 | 0 / 60 | 237 / 322 / 968 ms | 968 ms |
| 400 ms, 5 Hz | 5 / 60 (8%) | 218 / 318 / 336 ms | 414 ms |
| 200 ms, 5 Hz | 46 / 60 (77%) | 174 / 200 / 200 ms | 219 ms |

- **Jev cannot meet 100-200 ms from here.** The fastest call was 154 ms. Share of
  unbudgeted calls that answered within 150 / 200 / 250 / 300 / 500 ms: 0% /
  3-17% / 47-62% / 75-88% / 97-98%. The first call on a connection (TLS included) took
  417-536 ms. A budget near 400 ms answers about 92%. The deadline itself holds:
  `decide_jev` returned within 19 ms of it in every budgeted run. The loop runs on the
  PC, which was not measured; the same command reproduces it there.
- **Cost:** about $0.000023 per answered call (558 input tokens). Timed-out requests
  are billed too. All probes and five 60-call runs (about 340 requests) cost roughly
  $0.007.
- **Agreement with the scripted brain:** 62-65% of answered ticks by intent kind. In
  run 2 the differences were scripted `engage` -> Jev `burst` (13, at near range,
  where the burst is legal) and scripted `swing_to` -> Jev `engage` (8). The scripted
  brain is a heuristic, not ground truth: nothing here measures which is better.
- **Shape of a fit:** a blocking call suits a budget of about 400 ms, two to four ticks.
  Holds last 0.8-3 s and the gate stays scripted, so a non-blocking variant (request in
  the background, adopt the answer when it lands and is fresh) suits the loop better.
  It is not built.
