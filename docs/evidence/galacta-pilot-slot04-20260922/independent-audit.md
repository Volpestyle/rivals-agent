# Independent native/evidence audit ? Galacta pilot slot 04

Run: `galacta-pilot-20260922-04-learned`, scheduled pair02 mid/learned. Review date: 2026-09-22 local. Read-only audit; only temporary extracts/report written. Root owns admission, archive and status. Accepted software e5511c5 is reused, not re-reviewed.

## Result and recommendation

The native evidence supports the intended right/stair-side Galacta setup and **mid** first-phase bin, with the existing qualitative-health qualification. The bot is alive in all inspected phase and terminal-context samples. No cast, hit, KO, death, respawn or kill-feed event was observed in that bounded coverage. All logged returned control calls carry zero LT/RT and no buttons. The learned model proposed only `no_new_start`; this is not a run in which offensive model starts were repeatedly rejected by the executor.

Retain the scheduled allocation and its actual stop: **`range_lost`, phase-deadline guard interruption**. Do not change it to `max_time`, an accepted completed 20-second timeout, or `episode_complete`. The last observation is at phase age 19.995374 s; the subsequent send guard runs at 20.007566 s and refuses the camera-only proposal. This is affirmative evidence of the phase scope deadline, not evidence that range HUD or foreground focus disappeared. There is no terminal scoreboard, so terminal counters and a scoreboard KO/damage delta remain unknown. No setup-failure evidence was found; first-phase readiness and the terminal guard stop are separate facts. No new gate, rerun or code repair is requested by this evidence audit.

## Readiness and designated target

`episode-first-phase.png` and the first State belong to actual acquisition t=8.35685559999547. The two similarly named Galactas are spatially distinct. The designated one is the right-hand bot beside the courtyard stairs and railing. The approach samples preserve this identity through scene geometry, rather than relying on the shared name or tracker ID alone. Logged selected target IDs are only 1 or null; native samples continue to show the same stair-side bot after approaching it.

The actual first State bbox is [1119,501,1295,680] on 2560x1440: height 179/1440=0.1243055556, within the existing mid band. The earlier scout height 181/1440 was not substituted. The bot is name-only, with no visible prior damage bar. Root's fresh third-entry/no-prior-offense provenance, the zero baseline, and the inspected undamaged appearance support qualitative initial full health. Numeric bot HP/max HP and movement-menu configuration remain unknown. It hovers in place in inspected samples; that is not a certified movement setting.

Own HUD at phase start shows 250/250 HP, web ammo 5, swing 3 and uppercut 2, with PAD prompts. The authorized entry3 practice-settings image independently shows No Ability Cooldown and Friendly Fire both X/off. All 199 logged full States report own HP 250 and webs 5. Sampled native HUD remains consistent, including the final saved image.

The baseline scoreboard is visibly open and zero for KOs/deaths/assists and displayed damage/accuracy/other counters. Its original acquisition interval is [8.246444899996277,8.252998999989359], captured_t at the upper endpoint. Legacy t=7.239 is the prehold time, not the acquisition. A fresh first-phase frame follows at 8.35685559999547. `readiness_accepted` and `designated_completion` remain null in the original collection metadata; this report does not mutate them. There is only one board, the baseline.

## Independent recount and terminal attribution

`frames.jsonl` has 1,101 rows: 1,097 normal returned control calls, one not-sent failure record, and three returned release records. There are 199 full decision traces with 199 unique IDs: 194 `model_event/no_new_start`, four `warming_up`, one initial `target_unobserved`. There are zero model start proposals, zero Controller acceptances, zero owned pulses and zero returned LT/RT/button calls. Normal movement and camera output is scripted execution, not learned movement. Repeated reflex use of a decision is not another model proposal.

The reflex trace separately includes 502 `decision_expired`, 64 `target_missing_or_ambiguous`, 182 `no_new_start` and 320 `duplicate_no_new_start` reasons (plus initial rows without that trace and terminal releases). These executor states do not turn the 194 no-new proposals into attempted attacks. No offense was inherited. The original meta lists errors=[] and range_gaps=[].

Original phase origin is 8.35685559999547 and phase cap 28.35685559999547. The separately pinned startup/session cap is 33.664403700007824 loop seconds: original perf origin 199373.163642, absolute not_after_perf 199406.8280457, declared 14 s startup plus 20 s phase within 34 s from open. It was not restarted by baseline or phase entry.

The terminal row reuses decision 199, whose original observation/resources are t=28.272007199993823 and valid_until=28.372007199993824. The latest reflex observation is 28.35222940001404. Controller step executes at 28.36430939999991 with `duplicate_no_new_start`, no owned pulse, LT/RT zero and only proposed rx=-0.0543812751766609. The guard checks at 28.364422000013292 against the earlier phase cap 28.35685559999547 and returns `not_sent`, reason `scope_deadline_or_invalid_clock`. The finite clocks and exceeded phase cap resolve which branch applies: deadline. The request's own validity had not yet ended; no start request was present anyway.

Neutral release for `scope_deadline` returns at 28.3645370999875; final `range_lost` release returns at 28.366785999998683. The third returned release was the pre-baseline scoreboard release at 7.2445811000070535. Failure appears once in frames and once as its exact metadata mirror, not two failures. The entire four-event metadata list equals the original event rows. `not_sent` is not a delivered report and has no delivered-pad field. The process exit code 0 does not certify episode completion.

## Bounded original-video interpretation

