# Existing training evidence separates a cast from a hit

Research inspection, 2026-09-26. No source labels, admissions, models, or current
experiments changed. No new recording, video decode, remote transfer or GPU work.

## What is now established

The admitted TRAIN-only 051828 session contains a concrete contrast relevant to
the [effect-memory proposal](memory-method-audit.md): a fresh RMB press and ammo
consumption can accompany either a visible body hit or a ground impact.

| Existing row | Logged request time | Archived visual finding | Existing training label |
|---|---:|---|---|
| n39 | 3.991753177 s | Web ammo 5 to 4; white impact on the same named Luna Snow body | `start_request` |
| n119 | 11.919736277 s | Ammo recharges 4 to 5, then drops to 4; projectile impacts the ground near Spider-Man, away from the selected distant Galacta | unknown (`null`) |

Both requests are fresh RMB rises with LMB up. These are **not matched histories**:
camera, target, distance, prior actions and resource histories differ. Both are
casts; only the first has an established body hit. The second is not evidence of
a failed cast, and its unknown request-training label must not be relabelled as
negative merely because the shot misses. The original task's label contract and
a new outcome-learning task are different.

I inspected the two existing contact sheets. They visibly support the archived
description: a burst overlaps Luna in n39; the n119 sequence shows a projectile
ending at the nearby floor while the bots remain distant. This is inspection of
saved contact sheets, not an independent native-frame audit or an outcome reader
benchmark. No hit rate or generalization claim follows from two selected cases.

## Sources and integrity

[Machine-readable receipt](attempt-effect-contrast.json) records the two source
records and six verified file hashes. The v5 manifest matches the digest recorded
in the [admission lane's v5 section](../../lanes/human-admission.md). Its status is
`admitted_train_only`; 053616 was not opened. The v5 request evidence and visual
notes match that manifest. The referenced v2 manifest matches v5's pin, and both
contact sheets match v2's manifest:

- [n39 body-hit sheet](../../../data/human/skill-event-candidates/051828-request-timing-v2/sheets/n39-cast.jpg)
- [n119 ground-impact sheet](../../../data/human/skill-event-candidates/051828-request-timing-v2/sheets/n119-cast.jpg)

The receipt is a research extraction, not a new dataset-admission receipt. The
v5 packet's candidate records retain their own provenance fields; the separately
admitted examples remain authoritative for training. All source bytes were only read.

## Causal availability is still unresolved for the new outcome task

n39 records its hit confirmation at logger time 4.174999833 s. This is later
than the request and later than ammo consumption, so even that established hit
cannot be included at the request-time policy decision.

n119's `latest_evidence_t` is 12.008332853 s, while its retrospective reason
describes ground impact around 12.16–12.28 s. The field therefore does not license
making the entire narrative available at 12.008 s. It is an existing unknown
request row, not a causal hit/miss-memory event. This is a consumer boundary for
the proposed research, not a demonstrated defect in the existing training use.

Do not parse these narratives into online state, replace the frozen timestamp,
or silently admit new labels. A later outcome study needs its own reviewed
availability time, target association and unknown handling. The existing
`perception.events.Event.known_at` convention supplies the right distinction,
but these request records do not automatically implement that new contract.

## What this changes

### Continuation check: this pair does not establish a memory advantage

The next inspection followed the same hash-verified request evidence through
n56 and n131; those source records are now included in the research receipt.
After the Luna hit, n44 is a no-new-request control, n48 includes a melee press,
and n51 is another web request at 5.142668977 s on Luna. After the ground impact,
n123/n124 remain unknown controls; n126 is another web request at 12.617647277 s
on the nearer left Galacta, followed by an approach documented at n131.

Both continuations contain another web request. Different targets, camera views,
movement and recent controls prevent attributing their different timing or
behavior to remembered hit outcome. Nor does the metadata establish that the
relevant cue was absent from the current image. This pair therefore remains a
command/cast/hit distinction example and is **not a qualifying test of memory**.
Retrospective target-continuity annotations are not automatically causal inputs.
No additional video frames were decoded in this continuation check.

### Implication for experiment selection

New recording is not needed merely to establish that equal command type and
resource consumption can lead to different hit outcomes: existing material
already demonstrates that. It motivates an effect hierarchy—command delivered,
cast evidenced, hit evidenced, designated target completed—rather than one
generic success flag. The hierarchy is an engineering requirement, not an
original research result.

The remaining experiment is more demanding: find subsequent decisions where
remembering a causally available outcome helps after its visual cue disappears,
with controls for current-frame information, target identity and prior commands.
These two visually different moments alone do not establish a need for memory.
They supply a concrete source for that inspection and an explicit timing trap to
avoid; they do not yet validate a new learner or meet the doctoral objective.
