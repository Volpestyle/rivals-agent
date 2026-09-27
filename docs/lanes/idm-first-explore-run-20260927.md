# First EXPLORATORY IDM run: staged plan and blockers

Owner: idm-owner, VUH-1353. Prepared against intake commit `54bae68adf56ad1cbe77713937b9f51d7c99a9af`. Updated scope follows the lead's Swarm request to fit the first useful run within roughly 100 GB. No fit, decode, feature extraction, game input, deletion or commit was performed. V-C, V-Q and sealed Gate 2 payloads stayed closed; shared registry metadata was used for exclusions.

## What can launch first

**An interim range refit is staged; the requested expanded match experiment is not launch-ready.** Reuse the seven existing native IDM camera/HUD stores. Fit the five allowed range sessions `051828`, `200129`, `232304`, `021320`, `025230` (80.53 admitted minutes); score frozen dev `171533` and `205528` only as heldout. This consumes almost no new store space. It is a runner/refit diagnostic, not a full-cohort result, new-match test, or Gate 2 result. A bounded smoke precedes the three-epoch fit; its 5,000-example prefix is explicitly not a cohort result.

For the **smallest useful seconds-context diagnostic**, prepare whole TRAIN `200129` (26.62 minutes) and `051828` (6.97 minutes): fit on `200129`, hold out the entire `051828` family. Compare S/L, seed 0, three epochs, Amazing Combo -0.2..+0.6 s with jump control, fixed A4 camera bytes and deployed pitch A. About 33.59 source minutes need **22.62 GB** of new grey/HUD/DINO stores; reserve 25 GB for them and metadata. This is a single-session training diagnostic, not the originally proposed replicated five-session experiment. Recount support after context trimming: under 50 train positives is unsupported; under 30 heldout onsets is undecided. The five-session 80.53-minute extension would need about 54.23 GB of new stores, still below 100 GB, once smoke throughput and admission justify it.

The short/long arms use identical longest-context eligible anchors, human targets, seed, optimizer, train-only thresholds and heldout family. Keep the requested +0.6 s Combo endpoint despite the measured 1.175 s p90 HUD lag; failure cannot rule out a longer window. No outline-derived labels enter this runner; the account-colour addendum still governs future detector use.

## Staged artifacts and commands

Mac root: `/Users/james/dev/idm-data/explore-20260927/`.

- `code-54bae68/`: isolated Git archive, no shared checkout changes. Archive SHA256 `dee64e3ac6235f8cbef63ca2799146297d94fc3f535080245d5edd9bbaaa5e01`, verified at both ends (3,553,280 bytes). Only code plus required registry/denylist/patch metadata and kit documentation was transferred.
- Private `.venv` built offline from the locked execution group: torch 2.14.0, numpy 2.5.3. MPS reports built/available; no GPU operation was run while H1 owns the Mac. The 35 imported code-file hashes match the accepted `569a16b` runner exactly, including in this private environment. Existing independent acceptance therefore applies to unchanged code; it is not acceptance of new match data.
- `refit-interim.json`: exact seven-source paths and raw target/frame-manifest pins, SHA256 `ba6e7fe44d8ec7977c4c34f36ef07c7adc63f6f6b71374855f99bd90080211c3`. Local copy: `data/idm/explore-20260927/refit-interim.json`. Targets and frame manifests were hashed; arrays and videos were not opened. Runtime still verifies array bytes and target/store bindings.
- `run-refit.zsh`: refuses invocation without an explicit operator release argument and refuses existing output/exit paths. Local SHA256 `2b8dc5890efa73479d81499b7b9d7df8ed2b4a9377b6e8461ca1ceb5458c6f45`; Mac shell syntax check passed. No auto-start or polling.

Exact **Mac** launch after the lead/owner explicitly releases the slot:

```sh
cd /Users/james/dev/idm-data/explore-20260927
nohup nice -n 10 /bin/zsh run-refit.zsh --mac-released smoke </dev/null >launch-smoke.log 2>&1 &
echo $! >launch-smoke.pid
```

