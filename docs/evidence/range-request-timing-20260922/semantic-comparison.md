# Web-start source/runtime semantic comparison

2026-09-22. VUH-1346/VUH-1347. **Decision recommendation:** retain D as accepted
evidence that one owned LT pulse can produce one Web-Cluster cast on the reviewed
target. It supports a narrow ability-identity/executor review. It does **not**
establish that requesting a pulse now reproduces the human label's visible onset
within the next 100 ms. Review that timing interpretation explicitly; do not
silently shift labels, extend deadlines, change the checkpoint or fabricate a
runtime profile. No additional generic motor-settings completeness gate is needed.

This report reads accepted reports and code as text only. It issues no
RuntimeIdentity, DeploymentBinding, admission or review receipt. The current
checkpoint/shadow and native D audit remain unchanged. No media decode, runtime
imports, input, inference, training or raw human-input inspection occurred.

## Measured timing, with the retained uncertainty

Inputs are the accepted `audit-results.json` and `execution-diagnosis.json` under
`docs/evidence/range-cast-calibration-d-20260922/`. D's visual relation is
`video PTS ≈ acquisition-clock coordinate + offset`. The 23-match median is
4.249945300 s; the **one-frame-expanded empirical envelope** is
[4.221443733, 4.275683767] s. It is neither a guaranteed bound nor a confidence
interval or physical-input clock.

For emission bracket `(Elo,Ehi]` and reference `r`, the broad elapsed envelope is
`(Elo - offset_hi - r, Ehi - offset_lo - r]`. All milliseconds below follow that
same arithmetic. `calculation.py` uses only stdlib/report reads; `results.json`
retains full precision, equations, report hashes and code comparisons.

| Owned request | Native emission PTS bracket (s) | Acquisition → first LT attempt | Acquisition → emission, median-offset bracket | Acquisition → emission, broad envelope |
| --- | --- | ---: | ---: | ---: |
| 13 | (11.916667, 11.933333] | 40.602 ms | (153.810, 170.477] ms | (128.071, 198.978] ms |
| 28 | (13.450000, 13.466667] | 52.150 ms | (160.592, 177.259] ms | (134.854, 205.760] ms |

| Reference to visible emission | Request 13, median-offset bracket | Request 13, broad envelope | Request 28, median-offset bracket | Request 28, broad envelope |
| --- | ---: | ---: | ---: | ---: |
| First LT API attempt | (113.208, 129.874] ms | (87.469, 158.376] ms | (108.442, 125.108] ms | (82.703, 153.610] ms |
| First LT API return | (111.889, 128.556] ms | (86.151, 157.058] ms | (107.232, 123.899] ms | (81.494, 152.401] ms |

The median-offset send calculation exceeds 100 ms, but both broad send envelopes
include values below 100 ms. **Do not claim a proven >100 ms send-to-emission
delay or physical latency.** API attempt/return timestamps bracket software calls,
not physical input consumption. Watchdog release is not a measured physical
button-up time. Only two accepted casts were measured.

Within this empirical mapping, both visible emissions fall beyond acquisition
+100 ms: by (28.071,98.978] ms and (34.854,105.760] ms respectively. This is evidence
against assuming next-bin visible response in D, conditional on the visual
envelope; it is not a calibrated worst-case guarantee. Request 28's actual probe
deadline was additionally clipped to 9.128667 s, about 10.796 ms earlier than its
acquisition+100 ms. `results.json` distinguishes that probe deadline from the
ordinary learned consumer's acquisition+100 ms deadline.

Accepted native facts remain: two distinct casts/impacts on Luna, one per owned
pulse 13/28; four LT write calls do not mean four casts. Request 43 was refused
for insufficient press time, with zero LT sends and no observed launch in its
inspected interval. These are bounded observations, not a universal reliability
estimate or designated-Galacta result.

## What the two temporal meanings actually are

| Boundary | Current meaning |
| --- | --- |
| Human event label | `web-cluster-onset-v1`: reviewed visible onset bracket wholly inside `(grid_anchor, grid_anchor+.1]`, from five causal snapshots at/before their ticks. It does not assert a physical press at the anchor. |
| Model output | Probability of `start` versus `no_new_start` under that visual event supervision. Unknown labels were not negatives. This is not a learned raw-input timestamp. |
| Learned consumer | At actual acquisition anchor `State.t`, confidence-qualified `start` requests a new pulse immediately, valid until `State.t+.1`, carrying original ammo/time. No scheduling to a predicted emission timestamp. |
| Controller | One fresh request is accepted or terminally rejected by current target/aim/resources/busy/deadline guards. The nominal 33 ms LT press must fit before expiry. Deadline authorizes software input; it does not guarantee an emitted projectile before expiry. |

