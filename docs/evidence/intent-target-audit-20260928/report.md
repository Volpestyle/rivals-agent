# What is James turning toward? — bounded EXPLORATORY audit

In this 12-event sample, **six turns have an apparent bot focus in hindsight**;
the other six show traversal or leave the next target unresolved. The causal
pass identified a single plausible bot focus in four events. Hindsight resolved
three additional events (E01/E03/E11), while E12 went the other way: its clearly
visible current target was defeated and James turned out of the doorway.
These are assistant-authored interpretations of sparse frames, **not James's
intent labels, human-adjudicated truth, a learned planner score or a yaw result**.

The practical distinction is between continuing an engagement, acquiring the
next target and traversing/repositioning. A visible nearby bot is not always the
destination of the next turn. E09 contains engagement, a KO and departure in the
same two-second interval. E07 looks back toward the ongoing opponent after
passing beside it. E06/E10 primarily navigate a pillar/cover panel. E08 faces the
prominent bot briefly, then leaves; looking toward it does not prove an attack.
No event establishes deliberate defensive disengagement, so that class is not
forced onto post-KO traversal.

## Frozen selection and separate evidence passes

Plan committed in `42fce44`; selector/tests/metadata selection in `f17edb2`.
Causal annotations were committed in `44aa5d4` before future panels were decoded.
Only three explicitly admitted TRAIN sources were opened, with existing split,
admission and current sealed-denylist checks. No frozen-dev/sealed pixels, model
inference, fit, cloud app, desktop input or new data admission occurred.

There are two left and two right event windows per session, selected first/last
in each direction with >=10s separation. A qualifying 0.5s future window has
>=10deg net requested yaw, >=80% directional consistency and <=2deg absolute
yaw in the preceding 0.5s. The anchor is the start of a qualifying window;
it can precede the first nonzero yaw packet by up to 0.5s. It is not an exact
motor-onset timestamp. Candidates overlap before selection. The 30Hz step
period is read from each header, not assumed from the encoder's sampling rate.

We inspected causal t=-1,-0.5,0 first, then oracle t=+0.5,+1,+2. Source identities,
row indices, PTS, dimensions and timebase were pinned/checked; all 72 decoded
frames match exact PTS and composition<=their own row anchor. Future frames and
human yaw labels are oracle/selection evidence only. Causal contact sheets
contain no future controls. The annotator knew the balanced turn-selection
design, so this is not a formal blinded human experiment.

| Event | Session / row | Turn in next 0.5 s | Causal single-focus hypothesis | Oracle context | Apparent bot focus |
|---|---|---:|---|---|---|
| [E01 causal](causal/E01-contact.jpg) / [oracle](oracle/E01-contact.jpg) | 20260923T200129 / 201 | -13.00 deg | Unresolved | acquisition, engagement | Luna Snow on hero-simulation platform |
| [E02 causal](causal/E02-contact.jpg) / [oracle](oracle/E02-contact.jpg) | 20260923T200129 / 848 | +12.20 deg | Unresolved | traversal, unknown | Unresolved / no definite bot destination |
| [E03 causal](causal/E03-contact.jpg) / [oracle](oracle/E03-contact.jpg) | 20260923T200129 / 47225 | +10.75 deg | Unresolved | acquisition, engagement | Large Galacta Bot Ultra on elevated walkway |
| [E04 causal](causal/E04-contact.jpg) / [oracle](oracle/E04-contact.jpg) | 20260923T200129 / 47909 | -109.97 deg | Unresolved | traversal, unknown | Unresolved / no definite bot destination |
| [E05 causal](causal/E05-contact.jpg) / [oracle](oracle/E05-contact.jpg) | 20260925T203745 / 605 | +49.58 deg | Unresolved | traversal, acquisition, unknown | Unresolved / no definite bot destination |
| [E06 causal](causal/E06-contact.jpg) / [oracle](oracle/E06-contact.jpg) | 20260925T203745 / 1649 | -10.45 deg | Unresolved | traversal | Unresolved / no definite bot destination |
| [E07 causal](causal/E07-contact.jpg) / [oracle](oracle/E07-contact.jpg) | 20260925T203745 / 84800 | +62.97 deg | Yes | engagement | Closest small bot from causal foreground lane |
| [E08 causal](causal/E08-contact.jpg) / [oracle](oracle/E08-contact.jpg) | 20260925T203745 / 85281 | -35.92 deg | Yes | acquisition, traversal | Large Galacta Bot Ultra on ledge left of causal view |
| [E09 causal](causal/E09-contact.jpg) / [oracle](oracle/E09-contact.jpg) | 20260926T035932 / 298 | -13.10 deg | Yes | engagement, traversal | Luna Snow on hero-simulation platform |
| [E10 causal](causal/E10-contact.jpg) / [oracle](oracle/E10-contact.jpg) | 20260926T035932 / 1911 | +35.36 deg | Unresolved | traversal | Unresolved / no definite bot destination |
| [E11 causal](causal/E11-contact.jpg) / [oracle](oracle/E11-contact.jpg) | 20260926T035932 / 54257 | -10.75 deg | Unresolved | acquisition, engagement | Small bot near 5m lane marking below |
| [E12 causal](causal/E12-contact.jpg) / [oracle](oracle/E12-contact.jpg) | 20260926T035932 / 54816 | +59.20 deg | Yes | traversal | Unresolved / no definite bot destination |

Overlapping context labels: {'acquisition': 5, 'engagement': 5, 'traversal': 8, 'unknown': 3}. Counts need not sum to 12. Five of the six apparent bot focuses can be linked to a causal visible
candidate; E03 linkage is only possible, not proven. Only three of the four
causal single-focus hypotheses remain an apparent future bot focus. These
descriptive fractions are not accuracy estimates: there was no forced predictor,
independent adjudicator or representative sample.

## What this supports, and what it does not

The audit gives examples of mixed contexts and target ambiguity worth preserving
in diagnostics. It **does not prove** that intent conditioning explains the
model's yaw error: no checkpoint predictions were read here, and no oracle-versus-
causal controlled experiment ran. Sparse frames can miss brief switches or
attacks. First/last balanced sampling over-represents session edges; still-then-
turn selection excludes sustained turning and makes no population claim.
Three sessions in the practice range do not cover live self-fed behavior.

If target/intent conditioning is later tested, keep an explicit unknown/no-target
state and distinguish goal selection from target bearing. A causal input may use
past/current visible candidates, occlusion and visible engagement phase; it
cannot use the eventual attacked bot, future image, KO outcome or James's next
command. Even past visible attack animation would become the model's own action
feedback live. These observations must not be admitted as training targets
without the appropriate independent data review and label validation.

The currently requested next paid sizing remains one 4x4 regularization test
against the completed control, not a new intent-conditioned architecture. The
overfitting curves independently motivate that test; this audit does not license
more grids or encoders.

## Validation and cost

Five synthetic selection tests passed (direction, exact offsets, gaps/unknown or
unaccepted rows, quiet/mixed-sign controls and separation/shortfalls). All 72
native image hashes and exact-PTS receipts revalidated. Decode was CPU-only,
BelowNormal, two threads, streamed; no paid compute. Native JPEGs are retained in
the local archive identified by `native-archive.json`; contact sheets, receipts,
annotations and selection metadata are in this evidence packet.

Decode wall time: 178.750s across two passes; peak decoder working set 160.24 MiB; cloud cost $0.