After smoke finishes, check `.exit`, artifacts, exclusions, device and memory/throughput before the full interim fit:

```sh
nohup nice -n 10 /bin/zsh run-refit.zsh --mac-released full </dev/null >launch-full.log 2>&1 &
echo $! >launch-full.pid
```

The wrapper invokes `policy.idm.explore refit` with the exact manifest hash, MPS, seed 0, two OMP/MKL threads, three epochs for full, and 30/90-minute cooperative smoke/full deadlines. It writes separate console logs, PID and exit receipts. `/usr/bin/time -l` records elapsed time and peak RSS. The runner applies nice +10 as well. Deadlines are checked at progress boundaries, not a hard watchdog; hash operations or final scoring can overrun before the next check.

Each fit uses the existing `scripts.job_status.write`, owner `idm-owner`, host `mac`, running/progress/done/failed, absolute run log, unknown ETA. Names are `idm-refit-interim-smoke-20260927-01` and `idm-refit-interim-seed0-20260927-01`. Their receipts go under `~/dev/jobs/`. Watch for quiet phases approaching the 30-minute heartbeat limit and publish a truthful heartbeat if needed. A done receipt means process completion only. Metadata preparation has its own done receipt `idm-explore-preparation-20260927`; it explicitly says no fit or decode.

The edge command will be, from the same code snapshot, after its assets and produced-store hashes exist:

```sh
.venv/bin/python -m policy.idm.explore edges --manifest /Users/james/dev/idm-data/explore-20260927/edge-051828.json --manifest-sha256 FINAL_EDGE_MANIFEST_SHA --out /Users/james/dev/idm-data/explore-20260927/edge-051828-seed0-01 --job-name idm-edge-051828-seed0-20260927-01 --device mps --seed 0 --epochs 3 --walltime-minutes MEASURED_SLOT_MINUTES
```

That edge command is deliberately **not executable yet**: its manifest pins cannot be fabricated before preparation. Build its source manifest from the two exact admitted identities above; prepare with the reviewed `prepare` command, then pin produced `frames.json`/`features.json`. Never substitute CM3's 30 Hz feature caches for the IDM's 60 Hz recipe. Frozen-dev sources stay out of edge preparation and scoring.

## Runtime, RAM and disk estimates

These are forecasts, not new Mac measurements. The historical camera cost of .0029 s/example implies about 42 minutes for three passes through 80.53 minutes at nominal 60 Hz; budget **60–90 minutes including checks/scoring**, to be replaced by smoke timing. Initial smoke can take 10–30 minutes because it still checks stores and scores heldout data. Budget 4 GB active MPS memory and initially 12–24 GB process/host working memory for Python target objects, contexts and mapped pages; these are unverified envelopes, not enforced caps. Monitor actual RSS and MPS usage before expanding.

The 33.59-minute edge pilot has nominally 120,923 source frames. At the research memo's provisional 30–120 feature frames/s, extraction alone is about 17–67 minutes. Historical decode rate adds roughly 24 minutes if sequential; the actual fused single-frame preparation can be slower. Reserve **1–3 hours for preparation** and provisionally **0.5–2 hours for paired S/L fits, threshold calibration and scoring**. Start with a bounded preparation measurement before accepting that forecast. Cached-head active MPS budget is 2–4 GB; mapped pages/host objects are additional. DINO's single-frame implementation is not benchmarked here.

The new store costs `(448*252 + 80*200*3 + 6528*4) * 3600 = 673,372,800 bytes` per minute at 60 Hz, before indices and transient files. Full allowed range alone (166.92 minutes) is about 112.4 GB if regenerated, before the new matches or originals. The measured free space was 158 GiB. Reusing existing refit stores and bounding edge preparation avoids that immediate capacity problem.

## Match intake: precise remaining boundary

The registry at `54bae68` contains **16 idm_train files, not 16 ready live matches**. [Local roster](../../data/idm/explore-20260927/match-roster.json) records all IDs, media pins and reasons using registry metadata only.

