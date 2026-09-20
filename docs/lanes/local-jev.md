# Local Jev on the Mac (2026-09-20)

Research only: nothing here was installed, downloaded or run. Every number is a
claim from a README, model card or issue, checked against the repo's own files where
a README and the code could disagree. Repo state was read on 2026-09-20.

## Recommendation

Run **snapjudge** ([Micha0827/snapjudge](https://github.com/Micha0827/snapjudge),
MIT) on the Mac with `mlx-community/Qwen3.6-35B-A3B-4bit`, serving `POST /v1/systemone`
on the LAN. It is the "read next-token probabilities over option labels" route,
already written for MLX, with our wire shape and a cached question prefix that fits
a fixed intent vocabulary. It also publishes a game-decision benchmark run over HTTP on
Apple Silicon: median 78 ms against a 0.5 s budget on an M2 Max.

The simplest route is not a separate option: a hand-rolled `mlx-lm` scorer would
reimplement what snapjudge and system-one already do (see "The hand-rolled route").
Keep it as the fallback if the acceptance gate below fails.

Three caveats decide how far to trust this:

1. No source measures logit-read latency on an **M5 Max**. The nearest are an M5 Pro
   (64 GB) and an M2 Max (96 GB). The gate below measures it from the PC.
2. snapjudge is two commits and one author, two days old. Pin the commit and read
   its four Python modules (`cli`, `engine`, `prompts`, `server`; about 690 lines).
3. No agreement number exists for our task. Every "agreement with Jev" figure below
   is on TypeSafe's public support, invoice and security cases, not on Spider-Man
   intents.

## What `agent/jev.py` needs from a server

| # | Requirement | Where it is in `agent/jev.py` |
|---|-------------|-------------------------------|
| R1 | `POST` JSON `{model, state, questions}`; questions are `choice` with `instructions` and `criteria` (`name -> description`); one request carries `intent`, and `target` and `anchor` when offered | `questions()`, `Jev._request` |
| R2 | The `criteria` descriptions reach the model: they are the whole intent vocabulary and state each intent's preconditions | `INTENTS` |
| R3 | Response `answers[q]` has `choice` (string) and `probabilities` with a key for **every** option (a missing option counts as 0 in `_best`); `confidence` is optional | `_answer`, `_best` |
| R4 | `usage.input_tokens` and `usage.cost` are read if present, never required | `Jev._count` |
| R5 | Transport is HTTPS to `openrouter.ai` with a Bearer key, hard-coded in `HOST`, `PATH`, `_Session.post`, `load_key` | needs a change, see below |
| R6 | `model` is sent as `typesafe/jev-1.13`; the server must accept or ignore it | `MODEL` |
| R7 | Budget: blocking `TIMEOUT_S` 0.2 s; `AsyncJev` drops an answer older than `MAX_AGE_S` 0.6 s | constants |

Measured against real Jev from the dev Mac (`docs/lanes/l5-brain.md`): round trip
p50 237-250 ms, p95 322-393 ms, fastest 154 ms. A local server has to beat that to
be worth running.

## Comparison

Tags: **S** sourced from the README or repo, **D** derived here, **U** unverified.
"Wire" is the fit to R1-R6.

| Candidate | Model, size, licence | Apple Silicon | Claimed latency | Agreement vs Jev (published) | Maturity (2026-09-20) | Wire | Verdict |
|-----------|---------------------|---------------|-----------------|------------------------------|----------------------|------|---------|
| [razorback16/openjev](https://github.com/razorback16/openjev) | DiffusionGemma 26B-A4B; 4-bit MLX about 16 GB (**S**); code Apache-2.0. README says the weights are Apache-2.0, JoshuaSP's README says Google's terms: **U** | Yes: `OPENJEV_BACKEND=mlx`, in-process via `mlx-vlm`, one read at a time; no images, `think` or `steps > 1`. vLLM path needs an NVIDIA GPU with 24 GB or more (**S**) | MLX: 0.2-0.4 s per 3-question request on an M3 Ultra, about 0.39 s on an M4 Max. vLLM on an RTX PRO 6000: 94 ms p50 at concurrency 1 (**S**) | None | 17 commits, created 2026-09-18, 198 stars, 2 open issues. vLLM path needs unmerged PR #57250 | R1-R4 yes (`/v1/systemone`, choice up to 128 options). **R6 fails**: `typesafe/jev-1.13` answers 400 `Unknown model`; send `jev-latest` | The MLX claim is no faster than Jev. Not first choice |
| [GitHub30/OpenJev](https://github.com/GitHub30/OpenJev) | Any HF instruct model; README examples Qwen2.5-1.5B and 7B; MIT (switched from Apache-2.0 in the last commit) | Not documented. `backends/hf.py` picks `cuda` if available else `cpu`; a `device` argument exists, so MPS may work (**U**) | None | None | 8 commits in 45 minutes on 2026-09-20, 0 stars, 0 issues, no user reports | R1-R4 by README (`choice`, `probabilities`, `confidence`); `model` handling **U** | Too new, PyTorch not MLX |
| [ekzhang/openjev-sglang](https://github.com/ekzhang/openjev-sglang) | Qwen3.6-35B-A3B on SGLang 0.5.19; **no licence file** | No: B200 and Modal | "64 tasks in under a second" (tweet, on a B200); README gives no numbers | None | 18 commits, 221 stars, 3 issues, last push 2026-09-18 | R1-R4 yes; accepts `jev-latest` | CUDA only; the PC's 16 GB card cannot host it |
| [JoshuaSP/open-jev](https://github.com/JoshuaSP/open-jev) | DiffusionGemma 26B-A4B BF16; code MIT, weights Google's terms | No: H100 on Modal; research harness | 30.4 documents/s, 182 judgments/s at batch 16 on an H100 | 87.8% (2-step grouped) vs saved Jev 90.8% on 337 scored questions from 20 public cases; references are model-derived; it never called the Jev API | 3 commits, 20 stars, 2026-09-16 | No HTTP API: Python harness and `modal run` | Useful as a benchmark reference only |
| [com-kotobalabs/open-jev-deberta-v3-large](https://huggingface.co/com-kotobalabs/open-jev-deberta-v3-large) | DeBERTa-v3-large, 0.4B, Apache-2.0; trained on banking77, SST-5, BoolQ | CPU only shown: 1.8 s for 4 questions on an M1 Max (fp32). MPS **U** | 28 ms for 10 questions on an H100 | Says its numbers "are not comparable" to Jev's; in-domain accuracy 0.854, out-of-domain 0.690 | 405 downloads last month, 1 discussion | No HTTP API: `OpenJev.from_pretrained()` | Trained on customer text; would need retraining on game states |
| **[Micha0827/snapjudge](https://github.com/Micha0827/snapjudge)** | Qwen 3.5 family via `mlx-vlm`: recommended `Qwen3.6-35B-A3B-4bit` (about 20 GB), `Qwen3.5-4B-MLX-4bit` (fits 16 GB); weights Apache-2.0; code MIT | **Yes, MLX only**; one request at a time | **78 ms median** (English), 83 ms (German) on a game benchmark over HTTP, question-first layout, M2 Max 96 GB; 174-182 ms for the 4B, 242-274 ms for the 35B-A3B on longer states (1-4 questions per request) | Qwen3.8-27B 81.2%, Qwen3.6-35B-A3B 77.5% vs Jev 87.7% on 373 decisions from TypeSafe's 20 public cases (reference: GPT-6 Astra + Fable 5.1 consensus). Level with Jev on short texts, behind on long documents | **2 commits, 1 author, 7 stars, 0 issues**, created 2026-09-18, pushed 2026-09-19. Thorough README and evals | **R1-R7 yes** (read in `server.py`, `prompts.py`, `engine.py`): descriptions rendered as `- key: desc`; `probabilities` for every option; `usage.input_tokens`; `model` accepts any string; `--host`, `--api-key` | **Recommended** |
| [snellingio/system-one](https://github.com/snellingio/system-one) | `mlx-community/Qwen3-1.7B-4bit` default; `Qwen3-4B-Instruct-2507-4bit` "larger" profile; MIT | Yes, MLX, FastAPI | None published | None | 19 commits, 39 stars, 2 issues, last push 2026-09-18 | Choice, score, noul; `/v1/systemone` alias; descriptions shown in its examples (**S**) | Second choice: smaller models, pure attention |
| [bnsd55/jevmlx](https://github.com/bnsd55/jevmlx) | Qwen2.5-7B-Instruct-4bit default, 3B `fast`; MIT | Yes, MLX; serial worker | None; its benchmark leaderboard reads "No local results yet" | None | 100+ commits, 8 open issues (drift and A/B holds), issue #63 plans an M5 Max run | R1 yes. **R2 fails**: `_systemone_to_schema` keeps only the `criteria` keys and drops their descriptions. **R3 at risk**: `probabilities` come from `top_choices`, described as "top 3" (**U** whether all options are returned) | Active, but does not fit our request as it stands |
| [daseinlabs/open-jev](https://github.com/daseinlabs/open-jev) | Gemma 3 4B (gated HF download); **no licence file** | Yes, MLX | About 90 ms per request; 0.17 s with the context cached once, on an M5 Pro 64 GB bf16 | None; compares one quick-start request against Jev's docs only | 9 commits, 68 stars, 3 issues | Choice, score, noul on `/v1/systemone` (**S**) | No licence, so reference only. Its frozen-feature head trains in about 15 s and runs in under 10 ms (**S**), a route for later |
| [bespokelabsai/nimble](https://github.com/bespokelabsai/nimble) | Qwen3.5-9B LoRA (`Bespoke-Nimble-9B`, Apache-2.0); MLX runner does not load quantized weights | Yes, as a Python `ParallelScorer`, bf16 | **444 ms median**, 981 ms p95 on an M5 Pro 64 GB; 106 ms on an H100 | 90.1% vs 93.2% for Jev on 324 held-out examples from its own curated data | 6 commits, 1,044 stars | No HTTP server on Mac (Modal + SGLang serving is CUDA) | Slower than Jev on a Mac; no server |
| [githubnext/localjev](https://github.com/githubnext/localjev) | Any oMLX model; asks the model to write JSON probabilities | Yes, via oMLX | p50 0.52-0.89 s (4-bit Gemma and Qwen) and 1.21 s (DiffusionGemma) on an **M5 Max 64 GiB**, short input | None | 3 commits, 601 stars | Wire yes; probabilities are **self-reported, not logits** | Wrong mechanism and too slow |
| [rorshopping/jev-on-a-laptop](https://github.com/rorshopping/jev-on-a-laptop) | Qwen2.5-1.5B and 7B, Qwen3-8B, MLX 4-bit | Yes (M5 MacBook Air 16 GB) | 147 ms (1.5B), 611 ms (7B), 646 ms (8B) per case | 73.8% (7B), 71.2% (Qwen3-8B) vs 86.6% for Jev on 343 pairs | 16 commits, 22 stars | Benchmark scripts, no server | Evidence only |
| [TheoLeeCJ/SemIf](https://github.com/TheoLeeCJ/SemIf) (was `openjev`) | Qwen3.5-4B logits; MIT | Yes: native MLX backend (`docs/MLX.md`) plus a WebGPU demo | 1.02 s for 21 questions on an RTX 3090 (CUDA); its MLX numbers not read | 84.5% vs 88.3% for published Jev, modal agreement on a 102-row subset of TypeSafe's 20 public cases (its own metric) | 12 commits, 2,407 stars, 13 issues | README shows a scoring CLI, no `/v1/systemone` (**U** in the source) | Not a Jev-wire server |
| Small trained encoders: jeff (GLiFormer-large 400M), rlcd-modernbert-151m, Laya 421M, NanoJev 0.6B | 0.15-0.6B; licences per the tracker (rlcd-modernbert-151m Apache-2.0) | CPU/MPS **U** | jeff and ModernBERT cite under 35 ms on GPU | jeff: 66.9 vs Jev 75.3 on JevBench (tracker, self-reported) | Days old | jeff is a drop-in `/v1/systemone`; the rest are not | Accuracy well behind Jev on generic tasks; retraining on our states is the only fit |
| Hand-rolled `mlx-lm` scorer | Any Qwen3 or Qwen2.5 4-bit | Yes | **U**, nothing to cite | n/a | n/a | Whatever we write | Fallback, see below |

The tracker at [multimodalart/jev-reproductions-tracker](https://huggingface.co/spaces/multimodalart/jev-reproductions-tracker)
(Space last modified 2026-09-20, star counts snapshotted 2026-09-19) is one JS array
of about 50 artifacts. Its own summary: nothing open has Jev's weights or the RLCD
training, the best open scorers reach about 90% agreement with Jev on Bespoke's own
data, and confidence "does not reliably flag errors". The
[AbdelStark/awesome-typesafe](https://github.com/AbdelStark/awesome-typesafe) list
(last reviewed 2026-09-17) indexes SDKs, three reproductions (Luce, poorjev,
SemIf) and benchmarks; it adds no Apple Silicon server beyond what the tracker shows.
The razorback16 README also points to a hosted `api.codiv.ai`; a third-party host is
not local and is not considered.

## Latency evidence

Nothing below is on an M5 Max, and none of it uses our prompt.

| Hardware | Model and path | Number | Source |
|----------|---------------|--------|--------|
| TypeSafe API from the dev Mac | Jev 1.13, our request | p50 237-250 ms, p95 322-393 ms | `docs/lanes/l5-brain.md` |
| M2 Max 96 GB | snapjudge, Qwen3.6-35B-A3B, 38 game sentences, question-first | median 78 ms; state-first 397 ms | snapjudge README (2026-09-18) |
| M2 Max 96 GB | snapjudge, Qwen3.5-4B / 9B / 35B-A3B, SemIf authored-144 | median 174 / 320 / 274 ms | same |
| M5 Pro 64 GB | daseinlabs, Gemma 3 4B bf16, context cached once | 0.17 s; about 90 ms per request quoted | daseinlabs README |
| M5 Pro 64 GB | Nimble-9B bf16, one question | median 444 ms, p95 981 ms | Nimble README |
| M3 Ultra / M4 Max | razorback16 DiffusionGemma 4-bit, 3 questions | 0.2-0.4 s / about 0.39 s | razorback16 README |
| M5 Max 64 GiB | localjev prompted JSON (not logits) | p50 0.52-0.89 s | localjev bake-off, 2026-09-18 |
| M5 Air 16 GB | jev-on-a-laptop Qwen2.5-7B | 611 ms per case | its README |

The one large effect in the data: snapjudge's game benchmark drops from 397 ms to
78 ms when the fixed question comes before the changing state, because the question
becomes a cached prefix. Our request has that shape, with one exception in
`agent/jev.py`: the `target` question's criteria text embeds per-tick facts
(`"enemy, mid range, tag False"`), so that head changes every call. The same facts are
already in `state.targets`.

## The hand-rolled route

Answer to the lead's question: yes, it works, and it is what snapjudge and
system-one already are. The whole job is: build a prompt with the fixed question and
option labels first; prefill that head into a prompt cache once; per tick, run only the
state tokens through the model; take the logits at the last position; gather the token
ids of the option labels; softmax in float32; return `{choice, probabilities,
confidence}` per question. It is about 100-150 lines plus an HTTP handler.

What the existing projects add that is easy to get wrong: label tokenization when
labels share a leading token (`search` and `swing_to`), a capitalized variant of each
label, float32 for the final projection (snapjudge measures bf16 logits near 20 quantized
in steps of 0.125), and cache snapshots for Qwen 3.5's recurrent layers, which cannot
be trimmed. A pure-attention model (Qwen3, Qwen2.5) avoids the last one. The `mlx-lm`
prompt-cache calls (`make_prompt_cache`, `trim_prompt_cache`) are named from memory and
are **U** against the current release.

Do it only if the gate below fails on both snapjudge and system-one.

## Install and serve

Run on the Mac. Commands are unexecuted.

```sh
# 1. Get the code, pinned to the commit read for this doc (HEAD on 2026-09-19).
mkdir -p ~/dev && cd ~/dev
git clone https://github.com/Micha0827/snapjudge
cd snapjudge && git checkout 2df5ce2753b5
# Read snapjudge/{server,engine,prompts,cli}.py before installing.

# 2. Environment. Depends on mlx-vlm>=0.7.0, fastapi, uvicorn, numpy.
uv venv --python 3.12
uv pip install -e .

# 3. Optional: fetch the weights now (about 20 GB, Apache-2.0); serving does it otherwise.
uv run python -c "from huggingface_hub import snapshot_download as s; s('mlx-community/Qwen3.6-35B-A3B-4bit')"

# 4. A LAN key, kept out of argv and out of git.
openssl rand -hex 16 > ~/.jev-local-key && chmod 600 ~/.jev-local-key

# 5. Serve on all interfaces. macOS asks once to allow incoming connections.
SO_API_KEY="$(cat ~/.jev-local-key)" uv run snapjudge-serve \
  --model mlx-community/Qwen3.6-35B-A3B-4bit \
  --host 0.0.0.0 --port 8724 --name jev-local
```

Smoke test on the Mac, then from the PC (use the Mac's LAN IP; keep the Mac wired or on
5 GHz and note `ping` from the PC first, the LAN hop is unmeasured):

```sh
curl -s localhost:8724/health
curl -s localhost:8724/v1/systemone \
  -H "Authorization: Bearer $(cat ~/.jev-local-key)" -H "Content-Type: application/json" \
  -d '{"model":"typesafe/jev-1.13","debug":true,"state":{"hp":"high","web_ammo":3,
       "ready":{"swing":true,"pull":true,"uppercut":true},"crosshair_on_hostile":true,
       "targets":[{"i":0,"cls":"enemy","range":"mid","tagged":false,"under_crosshair":true}],"anchors":0},
       "questions":{"intent":{"type":"choice","instructions":"Which single intent should the Spider-Man fighter play next?",
       "criteria":{"engage":"Aim at the target, close in and fight it","pull":"Get Over Here! on an UNTAGGED target",
       "search":"No hostile worth fighting: look around","idle":"Do nothing this tick","disengage":"Break line of sight and get away"}},
       "target":{"type":"choice","instructions":"Which target should that intent act on?","criteria":{"0":"target 0"}}}}'
# PC (PowerShell): curl.exe http://<mac-ip>:8724/health
```

`"debug": true` adds timings, the top next tokens and a coverage value (probability
mass on allowed labels). Watch coverage: a low value means the model wanted a token
that is not one of our labels.

### Change needed in `agent/jev.py` (not made here; not this doc's file)

- `JEV_URL` (default the OpenRouter decisions URL), `JEV_KEY`, `JEV_MODEL`, read once.
- `_Session.post` builds `HTTPConnection` or `HTTPSConnection` from the URL scheme,
  uses its host, port and path, and sends `Authorization` only when a key is set.
- `load_key` must not demand `OPENROUTER_API_KEY` when `JEV_URL` is local.
- `questions()`: make the `target` and `anchor` criteria text static (`"target 0"`,
  `"anchor 0"`), since `state.targets` already carries the facts, so the question head
  stays cacheable. The saving is **U** until measured with `debug`.

### Acceptance gate

From the PC, with the change above:

```sh
JEV_URL=http://<mac-ip>:8724/v1/systemone uv run python -m agent.jev -n 200 --timeout 0.3 --hz 5
JEV_URL=http://<mac-ip>:8724/v1/systemone uv run python -m agent.jev -n 600 --async --hz 10
```

Adopt if the blocking run shows fallback rate under 2% and round-trip p95 at or under
150 ms (Jev is 322-393 ms), and the async run shows a `jev_share_of_choices` near 1 with
few `stale` drops. Otherwise step down the ladder:

1. Same server, `mlx-community/Qwen3.5-4B-MLX-4bit`.
2. system-one with `Qwen3-1.7B-4bit` (`uv run uvicorn system_one_lite.api:app --port 8010`
   from its `server/` directory; **U** whether its request body matches ours, read
   `docs/api.md` first).
3. The hand-rolled scorer.
4. Longer term: record real Jev and scripted-brain choices on live States, then train a
   tiny head on frozen features (daseinlabs reports under 10 ms; **U** for our task).

Latency is not the only test. Agreement with Jev on **our** States is unmeasured for
every candidate, and the scripted-agreement figure (62-65% for real Jev) is not a
proxy. A paired run, each bench State sent to both endpoints and the intent argmaxes
compared, costs about $0.007 per 290 Jev requests and gives the real number. It is not
built.

## Unverified

- Logit-read latency on an M5 Max for any candidate, and for our request shape.
- How snapjudge caches question heads when a request carries two or three questions,
  and whether a per-tick `target` question defeats the cache.
- Quality of Qwen models on Spider-Man intent choice; no benchmark covers it.
- Whether GitHub30/OpenJev runs on MPS; whether SemIf ships a Jev-wire server.
- razorback16's weight licence (README: Apache-2.0; JoshuaSP: Google's terms).
- jevmlx returning probabilities for options outside the top three.
- The LAN round trip between the PC and the Mac.

## Sources (retrieved 2026-09-20)

- [razorback16/openjev](https://github.com/razorback16/openjev): README, created 2026-09-18.
- [GitHub30/OpenJev](https://github.com/GitHub30/OpenJev): README, `pyproject.toml`, `backends/hf.py`, created 2026-09-20.
- [ekzhang/openjev-sglang](https://github.com/ekzhang/openjev-sglang): README, created 2026-09-17.
- [JoshuaSP/open-jev](https://github.com/JoshuaSP/open-jev): README, measured 2026-09-16.
- [com-kotobalabs/open-jev-deberta-v3-large](https://huggingface.co/com-kotobalabs/open-jev-deberta-v3-large): model card, page summary only.
- [Jev reproductions tracker](https://huggingface.co/spaces/multimodalart/jev-reproductions-tracker): `index.html` data array, Space modified 2026-09-20.
- [AbdelStark/awesome-typesafe](https://github.com/AbdelStark/awesome-typesafe): README, last reviewed 2026-09-17.
- [Micha0827/snapjudge](https://github.com/Micha0827/snapjudge): README, `server.py`, `prompts.py`, `engine.py`, `cli.py`, commit `2df5ce2753b5` (2026-09-19).
- [snellingio/system-one](https://github.com/snellingio/system-one), [bnsd55/jevmlx](https://github.com/bnsd55/jevmlx) (README, `serve.py`, open issues), [daseinlabs/open-jev](https://github.com/daseinlabs/open-jev), [bespokelabsai/nimble](https://github.com/bespokelabsai/nimble), [githubnext/localjev](https://github.com/githubnext/localjev) (README and bake-off report, 2026-09-18), [rorshopping/jev-on-a-laptop](https://github.com/rorshopping/jev-on-a-laptop), [TheoLeeCJ/SemIf](https://github.com/TheoLeeCJ/SemIf): READMEs and GitHub repo metadata (stars, commits, dates, licences) as of 2026-09-20.
- Hugging Face model pages for `mlx-community/Qwen3.6-35B-A3B-4bit`, `Qwen3.5-4B-MLX-4bit`, `Qwen3.5-9B-4bit` (Apache-2.0; existence checked) and `bespokelabs/Bespoke-Nimble-9B` (Apache-2.0).
- Our own side: `agent/jev.py` and the Jev section of `docs/lanes/l5-brain.md`.