Recorder PID 13076 was absent before hashing/decoding. ffprobe independently reports finalized original 60.000000 s, 2560x1440, 3,584 encoded frames. Only the 9?32 s window was sampled at 2 Hz (46 images, approximately 9.0?31.5 s), covering baseline/actual phase and short terminal context. Two moving approach correspondences were additionally sampled from 11.5?13.3 s at 10 Hz. This was not a whole-video review.

Saved `000012.jpg` at loop 9.680179 resembles video near 11.9 s; saved `000018.jpg` at loop 10.335151 resembles video near 12.6 s. Both show changing player/scene geometry. These support a rough video-minus-loop offset around +2.2 to +2.3 s; use approximately +2.1 to +2.4 s only for locating coverage, not as a calibrated uncertainty guarantee. The phase is therefore approximately video 10.5?30.8 s. Stationary tail poses were not used as synchronization anchors. Recorder launch brackets are not game-render timestamps; separate capture paths, resampling and native rendering prevent exact event-time mapping.

The bounded sequence shows running toward the right stair bot, then standing near it through the remainder. The bot stays visibly alive/name-only. No offensive animation/emission, damage reaction, kill feed or disappearance/respawn was observed in the selected samples. Web ammo is five and own HP 250 throughout visible sampled HUD. Saved `000183.jpg` at loop 28.292250 independently shows that same live bot immediately before the terminal tick. Around video 31 s, after the approximate phase end, a device-switch banner/KBM layout appears while the bot remains alive. This later context is not evidence of an in-phase focus/range loss. A finite sample cannot exclude every short transient between frames; the no-offense command trace corroborates the bounded negative visual finding. No zero terminal-counter reading is invented.

## Receipt and deployed-byte join

The exact source identity, runtime identity and deployment binding objects in meta equal their supplied JSON objects. The source identity's canonical sorted compact JSON SHA256 matches the binding (canonical object hash, not pretty-printed file hash). Runtime settings, controller/perception manifests, semantic-review receipt and deployment-review receipt hash links match. Binding-consumed identifies this one run and binding. Launcher scope is max-s20, collect-episode and stop-on-feed with PID48460. Loader receipt records unchanged checkpoint SHA256 6ee388070599e3df042ea73876e391340bf228a9e626cc212c60875d8191aeef, confidence .7, origin reviewed_human and zero preflight inference. No checkpoint contents were opened during this audit. Actual thread receipt says 24 intra-op/24 inter-op before and after, unmodified.

All 20 manifest entries (15 distinct paths, with shared dependencies listed in both manifests) match current deployed raw bytes and LF-normalized accepted e5511c5 git bytes. Hash-only comparison was used without imports or a new software audit. Selector/source pins are retained. The numerical fit and this one scheduled observation establish no independent policy quality or completed paired benchmark.

## Archive

Archive this entire temporary directory verbatim. `independent-counts.json`, `receipt-code-checks.json`, `moving-correspondence.json`, `video-info.json`, original before/after hash inventories and the selected evidence accompany this report. `contact-1.jpg` through `contact-4.jpg` show the bounded 2 Hz samples; the two `match-*.jpg` show moving correspondences. `selected/` contains copies of the phase/baseline and six named saved images plus sampled original-video frames. Image labels are approximate sampling locations, not exact game clocks.

All 48 inventoried originals/selected native sources match before and after. No original was altered. Full SHA256 inventory is retained in the JSON files; key pins follow.

| Original | SHA256 |
|---|---|
| `data\l1\galacta-pilot-20260922-04-learned\meta.json` | `7418db6db7aa0c7ae71fcb9012e5f322810d43070ab183dc0e5202326d2f19ca` |
| `data\l1\galacta-pilot-20260922-04-learned\episode-first-phase.png` | `d10e1041f71a7879785337e763352a208fc94b5f10ea1032581ad202f0c5dfb8` |
| `data\l1\galacta-pilot-20260922-04-learned\scoreboard-baseline.png` | `b5ad122feb47e648db3c0663ecfcb9115063dfdefd80f17d09f3299c7e1ba852` |
| `data\l1\galacta-pilot-20260922-04-learned\frames.jsonl` | `1eadcb5efba274883e103ebfae5e5f62c4f720008c75c3ea5ec226baf9e071a6` |
| `data\runtime\galacta-pilot-20260922-04-preflight\controller-deployed.json` | `20b3327fa7e2465fca5aa275f8910ed7040972a3a45a040e8ec7fdfd63a7a04d` |
| `data\runtime\galacta-pilot-20260922-04-preflight\deployment-binding.json` | `06c94ab8bff5b9eb0aacf83df4e5b700cfef4927b75382d20ca62d0249e686de` |
| `data\runtime\galacta-pilot-20260922-04-preflight\perception-deployed.json` | `7a796b7892f148060440e2b62ea5355331411b3198cb579a8cb8c58c67b46235` |
| `data\runtime\galacta-pilot-20260922-04-preflight\runtime-semantic-review.json` | `50091d7acc11c5b87de42dc66c724f1497a4753c84a8033ce9db09ba6971bd7f` |
| `data\runtime\galacta-pilot-20260922-04-preflight\learned-native.mp4` | `e7f9fed039156a289fa303dc87e29be721b0ac9efa8383ef03bebd35eaa975ac` |
| `data\l1\galacta-pilot-20260922-04-learned\000183.jpg` | `5d4a01ef79f68a0339f778d98a56fc30aa6b4e7d15c0c75742fb8a4142251d13` |