- Six older potential live sources: `005304`, `010620`, `012552`, `013711`, `015610`, `021321` (20260926).
- Eight new potential live sources: `051206`, `052001`, `053118`, `053838`, `055006`, `060021`, `061107`, `061900` (20260927, logger suffixes 4–8 and 10–12).
- `20260926T161008-331Z-116800-2` / 11-10-08 is replay-of-self, excluded from the live-target builder; it needs independently reviewed live-target alignment, not viewer inputs.
- `20260926T034805-307Z-63684-13` / 22-48-05 still has `training_pending`: its own main-account motor/identity/calibration statement is required. No released file is reclaimed.

**Missing prerequisite:** an independently accepted `rivals-idm-match-admission-v1` JSON receipt for the candidate live sources, with per-session media/family, imported-demo and step-table hashes, canonical identity digest, and motor-statement hash, together with those actual admitted artifacts. No such receipt or imported match directory was found in the inspected local session root or Mac IDM input/store roots. Admission-owner has been asked for any alternate location; absence elsewhere is not proven. The new registration/media-hash LAND is not this fit admission. A receipt destination may be `/Users/james/dev/idm-data/explore-20260927/match-admission.json`, but no file or acceptance at that path is claimed.

Mac inventory found seven native camera/HUD stores (the interim five plus frozen dev) and no stores for the fourteen prospective live matches or the three expanded range sessions. The latter have policy artifacts under `range-bc-data/explore/{sessions,steps,originals}`; compatibility/import pins still need checking before IDM target creation. DINOv2-small assets/config pin have not been located; both the old IDM and explore-policy execution environments lack transformers/safetensors. Explore-policy confirms no verified asset location or approved scratch cleanup. Use the existing supplemental dependency pins and model identity, not a different backbone.

**Launch status:** code/private environment/interim manifest/wrapper are staged. Still required before first fit: explicit Mac release, device smoke and real target/store preflight. Before edge work: pinned DINO assets/environment and preparation smoke/store manifests. Before expanded match work: the accepted receipt plus imports/tables, verified Mac originals and capacity forecast. H1 and Modal upload remain active; none was stopped.

## Space candidates for the lead and owners; no deletion performed

Allocated sizes from read-only `du -sk`, GiB rounded. Parent/child rows overlap; do not sum them. These are candidates to discuss, **not verified disposable artifacts**.

| Path under `/Users/james/dev/range-bc-data/` | GiB | Decision needed |
|---|---:|---|
| `caches/` | 3.36 | Ask policy owner whether the older cache generation has any remaining consumer |
| `caches15/` | 33.61 | Frozen interim cache; keep while active runs/uploads or review receipts depend on it |
| `runs/` | 0.94 | Retain accepted checkpoints/reports; owner can identify reproducible leftovers |
| `code-*.tar` archives (seven measured files) | 2.50 | Possible duplicates of extracted snapshots; confirm recovery and provenance needs |
| Extracted `code-*` directories (eight) | 8.14 | Mostly snapshots/native environments; only owners can identify obsolete ones |
| `explore/` total | 107.12 | Active H1 and Modal input tree: preserve |
| `explore/caches/` | 30.92 | Active source caches: preserve |
| `explore/interim-chunks26-seed0/` | 0.14 | Superseded run candidate; keep evidence/checkpoints until owner disposition |
| `explore/uv-cache/` | 0.61 | Rebuildable cache candidate, subject to active setup/upload use |
| `explore/transfer/` | 0.14 | Possible redundant transfer bundle; owner must verify completed destinations |
| `handoff/modal/` | 33.85 | Active round-3/Modal work; contains possible repeated packets but no deletion is inferred |

Raw inventories and staging receipts are under local `data/idm/explore-20260927/`. No original footage directory was sized recursively and no clip-library source was touched. The obvious small old outputs do not by themselves solve full-cohort capacity; the bounded run is the immediate route.