The current bridge is **visual-onset forecast → immediate guarded web request**.
It may react to a visible pre-emission phase that occurs after the human already
pressed; whether that happens for n142/n199 belongs to human-admission's pending
raw-press comparison. No conclusion about those press times is made here.
Controller .34 s spacing and aim/resource rejection likewise mean a model proposal
is not a delivered cast. The accepted shadow's five proposals were never sent.

One-pulse/one-cast evidence is sufficient for the narrow primitive identity
mapping, with the measured limits. It is insufficient for claiming learned
physical press timing or exact same-horizon visible realization. Root can retain
the original checkpoint as a **forecast-conditioned trigger experiment**, provided
the semantic review explicitly states this limited interpretation and timing is
evaluated separately; that does not rename/relabel its outputs or establish live
approval. If root instead requires human-equivalent command onset or emission
inside the original forecast bin, it needs an explicit **versioned action-time
interpretation** grounded in source press-versus-onset and runtime timing evidence.
That could require different supervision/alignment, but these two uncertain
samples do not yet justify a fixed correction, threshold change or retraining.
Keep that architecture decision open until the already assigned source timing
measurement arrives; do not block the accepted motor mapping or first fit.

## Exact identity inputs and meaningful differences

Full hashes and byte/line-ending comparisons are in `results.json`.

| Input | Source/training authority | Runtime/D evidence and boundary |
| --- | --- | --- |
| Client/resource regime | `1.1.3870120/build25364676`, `normal`; original profile `05f85d97...789162` | Current persisted client matches the same version/build. D's original metadata remains unverified-patch; its independently observed No Ability Cooldown off/depletion supports normal-resource D. Do not backdate the later profile. |
| Perception identity | `e9d40f7a12442335866df16edaa8ceea7116177ab8546b3267ac096c1c616798`; source-owned mapped MK HUD plus accepted outline/history extraction | D pins HUD `c34e9d07...df4661` and outline `fded81b1...cd4f8`; current files differ only by CRLF from those deployed hashes. Runtime uses PAD HUD, tracked aim crop with full-frame fallback and current tag reader. The source aggregate hash is not a runtime file hash. |
| Selector identity | `ddf1428a61c54805ce06164ef0daa7dfa1302fdf1735990336fdcab939ae098d`; reviewed source target correspondence, fresh Tracker/Memory per window | Actual shadow used `agent/brain.py` bytes `0deaafb7...b30c00`, fresh episode Memory and continuous recorded tracks. Current tracker bytes are `56fa3012...2c892`. Same function names/code do not establish equivalence between window-reset and continuous selection. IDs are local, not source-to-runtime entity identities. |
| Features/semantics | `masked-state-grid-causal-v1`, `web-cluster-onset-v1`; five snapshots, .1 s period, .025 s tolerance, confidence .7 | Same fixed extractor `range_policy.py` hash `c46e7d8a...3410bb`, same frozen dimensions/scaling/masks. Source State LF hash `7ee6b826...7c149` equals current State after CRLF normalization. Grid-to-actual-acquisition sampling assumption remains explicit. |
| Consumer/executor | No human mouse-to-pad conversion | Shadow consumer `77e4b7f1...5c89ba`; current controller/loop/intents LF-normalized bytes equal the D deployed receipt (`268527c0...e678c43`, `c345ec61...c2e5c3`, `836692b7...f50cf3`). Existing code/native review can be reused. |

The actual model consumes 13 value/known pairs: hp fraction, web ammo,
pull/uppercut/swing readiness, on-target, detector-known, selected-target-known,
target x/y/height, optional distance and tag. This single-output head still uses
those other features; they cannot be declared irrelevant without evidence.
`feature_row` normalizes positions by actual frame size and scales resources;
unknown remains masked. It never converts mouse counts into pad axes.

The source MK profile uses right-side web ammo and inverse badge appearance, with
visually identified uppercut at x=.8348 and pull/get-over-here at x=.8723.
Runtime `hud.read(frame)` defaults to PAD. `default_perception` uses native frame
size, a 960 px aim crop at 1440p, full-frame fallback, tracking and `read_tagged`.
Pin the **layout/slot mapping, crop/scale, readers, tracker, selector settings and
reset cadence**, not merely the module names. Existing accepted mappings and
native proofs are reusable; no new extraction was performed here.

