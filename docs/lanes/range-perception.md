# VUH-1346 source perception diagnosis — 2026-09-22

Current delivery: the [bounded VUH-1314 repair](#bounded-vuh-1314-repair-awaiting-independent-review)
below is implemented; its [evidence-ownership review fixes](#evidence-ownership-review-delta)
are now ready for the same admission-review owner and root integration. The
initial diagnosis below remains a historical record;
its original script, report and image artifacts are unchanged.

Read-only findings for root adjudication, linked to existing VUH-1294 (HUD) and
VUH-1314 (tracking). This does not reopen the accepted range policy. No production
changes, labels, admission decisions, imports, training, pad creation, input or
capture. Human-admission remains the candidate owner.

The smallest defensible source profile uses existing `hud.MK` and a separately
constructed `Layout` with visually identified slot positions. That fixes source
ammo and semantic identity, but **does not fix readiness**. Target disagreement
also has a measured detection/history chain; neither color switching nor simply
changing selector preference is sufficient.

## Scope and artifacts

Only the four authorized windows under
`data/human/semantic-candidates/20260922T032454-642Z-24328-1/` were inspected:
`candidate-{13521,19821,20021,21921}-{history.jpg,future.jpg,anchor-overlay.png}`,
`candidate-rows.json`, and their referenced history native frames. These are
diagnostic evidence, not admitted demonstrations. All 12 overview/overlay images
were visually inspected. Only 17 unique causal history frames were loaded for
computation: 13121–13521, 19421–20021 and 21521–21921, in 100 ms steps.
No future native frames or other corpus were read.

- [Private reproducible script](../../data/diagnostics/range-perception-20260922/diagnose.py)
- [Full measured outputs](../../data/diagnostics/range-perception-20260922/diagnosis.json)
- [Native E/F HUD at 20.021](../../data/diagnostics/range-perception-20260922/hud-20021.png)
- [Native ammo at 20.021](../../data/diagnostics/range-perception-20260922/ammo-20021.png)
- [Nearby/distant scene at 19.921](../../data/diagnostics/range-perception-20260922/scene-19921.png)
- [Nearby/distant scene at 20.021](../../data/diagnostics/range-perception-20260922/scene-20021.png)
- [Native squad chat at 13.521](../../data/diagnostics/range-perception-20260922/chat-13521.png)

Other `hud-`, `ammo-`, and `scene-` crops in that diagnostic directory cover
13521, 19821, 19921 and 21921. Crops preserve native pixels. Scene crops have
native origin (900,100); chat crop origin (0,800). Coordinates below are always
full-frame 2560×1440 pixels.

The report stores the exact source paths/hashes, candidate-row hash, code hashes,
code HEAD (`87f34a3b4bc06d3608de5bebbf2c5dd1adbb4fee`), library versions and full
trace. Each native hash matched its candidate reference; candidate rows were
unchanged across the run. Temporary exclusion experiments are process-local and
restore the original constant. Nothing writes back into the candidate tree.

## Existing source HUD profile and remaining defect

`hud.MK` already models the right-side web ammo and light-on-dark charge badges.
Both default layouts retain `get_over_here` at x=.8348 and `uppercut` at .8723;
those semantic names are reversed on this source. `slot_mapping` on the five
earliest history frames (13.121–13.521), using its existing vote threshold,
returns:

| Position key in MK | Visually identified ability | x fraction |
|---|---|---:|
| swing | swing | .7950 |
| get_over_here | uppercut | .8348 |
| uppercut | get_over_here | .8723 |

Constructing `dataclasses.replace(hud.MK, slot_cx={ability: hud.MK.slot_cx[position]
for position, ability in mapping.items()})` is sufficient for those positions.
Teamup has no successful mapping and is omitted, not guessed. This is a proposed
offline source profile derived from visible icons, not a backdated human binding
report or runtime pad profile. No later hidden/countdown-replaced icon supplies
identity. The five-frame mapping includes the 13.521 anchor itself; it is entirely
prior evidence for the later windows, not a claim of earlier calibration.

| Native time | PAD ammo | Mapped MK ammo | Mapped uppercut `(ready,charges)` | Uppercut countdown | Mapped pull ready/countdown |
|---|---:|---:|---|---:|---|
| 13.521 | unknown | 3 | `(True,2)` | unknown | `True / unknown` |
| 19.821 | unknown | 1 | `(True,0)` | 3 | `True / unknown` |
| 19.921 | unknown | 1 | `(True,0)` | 3 | `True / unknown` |
| 20.021 | unknown | 0 | `(True,0)` | 3 | `True / unknown` |
| 21.921 | unknown | 1 | `(None,0)` | 1 | `True / 6` |

These are actual reader outputs, not labels or assertions of availability.
Native crops visibly corroborate E's zero badge/countdown 3, later countdown 1,
and F's countdown 6. Plain MK fixes ammo but leaves ability identities reversed.

The shared implementation defect is in `read_ability`: icon ink color decides
readiness without reconciling recognized countdowns or exhausted charges. A white
countdown is accepted as ready-looking ink. `read` obtains countdowns separately;
`Hud.state_kwargs` carries the contradictory readiness into `State` while omitting
countdowns. Layout correction therefore still says uppercut ready with zero charges.
At 21.921 MK's spill guard refuses E/swing, but F still produces ready=True with 6.
This is a shared code path; native reproduction here is KBM only.

Root's minimal next assignment can use MK plus the reviewed visible mapping for
source extraction and repair readiness reconciliation in the existing HUD reader.
Known zero charges must not produce ready=True; a countdown replacing an icon is
not positive readiness evidence. A blanket `countdown > 0 => unavailable` would
also need care: charged abilities may recharge while another charge remains.
Unreadable charge/icon combinations must stay unknown. This diagnosis does not
establish a new complete ready-state rule or infer availability from hidden icons.
In particular, swing badge coverage remains incomplete (`None` at these anchors),
and its False read at 19.921 needs separate inspected evidence before being trusted.

## Nearby target miss, crop, acquisition and history

GREEN matches both nearby and distant native enemies. No color change is indicated.
The decisive experiment changes only `outline.PLAYER_ZONE_MIN_H` from 60 to 0
inside the diagnostic process, then calls the existing wide/aim functions. At
native scale 2, the unchanged rule removes components shorter than 120 pixels
whose center is in `PLAYER_ZONE=(.28,.33,.64,1.0)`. This happens before plate/body
association. It applies in the passed image's coordinates; HUD zones already use
the explicit whole-frame origin.

| Time | Nearby native body bbox | Height | Default wide/aim | Exclusion-only intervention |
|---|---|---:|---|---|
| 19.821 | `(1151,585,1276,669)` | 84 | missing / missing | body recovered in both |
| 19.921 | `(1153,613,1333,743)` | 130 | present / present | unchanged |
| 20.021 | `(1243,708,1305,795)` | 87 | missing / missing | body recovered, plate=True |

At 20.021 its name/health bar `(1149,639,182,40)` is also removed by the same rule.
The body center is (.4977,.5219) in the whole frame and (.4938,.5328) in the aim
crop, inside the player zone in both. At 19.821 the corresponding centers are
(.4740,.4354) and (.4307,.4031). These are **not aim-crop edge losses**: all are
inside the unchanged native crop `(800,240,1760,1200)`.

The selected upper region is visibly a distant Galacta bot/marker, not established
scenery. At 20.021 it produces `(1497,355,1565,431)` in both paths. At 19.921 the
producer actually detects the nearby target, so a detector-only explanation fails:

- Distant track 2 has already acquired selection at 19.821.
- At 19.921 nearby track 3 is 55.97 px from the crosshair; distant track 2 is
  460.00 px away. Nearby is in reach and inside aim, but `_acquirable` is False:
  it lacks a prior sighting in `memory.seen`.
- The same-ID hold prefers the established distant target. Clearing only the
  sticky target while preserving acquisition history still selects the distant
  target, so changing sticky preference alone cannot resolve this frame.
- At 20.021 the nearby component is removed again, preventing confirmation.

Replaying the same five candidate20021 native frames with only the player-height
exclusion disabled acquires the nearby bot at 19.721 and retains it through
20.021 using unchanged tracker/gate logic. Default crop-first replay selects the
distant bot at 19.821 and keeps it. The report includes both traces and full-width
controls. These are causal sensitivity measurements, not human target labels.

There is a secondary crop/tracker interaction: the upper bot's full-frame box at
19.721 starts at y221, but aim clipping starts at y240. Crop-first tracking changes
its ID from 1 to 2, delaying its acquisition a frame. This does not cause the
nearby filter failure; it illustrates why anchor detection and history must both
be examined. Native replays use no KBM-count camera conversion and no tagged
reader; exact frozen producer-State replays preserve the producer's tagged field.

Globally disabling player exclusion is **not a proposed fix**. Existing player
junk controls are justified. Root should assign the detector owner a narrow repair
that preserves the observed nearby partial outlines/bar association while retaining
player/HUD rejection. Confirming corrected causal target tracks comes before
changing selector policy. No future target feature or vocabulary change is needed.

## Other native controls

At 13.521 Luna is detected `(1276,555,1371,754)`, plate=True, inside aim and in
reach. In the original producer history it is a first sighting, so not acquirable.
The previous peripheral target is coasting; gate returns Idle with no target.
Clearing sticky selection does not remove the missing prior-sighting requirement.

That peripheral detection is a genuine false positive with a different cause:
`find_green` returns squad chat `(51,873,241,22,"bar")`; `find_enemies` projects it
down to `(69.1,996.2,273.9,1225.2)`. The native chat crop visibly reads the green
squad sender followed by “Attack here!”. Full-width detection retains it; the aim
crop excludes it. This is source HUD text rejection, not evidence that the real
distant Galacta in candidate20021 is scenery.

At 21.921 aim is empty; wide fallback returns a projected bar-only box
`(1334.5,176.1,1397.5,246.4)`, plate=None. Its source marker lies above the aim crop.
A projected box landing on architecture alone does not prove a scenery false
positive. This window offers no verified nearby target match or admitted Idle.

## Verification and limits

Executed without changing the shared environment, using cached isolated packages:

```powershell
uv run --offline --no-project --with opencv-python-headless --with numpy python data/diagnostics/range-perception-20260922/diagnose.py
uv run --offline --no-project --with opencv-python-headless --with numpy --with pytest python -m pytest tests/test_outline.py tests/test_hud.py::test_an_unidentifiable_slot_is_left_out_rather_than_guessed --deselect tests/test_outline.py::test_native_kill_feed_frames_lose_only_the_kill_feed -q -o cache_dir=data/diagnostics/range-perception-20260922/pytest-cache
```

Result: **24 passed, 1 explicitly deselected** (the native corpus-reading test).
Unchanged controls cover close-body survival, small player junk rejection, crop
origin/scale, green outlines, red fallback, bar/body association, HUD kill feed,
low-hue scenery and unknown slot identity. Private PAD white/red/empty icon controls
return True/False/None in every slot, identically before/after constructing and
using the mapped MK layout. Both PAD and MK definitions remain unchanged.

Native PAD regression corpus was not authorized and was not read. Synthetic
controls do not establish real PAD readiness accuracy, source label truth or
acceptance. These few windows do not justify a broad detector threshold retune.
Producer counts remain 0 Idle / 0 target-agreed Engage as reported by admission;
this diagnosis changes neither count. Root owns adjudication and subsequent
implementation/review assignment; human-admission owns target/control annotation.

## Bounded VUH-1314 repair: awaiting independent review

Root assigned `perception/outline.py` and `tests/test_outline.py` after accepting
the measured cause. Only those production/test files, this lane note and the
diagnostic directory changed in this lane. HUD is assigned separately. Selector,
tracker, candidate data, policy and frozen original diagnostic artifacts remain
untouched. No commits or live execution.

The player guard still uses its original zone, 60 px height threshold, color,
fill and area checks. Before dropping a guarded partial mark, the detector now
looks for an associated **filled health strip** in already accepted color/HUD
components. This uses existing `BAR_MIN_H` and `BAR_MIN_ASPECT`: a 6×24 px filled
rectangle at 720p (12×48 native), after the existing horizontal bar-gap closing
operation. It additionally requires an uninterrupted line of that width in the
original color mask, because horizontal closing alone can fill text into a solid
patch. The strip's connected component must satisfy existing bar height/maximum
width limits. A partial strip need not have the width of a complete nameplate;
the ordinary nameplate classifier's width/height thresholds are unchanged.

Evidence must have a body extent below it of at least `GREEN_MIN_H`, using the
existing bar/body association. This handles a joined plate/body component and
separate small body arcs. Merging alone does not release the player guard: each
original guarded component needs the positive association. Hollow player junk,
a bare filled patch, or an unrelated bar cannot supply that association. Marks
rejected by the existing color, HUD or kill-feed checks cannot supply evidence.

In the lower-left chat HUD region `(0,.55,.35,.88)`, a flat mark now needs this
filled-strip evidence or an associated supported body. This removes the observed
squad sender text without changing GREEN or rejecting the real distant bot. The
screen region is evaluated with the full-frame origin for crops. A real health
bar in the same area survives the paired synthetic control. Text-only world
nameplates in that region without a visible body/health strip can now be refused;
the pixels do not justify calling those text-only marks enemies there.

### Measured result

New artifacts, separate from all original diagnosis files:

- [Repair replay script](../../data/diagnostics/range-perception-20260922/repair_eval.py)
- [Before/after outputs, hashes and timing](../../data/diagnostics/range-perception-20260922/repair-results.json)
- [19.821 before](../../data/diagnostics/range-perception-20260922/repair-before-19821.png) / [after](../../data/diagnostics/range-perception-20260922/repair-after-19821.png)
- [20.021 before](../../data/diagnostics/range-perception-20260922/repair-before-20021.png) / [after](../../data/diagnostics/range-perception-20260922/repair-after-20021.png)
- [13.521 after: Luna kept, chat removed](../../data/diagnostics/range-perception-20260922/repair-after-13521.png)

Magenta rectangles in the new images are full-frame detector outputs, not human
annotations or selected-target overlays. The three after images above were
visually inspected. The replay reads the same 17 authorized history frames;
future frames are not involved. The baseline is the exact original Git source,
checked against the frozen diagnosis code hash with Windows line-ending handling.
The new report records hashes of all 18 frozen script/report/image artifacts and
checks that they stayed unchanged during execution.

| Candidate20021 time | Native nearby detection after repair | Selected track after repair |
|---|---|---|
| 19.621 | still missing; evidence too occluded | none |
| 19.721 | `(1157,579,1249,634)` | none; first sighting |
| 19.821 | `(1151,585,1276,669)` | nearby track 2 |
| 19.921 | `(1153,613,1333,743)` | nearby track 2 |
| 20.021 | `(1243,708,1305,795)`, plate=True | nearby track 2 |

Unchanged crop-first tracker/gate replay selects the nearby Galacta instead of
the distant bot from 19.821 through the anchor. The recovery is correspondence
observed on these diagnostic pixels, **not** a human target label or admission.
The first highly occluded frame remains refused. The joined partial boxes at
19.721–19.921 include marker pixels and do not establish perfect body geometry.

Across all 17 source frames, full-frame changes are restricted to removal of
the squad-chat false detection at 13.121–13.521 and addition of the nearby
partial mark at 19.721, 19.821 and 20.021. Other full-frame detections, including
the distant bots and 21.921 bar-only marker, are unchanged. Exact lists and crop
comparisons are in the report.

### PAD controls and verification

Root supplied the exact four pre-existing PAD fixture locations under
`C:/rivals-agent/data/l1/`; each was visually inspected in full. The kill-feed
fixture shows the green Luna name in the HUD, while the other three show genuine
enemy marks at the top/right screen edge. Both wide and aim-crop outputs are
**identical before/after** on every fixture. The native regression test also
passes its existing assertions (kill feed excluded, true edge enemies retained).

| Original PAD path suffix | SHA-256 |
|---|---|
| postfreeze30/000150.jpg | `a81ebeb1699107bc6230b1306d74f60d723e11027009961644f16942306d92d0` |
| tagrun0/000206.jpg | `212dc394cabc3fd2d8c75f6c8a2018a23c464be408ee1ca62d887659f788ec93` |
| tagrun0/000228.jpg | `18c7aeb00c79da5a7409b65c27fbcea098c1b51bd317a5fec31d77d624e0985f` |
| tagrun1/000342.jpg | `6e598a92fc9dbccd0ed02decf47e47e27f2237b6c02c4bb6e450553b3ba0ba75` |

Executed in the cached isolated environment, no shared environment installs:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
uv run --offline --no-project --with opencv-python-headless --with numpy --with pytest python -m pytest tests/test_outline.py --corpus -q -o cache_dir=data/diagnostics/range-perception-20260922/repair-pytest-cache
uv run --offline --no-project --with opencv-python-headless --with numpy python data/diagnostics/range-perception-20260922/repair_eval.py
```

**37 tests passed**, including all four authorized native PAD fixtures and six
hash-pinned source frames. New controls include the same partial body with and
without its strip, separate/joined geometry at both scales, unrelated/HUD bars,
thick player-junk contours, text versus a real bar in the chat area, crop/full
agreement, and a native ablation that removes only the separate name/health mark
while leaving the nearby body pixels identical. That ablation restores the guard
in both paths and retains the distant bot. All corpus-reading tests in this file
are now marked `corpus`, so default test runs do not open these native fixtures.

A bounded single-thread CPU timing check used 12 calls per path/version on two
already loaded authorized frames: median wide 31.71 → 32.99 ms, aim 8.09 → 8.45 ms.
These are local diagnostic timings, not a live latency qualification. Health-strip
inspection runs on accepted component crops, avoiding a second whole-frame pass.

Tested outline SHA-256:
`c795eced92aeb514ac08541595fefe779bf9dc367294cf120dfdc910825111bd`.
Review must consider the positive-strip exception and chat-region recall tradeoff;
this small development set cannot prove general bot identity or scene rejection.
Independent range-review and root integration remain required before live reliance.
Human-admission retains all annotations, acceptance and dataset ownership.

## Evidence-ownership review delta

Root independently reproduced and accepted two findings in the first repair.
Its original report, reproducer and media remain immutable; earlier assertions
that rejected components could not supply evidence and that each original mark
needed justified support were not fully enforced. This delta fixes those paths.

Before changing production code, eight regression variants failed: both cases
at 720p/native scale and in full/aim views. Exact full-frame 720p `detect` results:

| Review case | Before injection | With injection, old repair | With injection, fixed |
|---|---|---|---|
| P1: rejected H55 filled strip inside an accepted H65 hollow mark's bbox | `[]` | `[(561,351,701,407)]` | `[]` |
| P2: separate unassociated player junk next to a supported body | `[(501,301,551,421)]` | `[(501,301,596,471)]` | `[(501,301,551,421)]` |

P1 repair retains the accepted connected-component ID for every original mark.
Strip extraction uses only that component's original masked pixels. A bounding
rectangle can enclose separately rejected pixels and is no longer treated as
ownership. Existing color/HUD/component rejection remains upstream.

P2 repair retains exact original members while grouping arcs. For each owned
strip, each candidate body arc must independently overlap that strip horizontally
before grouping; the existing bar/body vertical association and minimum body
extent then apply to that aligned group. Only its recorded members and the strip
owner receive support. Membership is never inferred from containment in an
enlarged merged bbox. This preserves the common vertical extent needed by the
native split body while excluding the review's unrelated side component. The
normal `_merge` geometry is unchanged; its helper now retains provenance.

No color, size, player-zone, bar, association-distance or merge threshold changed.
Same-column fragments still use the existing geometric association; this remains
pixel evidence, not proof of object identity in every scene.

New review artifacts:

- [Frozen failing implementation](../../data/diagnostics/range-perception-20260922/evidence-ownership-before-outline.py)
- [Eight reproduced failures](../../data/diagnostics/range-perception-20260922/evidence-ownership-failures.txt)
- [45 passing tests](../../data/diagnostics/range-perception-20260922/evidence-ownership-tests.txt)
- [Delta reproducer](../../data/diagnostics/range-perception-20260922/evidence_ownership_eval.py)
- [Exact delta outputs and preservation hashes](../../data/diagnostics/range-perception-20260922/evidence-ownership-results.json)

`45 passed` with `tests/test_outline.py --corpus`, using the same cached isolated
environment and `PYTHONDONTWRITEBYTECODE=1`. The new reproducer verifies the old
failure and repaired/control equality for all eight variants. It reads only the
same 17 authorized source history frames and the four exact PAD fixtures. All
21 native frames have **identical wide and aim outputs to the prior repair**;
all four causal histories retain the same targets. In candidate20021, nearby
track 2 is still selected at 19.821/19.921/20.021, with the same anchor body and
plate=True. The joined partial detections, split body, chat rejection, native
same-body ablation and PAD valid controls all survive. Thirty original diagnosis
and first-repair artifacts are hash-checked unchanged.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
uv run --offline --no-project --with opencv-python-headless --with numpy --with pytest python -m pytest tests/test_outline.py --corpus -q -o cache_dir=data/diagnostics/range-perception-20260922/ownership-pytest-cache
uv run --offline --no-project --with opencv-python-headless --with numpy python data/diagnostics/range-perception-20260922/evidence_ownership_eval.py
```

Frozen review hashes:

- `perception/outline.py`: `369994b22c895c0248b8089a1ca37c9a30f3e5dd9cb653ad2cc3e59bfb17dd55`
- `tests/test_outline.py`: `edaafbae0f6bade5922792f6eb50ad0a508acbb213481902d1a2148622685e9a`
- Superseded first repair: `c795eced92aeb514ac08541595fefe779bf9dc367294cf120dfdc910825111bd`

The delta is for the same independent admission-review owner; root accepts and
lands it. No policy/HUD/selector/candidate changes, new corpus, input, installs,
commits or status edits. Previous bounded timing figures describe the earlier
repair, not a fresh latency qualification of this delta.

### Lead acceptance of the ownership delta

Independent same-reviewer verification accepted source `369994b2` and tests
`edaafbae` for landing. All 45 scoped tests pass; extra rejected-hue, shifted and
mirrored controls resolve the two findings, and 100 deterministic merge cases
preserve geometry and original membership. The reviewer verified all preservation
hashes, unchanged recorded native outputs/traces and both repaired native controls.
Root reproduced the original failures before dispatch, inspected the final
membership change and native before/after bot recovery, and rechecked the pins.

This accepts the bounded detector software and permits new candidate measurements
under that version; it does not relabel or admit the frozen failed packet. Median
delta overhead was 0.31 ms wide / 0.18 ms aim on two loaded frames, with one 55 ms
wide-call outlier. Live latency and broader same-column geometry remain unproven.
