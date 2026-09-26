# fit-interim-launch (VUH-1346, VUH-1359): the interim queue is running

**Interim scaling-curve point, not the real fit. Nothing from it is a policy acceptance or a live-pilot candidate.**

**Queue started 2026-09-25 14:45:17 CDT** on the Mac: `nohup nice -n 10 zsh -l …/interim94/queue.zsh`, pid 31539,
launched from Git Bash ssh with `ServerAliveInterval=15`.
- Pre-registration: `fit-interim-prereg.md` (`8094bdd1…`), approved with all three decisions.
- Queue script sha256 `a79e06b9…`.

**The six invocations, in order.** Each is both arms with one seed; the queue stops at the first failure.

| # | Run | Train | Seed |
|---|---|---|---|
| 1-3 | `runs/interim94-seed0`, `-seed1`, `-seed2` | the five train sessions, 80.53 counted min | 0, 1, 2 |
| 4-6 | `runs/interim94-control47-seed0`, `-seed1`, `-seed2` | 051828 + 200129, 33.59 min | 0, 1, 2 |

**Every run's settings:**

| Setting | Value |
|---|---|
| scope | plumbing |
| device | MPS |
| arms | `model_nohud`, `history_only` |
| epochs | 13 |
| weight decay | 1e-4 |
| stride | 64 |
| lag | 0 |
| batch | 8 |
| lr | 3e-4 |
| regimes | normal |
| dev | 171533 + 205528 |
| `--hud-parity` | `interim94/hud-parity-1-p2.json`, sha256 **`e9efe999…`** (the exact CRLF bytes, checked on the Mac) |
| code | `code-5d2ec29`, the git archive, `014f6ae4…` on both ends; torch 2.14.0, MPS available |
| sealed denylist | the pinned default |
| patch equivalence | the pinned default (`4df869f3…`), both builds, one kit version |

- **Status:** `interim94/queue.status`.
- **Per run:** `runs/<name>.log`, `runs/<name>.exit`.

## The seven caches: every one re-hashed in full against today's step tables before launch

This makes up for the plumbing scope's `cache_hashes_verified: false`. Full hashes in `verify-7.json`: sha256
`d23b8b9efee7faeea469d3f10b4bf4ed5d765d00ceded4a2645edf9417a889d7`, in the scratchpad `interim94\` and on the Mac.

| Session | Step table | Rows | global_sha256 | crop_sha256 | hud_sha256 |
|---|---|---|---|---|---|
| 051828 (train) | `d49224e3…` | 12,558 | `630da1532e8a9bc26c2630d41a9b53fe121bd4e6f43d9c8b69d062d75b7c331b` | `8340d6c35bb70be05efdbac718964730297be310415fa7774e3f5eadb19c3579` | `f7f0e718f2a3948b5ff98c2a026eb08b663238f1fe7c8bb772122269d6f0b445` |
| 200129 (train) | `fcc9b044…` | 48,195 | `56b6aa8f3239f69b626d6fbcd137c64ba036e697df5151a2177c6cfc10d387bb` | `e9aee92463112a6ae7c308b74e41e5db3cd3d7ebb057932c2bfa11d2686e413f` | `6433d9ae31a7b96d594412b37c9ade6f969bfc6fe6b2a8d4df6c163ff06369ec` |
| 232304 (train, new) | `8a6c63d4…` | 15,841 | `b925de72acccdfef74873cbd9d7c2745bc76dcf8c785e8344d793d5e611dd65a` | `3499aa3628b80d243fa80dd558f2a974b5d1bc855c805c9638c3334d798a97da` | `3c37df0ea20389b09e2affbb99566afc77954bb9e17ac1eef3afb8e9a1590980` |
| 021320 (train, new) | `841fe695…` | 65,702 | `5e42e5cebed590bd9cf30c6204af51107855bc23d2a76417f7a61d1808875188` | `5892f4d2c757874d0addb2ff31b61d286e248a3db198929ecf97dca6d693b94c` | `92ccf4171291f833cf808fef24a1c70ff42b1edc36f4b1c7d90fa9b50fd57af1` |
| 025230 (train, new) | `84cef39b…` | 6,667 | `db12444cc6c430a8618b4ffd99c43a76e139e4b10b16c040a0bca56870259363` | `2ad26159e9d04b6143351a4d034e5deb4038eb4084754f85de3b639d2439322c` | `13ccd92646271ec31797d508fa988c5333071f06350b6fe397486cbcd710f102` |
| 171533 (dev) | `dc28b0c1…` | 4,800 | `9738d5655f1925ecf3912fbdbc2daa178711ebea13ac84052210671a83823965` | `e27d552f87ce61847ca0f3fde94721c7d81ce316cecefcaf823585ae3988d979` | `9638a22ce9ed2e4334db8530a9fbb4afd88b61f08174b9acfe4923ba2247b16f` |
| 205528 (dev) | `941950f1…` | 19,935 | `7a45e68f826f948e2f98553f38c07255f39c649bdc8042d03f10429886653dfd` | `faa6c01d51b7d687f97e96265cbf615dcd4ef8041f00f9cf51636bac0bb39ad1` | `889f0a65c01b1e43565a0937954bbf7189fc4f40096c6da934078592505575b0` |

- **The four earlier caches were reused.** Their hashes equal the plumbing and smoke record (for example, 051828
  `630da153…`, 171533 `9738d565…`).
- **The three new ones** were built with the landed `policy.range_bc.cache` from `5d2ec29`, Homebrew ffmpeg 8.1.2.

**Media.** For each new video, the logger files and the step table:
- the video's sha256 equalled `expected_media_sha256` on Windows before sending (58f8e234…, a1a89dd3…, c6adfd57…);
- all were re-verified with `shasum -a 256` on the Mac;
- copies only; the originals were not moved.

## Expected finish

| Milestone | Estimate |
|---|---|
| The three 94-minute seeds (the scaling point), about 50-60 min each | about **17:30-17:50 CDT** |
| The three control seeds, about 24-28 min each; queue DONE | about **18:45-19:30 CDT** |

- **Basis:** the plumbing record's per-step time (about 0.72 s per no-HUD step with dev passes).
- **The range includes contention (see below).** I will refine it from the first epochs in the poll log.
- **Monitoring:** a 10-minute Git Bash poll until DONE or FAILED. Then collect, check each report's config and
  `hud_parity.sha256` against the pre-registration, and write `fit-interim.md`.

## Noted at launch

**Contention.** The IDM lane's queue was running on the Mac beside me:
- `idm-data/jobs/run.zsh stores-new`: frame stores for the same three new sessions, niced, 4 ffmpeg threads, reading
  our transferred originals;
- `run.zsh confirm`: 21 inference passes, "No training".

These are inference and decode jobs, not a competing fit, so I launched. They share CPU, GPU and disk with the fit,
and can slow it but not change its results. If you want the Mac exclusive, the queue can be stopped and restarted at
the next seed.

**One bug of mine, fixed before any run.** My first transfer script sent only the first session: `ssh` inside a
`while read` loop consumed the rest of the list from stdin. It now uses `ssh -n`, and `scp` reads from `/dev/null`.
All three sessions then transferred and verified.

## Parking

Parked until the queue ends. No other work is running from me.
