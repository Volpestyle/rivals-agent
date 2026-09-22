# Independent bounded native audit ? VUH-1346 first human-model runtime

Read-only review, 2026-09-22. Scope: the single preserved run range-request-diagnostic-20260922-1, its preflight/deployment records and bounded native video. No model loading, inference, human corpus, new capture/input, production changes or status writes. Unchanged software/primitive proofs reused.

## Outcome

One independently confirmed Web-Cluster cast hits the visible Luna Snow Hero Simulation target. Web ammo goes from 5 to 4; the shot is followed by a web marker, hit reaction and a health bar with a depleted segment. Luna remains standing. This establishes one exploratory learned-request-to-guarded-pulse-to-visible-hit occurrence, with scripted target selection/approach/aim and pulse execution. It establishes neither a KO nor human-quality behavior, success rate, generalization or a completed 10-second evaluation.

No receipt mismatch or new evidence blocker found. Retain the failed second request and the trace limitation below; do not collapse returned API calls into distinct casts.

## Distinct counts and attribution

- Metadata: 8.615-second learned phase, 84 decisions, 369 normal tick rows plus 2 terminal release rows.
- 83 unique persisted decision traces: 15 model start proposals, 29 model no-new-start proposals, 39 refusals (31 warming_up, 6 invalid_history, 1 target_unobserved, 1 low_confidence).
- Final ID 84 lacks its normal decision/probability row because send failure occurs before that row is written. Its owned terminal pulse proves a further accepted start request under the accepted executor contract. Therefore 16 starts are evidenced in total, but only 15 have complete persisted model proposal traces. Do not claim ID 84's exact model probability or original resource object was preserved.
- Two Controller-owned accepted requests: ID 75 directly in the normal acceptance trace; ID 84 through terminal pulse ownership. Counting only accepted:true normal rows incorrectly yields one.
- Two returned LT-down calls, both continuing the SAME ID 75 pulse; one failed guarded send for ID 84. The same failed-send object is referenced by both terminal rows and is not two failures.
- Zero RT or offensive button reports in the normal learned-phase rows. One visible cast and one visible target hit in the bounded native sequence.

## Original clocks and the returned pulse

ID 75: decision/resource observation 14.17610829998739, webs 5, start probability 0.9953083395957947, target ID 1, expiry 14.27610829998739. The later reflex observation is 14.224710799986497 and Controller execution is 14.24169919997803. Resources retain their original clock; expiry is exactly original observation + 100 ms. Pulse press-until is 14.274699199978029.

First LT attempt 14.241902199981268, return 14.243093899975065, not-after 14.24310829998739. Continuation attempt 14.269473599997582, return 14.270714299986139, not-after/release-at 14.274699199978029. The next recorded send is LT=0 at 14.290274299972225, returned 14.292633399978513, with ID 75 cancelled_after_press. These are API/loop clock observations, not physical LT edge measurements.

## Why the run stopped

ID 84 was owned for target 1, with pulse press-until 15.169202899971976 and valid-until 15.170279799983836. Its send was attempted at 15.136467799980892 with not-after 15.137279799983837; it failed at 15.137805899983505 with exactly: RangeLost('guarded input deadline expired after proof; input released'). The proof crossed the full-press send deadline. This was before the overall authorization deadline 23.47643739997875. The specific evidence indicates neither global budget expiry nor focus/range-HUD loss. The broad metadata stop name range_lost should not be described as visual range disappearance.

The first terminal record truncates owner 84 and its neutral release returns at 15.137881599977845. The subsequent range_lost cleanup release returns at 15.138839699997334. ID 84 has no returned LT call and no independently observed second cast. Successful release APIs do not measure physical device timing.

## Native evidence and synchronization limits

