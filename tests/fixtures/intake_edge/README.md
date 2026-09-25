# Intake edge-rule fixtures (232304 spawn edge)

Three frames of `2026-09-24 18-23-04.mkv` (session `20260924T232304-170Z-12024-1`), decoded natively by exact PTS
(frame index = presentation index; file ms = round(index x 1000/120) + 21), resized to 1280x720 with INTER_AREA and
stored as JPEG quality 92. `scripts/record.py` `in_range` gives the same answer on these files as on the native frames.

| File | Frame | File ms | Composition ns | Shows | `in_range` |
|---|---|---|---|---|---|
| `232304-f308.jpg` | 308 | 2588 | 360061738644248 | spawn-in: untextured hero, range banner, no HP bar | False |
| `232304-f309.jpg` | 309 | 2596 | 360061746977581 | the same | False |
| `232304-f310.jpg` | 310 | 2604 | 360061755310914 | textured hero running, HP bar 250/250 | True |

The intake scan read HUD presence True on all three; the lead's rule (2026-09-25) lets an edge sit only on a frame
both proofs hold, so 232304's seg-002 opens on f310, not f308. Used by `tests/test_human_intake_edges.py`.
