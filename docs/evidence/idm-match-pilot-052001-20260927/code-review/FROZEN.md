# FROZEN delta for the match-mode review (supersedes PACKET's and ADDENDUM-1's file pins; admission-owner)

Frozen 2026-09-27 10:57:43 CDT at HEAD cf82821. These files will not be edited until fit-review's verdict. Scaling to the other seven writes only new session folders under data/human/sessions/<id>/.

Copies of every file are beside this manifest as *.frozen.*, with matchmode.frozen.diff against HEAD for the three modified files.

| File | LF sha256 now | In PACKET (39365985) | In ADDENDUM-1 (38754d91) | What changed since |
|---|---|---|---|---|
| agent/human_intake.py | b67dcb1a7d66e1971981038bedee77d65fe4cf67c58f7b45b183d847ff932412 | b67dcb1a | b67dcb1a | unchanged |
| data/human/sessions/intake_session.py | 2697bb6912dcc794e26fb65ff710e7d6dd4d954136b3f214125386bfe89231f5 | f65c7a56 | f65c7a56 | ADDENDUM-2 only: the round-start splash settle in match_hud (HUD_HOLE_NS, HUD_RETURN_SETTLE_NS), match mode only |
| data/human/sessions/assemble_session.py | 9447cbe165ca9d790a35484fda70efd78ff877daa10b9ae8cadf9fcda51d5815 | 03b37c1d | 9447cbe1 | unchanged since ADDENDUM-1 (MOTOR_STATEMENTS 2026-09-27 and MATCHES_0925) |
| data/human/sessions/match_admission.py | 00a42683856d7e36d645ff22cc1318c572e1550f260b34791a608c5e72112ba9 | 00a42683 | 00a42683 | unchanged |
| tests/test_intake_match_mode.py | 52e8bfb265859a35acb2344994b8d7a0b7aa62b05febe6b5e975fe61c46be920 | 97656fa2 | 97656fa2 | ADDENDUM-2 only: test_after_a_round_transition_gameplay_resumes_only_after_the_splash_settle |
| docs/lanes/human-admission-2.md | a65119ff9b8a8aeae1368f776378697b83bc89fbaa99044e9026caf9b651b9cb | 402a9c0e | 402a9c0e | notes only: frame-review v2 settled (appended); no code |
| tests/fixtures/intake_match/052001-own-webs0-missed.jpg | 9d55a82918ebc472fcc7f67b93aaab3386c543b4b4301d8cf6762db3f337bb96 (raw) | same | same | unchanged |
| tests/fixtures/intake_match/052001-own-webs0.jpg | 0e72cd3bd44ad87f9dee49f63df59b826e5f161007ef45cb35cdf81eb22ac751 (raw) | same | same | unchanged |
| tests/fixtures/intake_match/052001-own-webs3.jpg | e7be4cb275adfc3b5a1780c9fcd49bbfa61aa3d3434bf249e30c9c7d2dc487b9 (raw) | same | same | unchanged |
| tests/fixtures/intake_match/052001-spectate.jpg | 7ce5089e2800d04d1d813d823c658824b5a6a50bb2dc675d32fe7b98824f4652 (raw) | same | same | unchanged |
| data/human/sessions/code-snapshot-f8fd92c-6046514b/manifest.json | f37a5a717d06517d160403146eb69818060874582ce79d5fd6aa196fcea82e4e (raw) | same | same | unchanged |

Pilot -5 was assembled with intake_session.py at LF f65c7a56, before the splash settle. Its artifacts (ADDENDUM-1 table) are unchanged and not re-run.