The allowed reports carry the exact source perception/selector aggregate hashes
but do not expose their complete hash-construction manifests. I have not guessed
their composition or minted replacement hashes. Root/admission should reuse the
existing manifest recipe to map its constituent code/config pins to the runtime
inputs above. In particular, the existing deployment validator requires the
source/runtime selector hash to agree: copying `ddf1428a...` without establishing
the same scoped inputs would not be evidence. Runtime perception may legitimately
have a distinct hash for PAD; its semantic mapping needs explicit review.

## Minimum settings relevant to this head

Current profile SHA-256 is exactly
`26b48957c1c8cfaa2f9ab846ef097183786f5f7f879926106066de6a6e3575c9`,
collected at `2026-09-22T19:57:49.725165+00:00`, **after D**. It records persisted
values, not all active in-memory values or absent defaults.

| Relevant area | What exists | Minimal remaining boundary |
| --- | --- | --- |
| Web binding and pulse behavior | D's owned LT pulses produced one observed web cast each, normal depletion and impacts. No declared gamepad remap keys are saved. | Reuse D's narrow binding proof. Absence of mapping keys is not proof of every default; future runtime must identify unchanged effective LT/web mapping and calibrated executor, not demand complete KBM bindings/DPI. |
| Resource/client behavior | Matching currently installed build; D observed normal cooldown menu and depletion. | Preserve current-versus-D chronology. Saved `NoCDSaved_raw=0` is uninterpreted; do not replace visual regime evidence with a guessed encoding or infer a server hotfix identity. |
| Scripted aim/approach | Persisted horizontal sensitivity 265, curve enum 3, aim-assist intensity 0, aim-assist type enum 0. D achieved two target hits with its reviewed code. | Pin the actual aim calibration/settings used by the eventual bounded runtime. Missing vertical/deadzone/default fields stay unknown; a same-scenario measured aiming result can support bounded use without a full-motor reconstruction. Raw enum values do not name an unverified curve or assist mode. |
| Pixel/HUD/target observations | Saved 2560x1440, fullscreen-mode enum 1, dynamic resolution True; D native output was 2560x1440. Saved enemy-color enum 9. Accepted MK/PAD and green-body detection evidence exist. | Keep actual frame dimensions/layout/readiness mapping, crop policy and enemy-channel evidence pinned. Do not infer color from enum 9 or assume constant internal render resolution. Pixel checks concern features, not human motor settings. |

Hero-specific saved swing/hold/wall-run settings are retained in the original
profile but are not prerequisites to the web-only primitive mapping. They would
matter to a changed movement/ability scope; this head does not claim learned
swing, route or teammate support. No new blanket setting-completeness demand.

## Smallest remaining agent-owned work for root's decision

1. **Use the already assigned source measurement:** human-admission reports raw
   press relative to the two accepted visual onsets/anchors. This lane neither
   reads those files nor repeats that work. It resolves whether current features
   precede initiation or already observe post-input animation.
2. **Finish scoped identity reconciliation:** reuse accepted source manifests and
   D/current code pins to identify exact PAD layout/readiness, crop/tracking and
   selector inputs, and tie the eventual run to a contemporaneous settings/code
   snapshot. This is agent-owned configuration evidence, not new human footage.
   The post-D saved profile cannot retrospectively complete D's runtime identity.
3. **Only if root needs a quantitative timing guarantee:** collect a bounded,
   same-clock acquisition/send/visible-onset measurement with its actual mapping
   uncertainty and effective current profile. D already supplies empirical
   intervals, so do not repeat cast identity review merely to fill a checklist.
   Current send uncertainty straddles 100 ms; do not choose a compensation from
   its median. Exact physical latency is not established or required to retain
   the narrow motor mapping.

Independent human validation remains required for accepted live reliance. This
comparison neither adds a new review framework nor treats the possible temporal
mismatch as a reason to halt the accepted first fit/native audit. Root owns the
final forecast-trigger versus action-time architecture and eventual binding.

Reproduction (arithmetic only; refuses to overwrite existing results):

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
uv run --offline --no-project python data/runtime/range-skill-candidate-20260922/calculation.py
```
