# Match -5 ping-a1 assembly stopped by the game guard

The corrected assembly attempt on 2026-09-27 was stopped at 18:56:32Z with
`failure: "Marvel or OBS active"`. The recorded `exit_code: 0` does not establish
success: the non-null failure is authoritative. The owned Windows Job Object
was closed; reconciliation found no surviving assembly supervisor, Python
worker or ffprobe child. Marvel processes were active at reconciliation.
No process belonging to James or another lane was stopped by admission.

Run record:
`data/admission-codex/runs/20260927T052001-827Z-150600-5/ping-a1/assemble.run.json`.
Only settings and review were emitted before the guarded import was interrupted.
No replacement steps, imported demo, freeze, pending receipt or accepted-a1
was produced. The original acceptance remains superseded.

Before the attempt, the nine prior assembly outputs were checked against their
frozen hashes and retained as `.v1` files. The exact mapping is
`data/human/sessions/20260927T052001-827Z-150600-5/assembly-ping-a1-supersedes.json`.
The historical Mac relocation is unchanged; its label tables remain held.

The final independent ping review is retained as
`independent-review.ping-a1.verdicts.json`, SHA256
`df3e8409b85bf4fd79f943099ea116e9e590402decae40d0cdf08c246097aead`.
It agrees on all 52 segments, with seven accepts totaling 342.399986311 s.
Its nonblocking VK52 observation is retained; the lead agreed to no new cut.

Next: after Marvel and OBS stop, coordinate the decoder slot with frame-review.
Preserve this failed attempt and its partial output files, then retry assembly
into a distinct run directory. Verify unchanged step rows, original raw payload
and decoded PTS, and absence of accepted ping-cut overlap before issuing the
pending and pre-authorized accepted-a1 receipts. The prepared verification helper
is `data/admission-codex/verify_ping_assembly.py`; its renumbering, changed-camera
and changed-run-partition controls pass, but the real assembly check has not run.

The slot was released after Job Object closure, then frame-review was explicitly
notified that active Marvel/OBS still prohibits decoding. The user approved its
-4 boundary decode, which remains subject to that same runtime guard.
