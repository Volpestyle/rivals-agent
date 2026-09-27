# Match -8 accepted

Accepted under the lead's 2026-09-27 pre-authorization after successful
guarded assembly and receipt generation. Independent cut review `b35afbf`
is LAND and frame-review agrees on all 70 segments.

- Receipt: `receipt/match-admission-055006.accepted.json`, SHA256
  `27e34517ec16b694147a0a897eb8c75fcfce34061b778fbf59ca29e7c86c9819`.
- Pending receipt preserved byte-for-byte, SHA256
  `5193dba53edd3f64dced0d62ce991457aa61ce3a1c74403a2f03d26bcef3c3ff`.
- 13 accepted spans, 309.391654304 seconds, 5.156527571733333 counted minutes.
- 12,283 steps; 9,272 eligible 30 Hz rows. Steps SHA256
  `957eb1a554858f6a3ca09184276dafaa9c5aeb705f1dced412b84234867298ef`.
- Imported demo SHA256
  `0fc7874f7ae6a25823b81e437d08787b6f61bc71749877d4e0838d758b2e74f3`.
- Artifact freeze SHA256
  `6ef847473ab128fa93757c216fb4fa9d6ee1250d0a0b46786452200c7b325cda`.

Assembly and receipt run records both have exit 0 and failure null.
Assembly peaked at 172,683,264 bytes. All 19 frozen session artifact hashes
were checked before writing acceptance. The receipt cites the cut LAND and
final independent verdict by full SHA256; its session entry equals the
pending entry exactly.

Consumer authority must refresh before use. This admission does not add -8
to the current IDM refit roster or authorize a new transfer. Comms binding
clarification is in `COMMS-BINDINGS.md`; no gameplay-vocabulary change.
