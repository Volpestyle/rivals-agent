# Spider-Man combo arsenal: inspected guide sources

Source check: 2026-09-20. This is a timestamped demonstration inventory for
[the kit](../spiderman-kit.md), not a set of verified current-patch controller macros.
Codex owns this file; the lead owns kit integration and live verification.

## Evidence and local media

Day and Req are the priority sources. Day explicitly introduces his guide as game
sense rather than a comprehensive combo catalogue (00:00–00:19); its pull lesson is
presented by guest MatchuXD. Req's selected video is match decision commentary, not
an input tutorial. Matchu's own tutorials fill mechanical gaps. Hydro and FFAme are
additional technique sources where those priority videos lack an input breakdown;
their rank is not independently verified.

| ID | Author and source | Upload date / duration | Inspected content |
|---|---|---|---|
| D | [Day: Ultimate Guide, featuring MatchuXD](https://www.youtube.com/watch?v=yuh5NnzOLvo) | 2026-09-03 / 34:17 | Range demonstrations near the start, then narrated match/replay analysis |
| R | [Req: Inside the Mind](https://www.youtube.com/watch?v=vwS65E0yNlU) | 2025-10-28 / 14:27 | Match POV, hero selection, death/killcam; no range in the sampled frames |
| Y | [Matchu: Yo-Yo tutorial](https://www.youtube.com/watch?v=OGkhRImOzgs) | 2025-05-06 / 1:19 | Range; enlarged ability HUD; edited vertical layout |
| T | [Matchu: Top 5 Combos](https://www.youtube.com/watch?v=UPecYKDUT-A) | 2026-05-29 / 1:59 | Range demonstrations and names; incomplete input narration for several entries |
| B | [Matchu: Buffed combos](https://www.youtube.com/watch?v=1KCahJFDBDY) | 2026-09-11 / 1:41 | Match demonstrations of four double-uppercut variants; enlarged ability HUD |
| S | [Matchu: Best Combo for All Ranks](https://www.youtube.com/watch?v=yVOR69zfQ6g) | 2025-06-20 / 1:34 | Sekkombo in the range, slow/fast demonstrations, keyboard/mouse overlay |
| P | [Matchu: Old Combo Is Back](https://www.youtube.com/watch?v=DsYg_fWwimk) | 2026-01-15 / 0:22 | Peni-dependent variant in the range; keyboard/mouse overlay |
| H | [Hydro: Easy and Advanced Combos](https://www.youtube.com/watch?v=tHsy7xGoYE0) | 2025-09-14 / 13:10 | Narrated input breakdowns; mixed range, settings and match/replay footage |
| F | [FFAme: Season 1 CEO Guide](https://www.youtube.com/watch?v=57GoyFs3Pns) | 2025-01-11 / 37:12 | Clean range/timed-practice demonstrations; Stack narration and selected frames inspected |

Media, source metadata, automatic transcripts and inspection frames stay in
`data/demos/guides/`, gitignored. The local manifest records decoded duration,
resolution, FPS and transcript provenance. Dates above come from retrieved video
metadata, not relative search snippets. Day's description links `twitch.tv/daymr`;
Req's links `twitch.tv/reqmr`. Titles claiming rank do not verify rank.

Narration is transcribed locally with `mlx-whisper` and
`mlx-community/whisper-large-v3-turbo`. The lists below normalize transcription
errors such as “pole” to the ability name supported by the captions/demonstration.
They preserve narrated action order, not verbatim prose or exact physical inputs.
Automatic transcripts are not fully audited by listening; selected caption and
scene frames are inspected. No current-game execution is performed in this lane.

All times are seconds on the full source video's timeline. A narrated interval
locates an explanation; it does not establish the game's inter-input timing.
Edits, pauses, replay speed, slow motion and HUD latency prevent that inference
without a separate timing check. Even range footage retains patch, control-layout,
compression and overlay differences from our runtime. Keyboard overlays are useful
weak input evidence, not synchronized input logs.

## Narrated inputs and usage

Ability names are the source-level contract. The kit maps cluster to LT, melee to
RT, uppercut to X, swing to LB, jump to A and the ordinary contextual Get Over Here!
to RB. **Do not translate an explicitly aimed pull on a tagged target to RB until
its control setting is verified.** Source creators use custom keyboard bindings.
A downslam also needs its airborne prerequisites; “slam” is not an unconditional RT.

| Source/time | Technique | Narrated action order | Purpose / conditions stated |
|---|---|---|---|
| D 01:31–01:43 | Momentum setup | Swing or bunny-hop, then uppercut | Carry momentum farther before an off-map pull |
| D 01:46–01:52 | Ground-zip setups | Ground zip → uppercut; or ground zip → cluster → double jump → uppercut | Preferred setups for crossing the map before a pull |
| D 01:56–02:26 | Long/off-map pull | For swing/bunny-hop alone, aim the pull. After an uppercut setup, cancel uppercut with swing, then pull | Frees the pull sooner; an uppercut hit can make the target's trajectory easier to intercept |
| D 02:28–02:46 | Pull practice and aim delay | Repeated practice; aim may change after the pull animation begins | Demonstrates starting toward one bot and flicking toward another; binding press is not projectile release |
| Y 00:09–00:52 | Yo-Yo | Get airborne → pull → double jump → swing-cancel → cluster → uppercut → swing-cancel → cluster → downslam | Pull cancel must occur late enough for the pull to happen. Narrator claims a 275-HP finish; not measured here |
| Y 00:52–01:06 | Yo-Yo target use | Same sequence | Displace Loki/Cloak from utility; coordinate allied fire if the full sequence fails. Interaction claims are dated source claims |
| S 00:46–00:58 | Sekkombo base and extension | Cluster → pull → punch → cluster → uppercut; extend with swing-cancel → cluster | Pull the opponent out of position without travelling to them; follow-up helps against intervening healing |
| S 00:26–00:46; 01:11–01:21 | Sekkombo movement and timing | Moving/jumping variant; time punch after pull arrival before the next cluster | Be harder to hit and avoid cancelling/missing the punch |
| T 00:03–00:19 | Cluster/downslam string | Cluster → downslam → cluster → uppercut | Narrator warns the first shot advertises the attack and the slam requires precise arrival |
| T 00:19–00:49 | Bread-and-butter / Hydro | Uppercut animation cancel and simple-swing use are discussed; full orders are not spoken here | Bread-and-butter is characterized as slow/counterable; Hydro as a simple-swing option. Names alone do not supply macros |
| B 00:08–00:25 | Corn-on-the-Matchombo variant | Cluster → swing to feet → uppercut → swing → pull → swing → cluster → uppercut; optional swing → cluster → downslam | Two uppercuts and displacement. Title/name spelling in automatic speech is uncertain; identify by source/time and sequence |
| B 00:25–00:43 | Symbiote ladder variant | Cluster → uppercut → swing → cluster → symbiote → swing → cluster → second uppercut; optional swing → cluster → downslam | Three-stage vertical displacement; **team-up dependent, outside the first bot's execution set** |
| B 00:43–00:57 | New bread-and-butter | Cluster → uppercut → swing → cluster → Get Over Here! targeting → second uppercut; same optional extension | Narrator distinguishes targeting/strike here from pull elsewhere; describes a faster re-hit sequence |
| B 00:58–01:20 | Double-uppercut CJ variant | Cluster → swing → uppercut past target → swing/pull → swing/cluster → uppercut | Greater displacement; simple swing is said to save a swing needed for downslam in the regular variant |
| P 00:00–00:21 | Peni Sekkombo variant | Activate Peni team-up before pull; use its available activation during pull. Alternative waits about 1.5 s for explosion/tracer interaction | **Peni dependent**, not evidence for a solo macro or present-patch timing |
| H 01:19–01:53 | Setup / Flashstep | Hold-to-swing on, separate simple-swing binding, optional secondary punch binding; cluster → Get Over Here! → simple swing → overhead → cluster → uppercut | Evasive displacement against hitscan/CC; manual and simple swing are distinct source controls |
| H 03:50–04:24 | Reverse Flashstep | Cluster → Get Over Here! → simple swing → uppercut → manual swing → cluster → overhead | Slower but more consistent opener; uppercut has wider coverage |
| H 04:30–05:04 | Delayed Flashstep | Cluster → Get Over Here! → uppercut → manual swing → cluster → simple swing → overhead | Vary displacement timing; narrator also recommends against flyers |
| H 06:06–06:53 | Double-swing overhead | Uppercut → manual swing → cluster → simple swing → overhead | CC avoidance/extension; preserve swing resource for exit and consider enemy escapes |
| H 07:04–08:12 | Hydro | Cluster → Get Over Here! → punch → cluster → simple swing → punch → cluster → uppercut | Burst against tankier/self-healing targets and post-ult follow-up; not the narrator's replacement for Sekkombo against strong CC |
| H 08:39–10:44 | Double-swing Panther | Cluster → Get Over Here! → manual swing → cluster → simple swing → punch → cluster → uppercut | More reliable around cover/low ceilings; says both pull and attach work; manual-swing interval supports reaching the ground before punch |
| H 10:50–11:41 | Short Panther variation | Cluster → Get Over Here! → simple swing → punch → cluster → uppercut | Requires grounded approach/target for punch; airborne follow-up can become overhead instead |
| H 12:02–12:09 | C.e.ombo | Overhead → cluster → simple swing → punch → cluster → uppercut | High-precision bonus string; name is source-specific |
| F 20:07–21:30 | FFAme Stack | Apply tracer → Get Over Here! → uppercut in very rapid succession, **Get Over Here! first** | Demonstrates rolling/plinking two bindings. Controller binding suggestions are speculative in the narration |
| F 21:31–23:19 | Stack approach / extensions | Tag from farther away → swing within about 4 m → Stack; then swing-cancel → cluster → punch, or punch → cluster | Drive-by burst and follow-up; range and damage are historical source claims |


B 01:20–01:36 gives a 290-damage subtotal for two clusters and two tracer-enhanced
uppercuts, before other hits. This is the narrator's arithmetic/claim, not a measured
current-patch damage result. Likewise the older 275-HP kill claims do not establish
our bot's damage or timing. Consult the kit's current sourced values and live trials.

## Sekkombo: the actual unresolved dependency

S 00:46–00:53 explicitly describes a pull, and inspected frames around 00:48–00:50
show the enemy travelling toward Spider-Man. Treating the word as merely a mistaken
name for web strike is unsupported by that demonstration. It does **not** prove the
same sequence is possible with our default contextual RB or on the current patch.

The kit already identifies a possible separate PC pull binding. Current settings,
that binding's availability on pad, and tracer state at projectile release need a
live check. Preserve `cluster → aimed pull` as the demonstrated semantic sequence;
do not silently convert it to `cluster → web_strike`, or ship `LT → RB` as equivalent.
The lead owns this live test and the resulting kit/controller decision.

## Stack and swing controls

F 20:10–20:18 first calls the Stack nearly simultaneous, then explicitly requires
Get Over Here! **before** uppercut. F 20:33–21:04 demonstrates rolling/plinking two
bindings; F 21:22–21:30 only speculates about controller bindings. This is not
proof that one physical button triggers both, or that one simultaneous pad report
works. Keep the ordered pair and measure its current valid interval in the range.
H distinguishes manual swing from separately bound simple swing; mapping both to
ordinary LB without checking settings would erase the demonstrated mechanic.

## Practice-range material for HUD inspection

| Source / inspection interval | What is visible | Extraction caveat |
|---|---|---|
| D approximately 00:25–00:58 | Day's team-up/CC comparison; range banner visible at 00:30 and 00:45 | Team-up effects, avatar/chat and subscriber alert; edits/zooms |
| D 01:22–02:49 | Matchu's movement/pull lesson; range visible at 01:30, 01:45, 02:15, 02:30 and 02:45 | Split-screen comparison around 02:00; cut/zoom and overlay boundaries need segmentation |
| Y 00:09–01:12 | Range pull/uppercut demonstrations; enlarged HUD | Vertical re-layout, burned-in captions, edits; does not match a standard 1080p HUD table |
| S 00:26–01:21 | Range movement and slow/fast Sekkombo demonstrations | Keyboard overlay may help label inputs, but delay and custom bindings are unverified; slow demonstration is not real-time timing evidence |
| T 00:03–01:56 | Range examples including Hydro and Sekkombo | Large avatars/ranking text hide scene regions; full input order not spoken for all entries |
| P 00:00–00:21 | Range Peni interaction | Team-up-specific, older patch, heavy overlays |
| H around 02:50, 04:00 and 04:40 | Range/timed-practice examples; reverse/delayed notation visible at 04:00/04:40 | Mixed with match/replay footage; do not treat the whole chapter as range |
| F 20:00–23:50 | Clean landscape range/timed-practice Stack teaching; inspected at 20:05/20:30/21:00/21:40/22:30/23:20 | Old Season 1 mechanics; narration includes failed attempts, which must remain separate from successes |

These are inspection windows, not assertions that every frame within each interval
is usable. Preserve originals, reject non-gameplay and edits, and mask person-like
streamer graphics before target proposals. Read source-specific HUD regions; unknown
or hidden values stay unknown. No numerical inter-ability timing is accepted yet.

## Tactical annotations available from the priority sources

- R 00:28–00:40: narrator identifies a Doctor Strange portal setup and attempts a
  disruptive pull; R 01:12–01:18 describes pulling a displaced Peni into the team.
- R 01:19–01:40: flank or pass the supports before engaging rather than entering
  directly in their fire. This explains a decision, not a universal target rule.
- D 11:02–11:12: when too close to the ground for the preliminary cluster, describes
  taking the cluster opportunity after the downslam instead.
- D 23:42–24:10: discusses timing an engage around the next swing recharge so an
  exit charge becomes available; he also notes he could have waited longer.

These are candidate narrated decision windows, not proof of optimal play, and narration
may be retrospective. Separate what was observable at decision time from commentary.

## Coverage and remaining verification

The inventory is not a claim to contain every viable Spider-Man combo. Naming varies,
several names overlap, and the videos span patches. Concrete source gaps remain:

| Named tech | Current evidence status |
|---|---|
| Sekkombo | Spoken order and actual pull demonstrated in S; current pad translation unresolved |
| Yo-Yo | Detailed spoken sequence and range demonstration in Y; cancel window unmeasured |
| Long Pull | Detailed movement/pull lesson in D; travel/timing not measured |
| Swing cancels | Specific pull/uppercut cancels narrated in D/Y/S; do not conflate them with every possible swing-cancel mechanic |
| Season 10 double-uppercut strings | Four narrated variants in B, with match demonstrations; separate the symbiote variant |
| Hydro / Perfect Swing | Hydro and double-swing variants have spoken orders in H; simple-swing control and current pad translation need verification |
| FFAme Stack | F explicitly requires Get Over Here! before uppercut, demonstrated in the range; current timing and pad mapping unmeasured |
| Downslam Exploit | Cluster/downslam string is narrated in T; the distinct wall/no-wall exploit from snippets is not verified |

Additional discovery pointers remain unverified: [downslam tutorial](https://www.tiktok.com/@sekkunnn/video/7485563163417627926),
[FFame discussion](https://www.youtube.com/watch?v=PS1ES-XmBnY),
[FFame alternate guide](https://www.youtube.com/watch?v=as6BlJkCg7Y),
[controller Yo-Yo](https://www.youtube.com/watch?v=U525nvibqO0),
[Agni Kai Yo-Yo](https://www.youtube.com/watch?v=fTqNQtkrXLQ),
[Blade swing cancels](https://www.youtube.com/watch?v=JLB7MmsklY8), and
[CaptainRocket Sekkombo](https://www.youtube.com/shorts/bbpbpppyqDo).
No input order or damage figure is accepted from their search snippets.