Original learned-native.mp4: 2560x1440, 60 seconds, 3573 frames. Inspected bounded coarse samples at 2 fps over approximately video PTS 10?23.5 seconds, plus all 142 extracted native frames from PTS 18.8 through 21.1833333333. Original PTS retained from ffmpeg showinfo; dense-index.json gives each frame. Full frame key sheet and all six dense crop sheets inspected; saved run frames 000069 and 000071 also inspected.

Ammo remains 5 at PTS 19.3166666667 and becomes 4 at 19.3333333333. A clear white web emission appears at 19.3500000000, absent at 19.3333333333: recorded-video emission bracket (19.3333333333, 19.3500000000]. The hit/marker/depleted health segment is clear by 19.4833333333. No second launch appears in the dense interval. Later PAD-to-KBM HUD change moves the ammo layout; the infinity symbol in the fixed crop must not be interpreted as a web refill.

Eleven saved-frame center-image comparisons (000066?000076) find nearest video frames with PTS minus original observation times spanning 4.9617864334?4.9855658334 seconds. Examples: 000069 / observation 14.2247108 matches PTS 19.2; 000071 / observation 14.4602873 matches PTS 19.4333333. correspondence.json retains distances and times. This is empirical image correspondence with adjacent-frame ambiguity, not a calibrated render-clock transform, exact game time, input-to-photon measurement or a new primitive latency calibration. Recorder wall/perf brackets alone are not exact alignment.

## Artifact and scope join

The actual meta source identity, runtime identity and deployment binding exactly equal the preflight originals. Canonical source identity digest was independently recomputed; manifest/review hashes join exactly. Controller and perception deployed files were independently hashed and agree with their manifests and accepted main bytes after the documented CRLF normalization. Selector pin remains original. Actual source/runtime/deployment objects are reproduced below without loading the checkpoint.

Binding-consumed record and launch retain the exact model/binding/run; one learned launch, no retry. Loader preflight reports reviewed_human, confidence 0.7 and zero inference calls. Original model bytes were not read or loaded during this audit. The recorded invocation requests 10 seconds; camera startup plus phase has a single 24-second authorization budget. No scoreboard/keepalive occurred. The 60-second recording duration does not expand control authority.

Independently inspected existing ps-0.jpg shows No Ability Cooldown X/off; settings-11p8s.png shows native PAD LT web ammo 5 and RT infinity, consistent with the effective-setup receipt. The native run itself identifies Luna and shows ammo depletion. These observations do not establish every latent motor/server setting.

## SHA-256 pins

- `data\l1\range-request-diagnostic-20260922-1\meta.json`: `4d50f241fd42c653e39b8aad4c72a9bb8eb6669160495f5aecb22795ec58b613`
- `data\l1\range-request-diagnostic-20260922-1\frames.jsonl`: `f735585c44b1657569da4a4a2447c3b5605f12411728cc122f1618287ace47ec`
- `data\runtime\range-request-preflight-20260922\learned-native.mp4`: `05545fd867cf8947b427dfafed8ab5455a020e37a6a7091b13649c30fc9ce960`
- `data\runtime\range-request-preflight-20260922\deployment-binding.json`: `25127cfe9fc9c39cad11029bc0018a3039970573c72e2f111f7b4fa13da4b859`
- `data\runtime\range-request-preflight-20260922\controller-deployed.json`: `463cc91f5aa9e2363f2bb0ab7e6c41cc20e83bfb0258a652c680b59b59ea75b3`
- `data\runtime\range-request-preflight-20260922\perception-deployed.json`: `eec81481931085a547b677d6a1be8bb1787ba5a41a974b59079de8cfd0805c24`
- `data\runtime\range-request-preflight-20260922\effective-setup.json`: `a28efd61ea2d9d1f8ea0af91adc47e81646e48471c49267c95ca6270dced2631`
- `data\runtime\range-request-preflight-20260922\runtime-settings.json`: `086c29d8113d1a027540ea5b3a71308e0b9ba137419806dd861ca18c277ce8ff`
- `data\runtime\range-request-preflight-20260922\runtime-semantic-review.json`: `1b370c7c851fb24f046ccc15346d345a1f11392d40134b1bf5d32c6b4c4d1426`
- `data\runtime\range-request-preflight-20260922\deployment-review.json`: `8ac0f800139ee0d091647c120b441cdce728beaa3f9af68ad9d5cdd9deaeba33`

