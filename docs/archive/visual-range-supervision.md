# Visual supervision for the first range policy

Lead decision, September 22, 2026; tracked by VUH-1309 and VUH-1346.
This authorizes a small candidate annotation and independent review. It does not
admit a recording, approve a checkpoint, or change the native KBM importer.

The first policy learns when to delegate `Idle` or `Engage` to the existing
controller. Its supervision may come from visually audited human behavior without
converting raw keys or mouse counts to abilities. Unknown source motor settings
do not become known merely because this route does not use motor labels.
The proposed reconstruction-only schema expansion is parked: it would not admit
examples to any training consumer.

## Bounded source and identity

The candidate is the original `2026-09-21 22-24-54.mkv`, session
`20260922T032454-642Z-24328-1`, SHA-256
`2df73a79377e316e28f9e53947ee203dda95f949772f7fd68d1f864dbe960c51`.
Its own output configuration and bounded packet check establish applicability of
the source-derived +21/1000-second AAC/Matroska offset. Reuse the existing
3609-frame integrity result and one discarded callback-tail packet.
OBS composition timing remains an explicit assumption; game render, display,
input delivery and player-observation latency are uncalibrated.

Independent inspection confirms charge depletion and recharge countdowns before
the menu, followed by No Ability Cooldown OFF at 23.0 seconds and an activation
at 23.7 seconds. Always On remains OFF. This establishes the observed pre-menu
normal-resource behavior; it does not establish continuously unlimited resources
afterward or the later recording's settings.

Use conservative file-time bounds 11.0 through 22.25 seconds, then pin actual
decoded frame PTS. Loading/hero selection precedes this interval. Escape occurs
at 22.305231 seconds. Every five-step history and future 100 ms label interval
must fit entirely inside reviewed gameplay: nominal anchors 11.4 through 22.15
seconds. Reject boundary, focus, target and visual-response ambiguity.

The source profile records Spider-Man/range, observed resource regime, installed
client build 25364676 / version 1.1.3870120, source clock assumptions, visual
settings actually observed, and explicit unknown motor sensitivity/bindings.
James's later settings report belongs to session 033319 and cannot be backdated.
The profile's digest identifies this complete provenance document, including its
uncertainties; it is not evidence that all settings are known. If used as
`Identity.settings_sha256`, the receipt must explicitly name this visual-only
contract and exact profile. Runtime pad settings/calibration remain separate.

Both recordings belong to `james-2026-09-21-evening`, train-only for this
diagnostic. They cannot validate one another. VUH-1347 remains the independent
session requirement; no live-policy clearance follows from candidate annotation.

## Evidence required for each example

- Five causal pixel-derived `State` snapshots at the default 10 Hz, with native
  frame identity/PTS, source timing, known bits and the frozen perception and
  selector identities. Use the actual detector/selector output, including its
  failures. A human annotation of a future target must not replace causal input
  features, and missing history must not be padded.
- An inspected `(t, t+100 ms]` future showing offensive delegation to the same
  selected target, true neutral behavior, or explicit unknown/conflict. Target
  identity and gameplay context must support the controller's `Engage` meaning.
  Luna Snow's Hero Simulation is not automatically equivalent to the pilot's
  designated Galacta bot. Pull/WebStrike/burst remain outside this vocabulary.
- Native visual evidence covering body motion, target response and action
  recovery. No-button periods are locators only. Movement, swing, falling,
  retreat, recovery, menus and focus loss cannot supply `Idle` negatives.
  Inspect visible network stalls/snapping per window; network-loss telemetry is
  not recorder-loss evidence.
- Immutable source/group/segment bounds, annotation reason, evidence IDs and
  independent review receipt. Raw events may locate windows; this route assigns
  no abilities from button presence and creates no synthetic pad labels.

Report actual accepted/unknown/rejected class support before scaling. Both
classes remain required by the trainer. If no true neutral or causal target
correspondence is verified, preserve that limitation; do not manufacture a
trainable cohort by changing the vocabulary or history length.

The corpus owner prepares candidates; an independent reviewer examines the
contract, native examples and their causal feature construction before lead
admission. Ordinary native-import eligibility, independent validation and genuine
runtime/deployment binding keep their existing authorities.

---

**Archived 2026-09-23** from `docs/visual-range-supervision.md`. Everything above this line is verbatim, so line
citations such as `:62-65` still hold.

**Superseded in part (review R8, 2026-09-23).** Under whole-session behaviour cloning, a quiet bin inside accepted
genuine play is supervised "no action". That supersedes the rule above that no-button periods cannot supply `Idle`
negatives (lines 62-65), for the whole-session head only. Menus, lobby, AFK, UI-key spans and focus loss are still
never supervision, and focus snapshots stay unknown holds. Sources:
[human-admission.md, "Superseding decision (review R8)"](../lanes/human-admission.md#superseding-decision-review-r8)
and [the whole-session intake design review, R8](../evidence/whole-session-intake-20260923/review-design.md).
