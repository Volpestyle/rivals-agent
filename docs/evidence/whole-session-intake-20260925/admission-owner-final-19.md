# admission-owner final 19: 232304 admitted (train, 8.77 counted min)

**Assembly.** `20260924T232304-170Z-12024-1` was assembled on 2026-09-25 from **`code-snapshot-b7d4592`**, with the
reviewer's **v2** record `8a504cbd…` (against the edge-rule re-emission; it supersedes `3cfeeace` for assembly).
- **Freeze:** checks clean; 23 folder files, 9 external.
- **Pinned alongside the current files:**
  - `motor-settings.v1.json` (`14334d6b…`);
  - `segments-evidence.v1.json` (`504e11fa…`);
  - `owner-verdicts.v1.json` (`452c4381…`).
  Each is named by sha256 in its successor's `supersedes`.
- **The motor pointer:** the v2 evidence's `motor` names the current record (`46e82b4f…`).

**What it holds.**
- **Accepted:** seg-002 (320.51 s, opening on f310 under the edge rule) and seg-005 (205.42 s); **8.7654 counted min**
  (2 runs).
- **Trainable:** 8.7650 min.
- **Step table:** 15,841 rows, 15,777 accepted and gap-free.
- **Import:** 63,666 decoded frames, 63,665 referenced. `unknown_composition` holds:
  - packet 38775 (file pts 323138), a duplicate of packet 38770, 5 packets apart;
  - slot 323.243–323.260 s in logger time, inside rejected seg-004 (323.235–323.260 s).
- **Header:** patch `1.1.3892207/build25501035`, settings `a8dea3ba…`, sitting 2026-09-24-early-evening.
- **The fit's reader** loads it with the other five tables (see final-18).
- **These bytes equal the rehearsal's** (step table `f60f7f75…`, minutes `5a46215c…`) except where the snapshot and the
  N3 wording enter:
  - the step table's `source` (`8a6c63d4…` here);
  - the review and import audit text;
  - the freeze.
  The accepted rows and minutes are identical.

## Bytes (`data/human/sessions/20260924T232304-170Z-12024-1/`, all LF)

| File | Bytes | sha256 |
|---|---|---|
| `20260924T232304-170Z-12024-1.steps.jsonl` | 10,744,594 | `8a6c63d4024b13d5b73ab0154f434782e6cfc853d6eaa8291bd9fa8ca8f3b1b1` |
| `artifact-hashes.json` | 5,290 | `ccdf62482e72739dffa373371ceb3ba9a5c382c340bf07129b5613647d1a1fb6` |
| `review.json` | 11,943 | `80a049d44e05a82fc97c106109bddd6b0492beee185811b25c204da7884baf89` |
| `settings.json` | 5,068 | `ebbfa839979d577256945695c2b6fe408d8c6abb1ffbf3f147d93777ca11ba13` |
| `imported-demo.jsonl` | 33,345,496 | `1cde21bdd67b88102199b104df6fec826aa0f2c7147c55dd9896b2376ed07d5c` |
| `sampling.json` | 639 | `243f9265474b2dbe084723f632a9894bc2dc1ef2e3126f3b7e4b472c690c4de1` |
| `minutes.json` | 966 | `5a46215cfae3406d272571dd2e9a7b996ba8be8d781154e2a193331c18bff005` |
| `recording-log.dfbb4dd.md` | 7,747 | `25c9f622155726df96d5ab33bd021288630a74656b6a18d3dbf9748d41f4b799` |
| `registry.f36e9e3b5650.json` | 8,492 | `f36e9e3b565041cbd719d3d4c6b80033d66a685a599f3b6607e67bab3ee574fb` |
| `independent-review.verdicts.json` (v2) | 39,000 | `8a504cbdd6321c771553fe6c39ddfa9aa719ab9153a64c7e223c2472d9a04529` |
| `independent-review.md` | 11,523 | `27e60855cfbdda8da0389734230cf6f51fb1e012116df36c5b8b3d715920969c` |
| `motor-settings.json` | 6,146 | `46e82b4f110d514996625c5824dce7105e076863b4763e3e534b1554577201eb` |
| `motor-settings.v1.json` | 5,711 | `14334d6bcea838140f58f0710ee7e94559c8c17d1e3d16661700c02ffa63761d` |
| `segments-evidence.json` | 45,796 | `939c3a5154cebb453bcb480b7089e4967f909f3c93b48b67d18bd9f07315d48d` |
| `segments-evidence.v1.json` | 40,620 | `504e11fa998b52005dc46e8de5219faecf838137273bccf8223684a0ce6d01c2` |
| `owner-verdicts.json` | 16,217 | `a9ec8cb3c2e85c73ab91f0d0179d606bed6ddaf62fe1f2aadf230bbead391eab` |
| `owner-verdicts.v1.json` | 16,020 | `452c438141bfad119b6d20ea39857283c57de12beac9044ea5fcdfa80450a4db` |
| `provenance.json` | 47,311 | `9e2825039380f24929e9d969989f0ebe2490eee877a041e95f3b80f33b5b8bb4` |
| `recorder-verification.json` | 1,208 | `5ca18044e68600c646a3a5c5e5c3b4ec5d8792fc030cc5f4d93bf863d0684319` |
| `input-profile.json` | 1,602 | `1e78e5bd9c078ec83efbabef7b2ff02abdf84ed418c1078c52f380c02d7b8662` |
| `slot-mapping.json` | 260 | `e2f10206ae497a837358e3c092413d1a83056b6955496752a379da8850cb6aca` |
| `hud-scan-samples.jsonl` | 2,000,477 | `eb6a2d0f0cdd951d77dd99ed68a7cd45ea90509c9832f22174540b595beab415` |
| `regime-timeline.json` | 23,842 | `b67fd6dd3468e271ea2e6047c4446fda185f4e4105ca7bb953495fcd05d7febc` |
| `candidates-pass1.json` | 2,254 | `c6dab7e32a5242858d0052b501d74f34f68f6482daf847ebd380f274e656d06c` |

`review-frames/` (68) and `review-frames.v1/` (68) are not pinned by the freeze; their hashes are in the v2 and v1
evidence. The tally row and landing list are in final-20.