## Actual source/runtime/deployment receipt

```json
{
  "checkpoint_sha256": "6ee388070599e3df042ea73876e391340bf228a9e626cc212c60875d8191aeef",
  "source_identity": {
    "patch": "1.1.3870120/build25364676",
    "cooldown_regime": "normal",
    "source_profile_sha256": "9f413b81dabc71518359c28a6e506b1a1accbae5654bbf006967652332e3208f",
    "perception_sha256": "e9d40f7a12442335866df16edaa8ceea7116177ab8546b3267ac096c1c616798",
    "selector_sha256": "ddf1428a61c54805ce06164ef0daa7dfa1302fdf1735990336fdcab939ae098d",
    "semantic_revision": "web-cluster-request-v1",
    "feature_revision": "masked-state-grid-causal-v1"
  },
  "runtime": {
    "patch": "1.1.3870120/build25364676",
    "cooldown_regime": "normal",
    "runtime_settings_sha256": "086c29d8113d1a027540ea5b3a71308e0b9ba137419806dd861ca18c277ce8ff",
    "calibration_sha256": "7e1ab360fcf5fe074160a1b8a0564554249b77315fb72648642ec609d5b1f1d5",
    "controller_code_sha256": "463cc91f5aa9e2363f2bb0ab7e6c41cc20e83bfb0258a652c680b59b59ea75b3",
    "perception_sha256": "eec81481931085a547b677d6a1be8bb1787ba5a41a974b59079de8cfd0805c24",
    "semantic_review_sha256": "1b370c7c851fb24f046ccc15346d345a1f11392d40134b1bf5d32c6b4c4d1426",
    "input_domain": "virtual_pad",
    "selector_sha256": "ddf1428a61c54805ce06164ef0daa7dfa1302fdf1735990336fdcab939ae098d",
    "semantic_revision": "web-cluster-request-v1",
    "feature_revision": "masked-state-grid-causal-v1"
  },
  "deployment": {
    "checkpoint_sha256": "6ee388070599e3df042ea73876e391340bf228a9e626cc212c60875d8191aeef",
    "source_identity_sha256": "082535863ad7773de498b872eccbacc21753da99966f2f64ff953d1871c5995e",
    "runtime": {
      "patch": "1.1.3870120/build25364676",
      "cooldown_regime": "normal",
      "runtime_settings_sha256": "086c29d8113d1a027540ea5b3a71308e0b9ba137419806dd861ca18c277ce8ff",
      "calibration_sha256": "7e1ab360fcf5fe074160a1b8a0564554249b77315fb72648642ec609d5b1f1d5",
      "controller_code_sha256": "463cc91f5aa9e2363f2bb0ab7e6c41cc20e83bfb0258a652c680b59b59ea75b3",
      "perception_sha256": "eec81481931085a547b677d6a1be8bb1787ba5a41a974b59079de8cfd0805c24",
      "semantic_review_sha256": "1b370c7c851fb24f046ccc15346d345a1f11392d40134b1bf5d32c6b4c4d1426",
      "input_domain": "virtual_pad",
      "selector_sha256": "ddf1428a61c54805ce06164ef0daa7dfa1302fdf1735990336fdcab939ae098d",
      "semantic_revision": "web-cluster-request-v1",
      "feature_revision": "masked-state-grid-causal-v1"
    },
    "review_sha256": "8ac0f800139ee0d091647c120b441cdce728beaa3f9af68ad9d5cdd9deaeba33"
  },
  "origin": "reviewed_human",
  "scope": "learned_web_start_timing_scripted_target_aim_movement_pulse"
}
```
