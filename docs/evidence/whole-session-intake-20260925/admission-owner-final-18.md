# admission-owner final 18: 025230 admitted (train, 3.66 counted min)

**Assembly.** `20260925T025230-605Z-7804-2` was assembled on 2026-09-25 from **`code-snapshot-b7d4592`** (manifest
`1927686c…`: the reviewed importer, edge rule, E1 and N1–N3), with the independent record `33f0c38d…` (equal to the owner
verdicts on all 8 segments).
- **Freeze:** checks clean; 21 folder files, 9 external.
- **Motor:** both motor records are pinned. The evidence's `motor` sha256 (`8955d5b8…`) names `motor-settings.v1.json`,
  which the current record names in `supersedes`.

**What it holds.**
- **Accepted:** seg-002 (175.03 s) and seg-005 (44.81 s); **3.6640 counted min** (2 runs).
- **Trainable:** 3.6633 min at the 33.3 ms stride.
- **Step table:** 6,667 rows, 6,594 accepted and gap-free.
- **Import:** 26,997 decoded frames, 26,996 referenced. The audit's `unknown_composition` holds the one excused frame:
  - packet 118 (file pts 1021), a duplicate of packet 119, 1 packet apart;
  - slot 1.081–1.098 s in logger time, inside rejected seg-000 (the focus transition, 0.999–1.249 s), 82 ms after
    focus gain;
  - my earlier "0.99 s, before focus" (final-16, importer-dup-cts.md) measured from the first frame, not from the
    logger start, and was wrong. The segment check is unaffected;
  - rationale: "a stated bound, not a measured one…".
- **Header:** patch `1.1.3892207/build25501035`, settings identity `a8dea3ba…`, calibration v2 (the 09-23 slow-turn gain,
  confirmed across speeds by the 030045 take), sitting 2026-09-24-late-evening.
- **Per-session motor source:** the `57d1f3d` recording-log line.
- **The fit's reader** loads this table in one cohort with the four admitted sessions and 232304. The equivalence file
  maps both builds to the same kit version; without it, the cohort is refused, as designed.

## Bytes (`data/human/sessions/20260925T025230-605Z-7804-2/`, all LF)

| File | Bytes | sha256 |
|---|---|---|
| `20260925T025230-605Z-7804-2.steps.jsonl` | 4,515,567 | `84cef39b81ce8a40637bb5cf9766cdfc6f4054b32cda5d94ac1082329434c288` |
| `artifact-hashes.json` | 4,964 | `5617d968ac8f0e76fbd5459bc9a0b233e308a74f365309760f0d23166c014ab6` |
| `review.json` | 11,630 | `c4a2fe0de27875fa9403f7856458e160798783859021eb47da90096b7c3e386c` |
| `settings.json` | 5,064 | `1bcf44c28b37b31ee1a74bcf41a7c3ed5040ba61c2ce7d461acd17bd486f7512` |
| `imported-demo.jsonl` | 13,866,893 | `ef09a52d7fde5b3dbc884d27c08e2c7ec09b6227b759c7f75b541b5b6d37cb85` |
| `sampling.json` | 634 | `f4b19867053ccb8cdf177a73105ac32ab5238eb067f73f41ab89349469defaa0` |
| `minutes.json` | 914 | `ff05d3a8e49570cddfbda311486896ba7e652a42cc8b204f80941a566ee24870` |
| `recording-log.dfbb4dd.md` | 7,747 | `25c9f622155726df96d5ab33bd021288630a74656b6a18d3dbf9748d41f4b799` |
| `registry.f36e9e3b5650.json` | 8,492 | `f36e9e3b565041cbd719d3d4c6b80033d66a685a599f3b6607e67bab3ee574fb` |
| `independent-review.verdicts.json` | 30,417 | `33f0c38d5ecc4036abdc04b7f1f3668a8c35dc44c66b1d6424897a57ee8c1933` |
| `independent-review.md` | 7,444 | `4b51449a7f4f718775c1a1d92eb24252cc9a062ee37ecfb190696f5cc12c5018` |
| `motor-settings.json` | 6,143 | `2a6e604e460f8f8ecdc8f3e7ddaf4332652e49b8d4b16a19566fe3eb78ea7099` |
| `motor-settings.v1.json` | 5,708 | `8955d5b83fd0e8d4480d9cd3fd5be4498bc67892d789713568cc0a7c6c01e84d` |
| `segments-evidence.json` | 23,536 | `b7d89667a92e988a370de213d6ae8776ac31492fc9f6f60ca17cd73002e80fbd` |
| `owner-verdicts.json` | 9,634 | `c87ec4ced324aa7f34f384fbabe5dc9a06ba2886b25e577fd3e7f210fdf52d9b` |
| `provenance.json` | 47,309 | `ecfc042eb2f876f257e4486d668f319a8eee27e46ddd96ac71d660297e50fb5a` |
| `recorder-verification.json` | 1,207 | `b475d4e3e02be47bc54dd69d7cd1ed0e1b3be46a41795c208c6538921daf8d99` |
| `input-profile.json` | 1,587 | `68fd2bbd41801a1e1a6127388c490fb91a4b26bfe146945060482477504ad600` |
| `slot-mapping.json` | 259 | `98cc2121f166817ab81ea07a2006959f5e8b4d68c015daae58c0836a8b7861cc` |
| `hud-scan-samples.jsonl` | 843,897 | `2639802cb59aafc600c2119b73ec4d35842bcde8f9a42afedfa82fe2f43f7e0b` |
| `regime-timeline.json` | 10,308 | `1c1920e169dc54c41e22bf01b535a5998cbced8cbdc47a1e730ccf63e618a842` |
| `candidates-pass1.json` | 2,084 | `52797f46255c9eb23b5c88bf34b2641afb824ed8708f6fec940924f20c9e3278` |

`review-frames/` (34 files) is not pinned by the freeze, as for the admitted sessions; its hashes are in
`segments-evidence.json`. The tally row and landing list are in final-20.
