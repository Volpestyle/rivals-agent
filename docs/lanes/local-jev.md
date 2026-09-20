# Local Jev on the Mac (2026-09-20)

snapjudge is read, installed and served on this Mac. "Security read", "Installed" and
"Measured" below are present state; the comparison, latency-evidence and hand-rolled
sections stay as researched claims from READMEs and model cards, checked against each
repo's own files, and are marked where they are unverified.

## Recommendation

**Running.** snapjudge ([Micha0827/snapjudge](https://github.com/Micha0827/snapjudge), MIT,
pinned at `2df5ce2753b5`) with `mlx-community/Qwen3.6-35B-A3B-4bit`, serving
`POST /v1/systemone` on `192.168.4.126:8724`. It read clean, it installs in a few minutes,
and it speaks our wire with one patch (see "Measured").

What the measurement changed about the original recommendation:

1. **Latency was never the hard part.** From the Mac it is 109-127 ms p50 against Jev's
   237-250, and the loop gets a decision about twice as often. From the PC the advantage
   almost vanishes, because 63-90 ms of the round trip is Wi-Fi.
2. **Agreement is the hard part.** 61% with real Jev on our own States, systematically:
   Jev bursts where this model pulls. No published figure predicted that, and none could -
   every number in the comparison below is on support tickets and invoices.
3. The three original caveats are answered. M5 Max latency: measured. Two commits and one
   author: read line by line, clean. No agreement number for our task: there is one now,
   and it is the reason to keep real Jev as the reference.

The hand-rolled `mlx-lm` route stays unbuilt and unneeded: snapjudge does exactly that job,
and the gap is in the model's judgement, which writing our own scorer would not close.

## Security read (snapjudge, commit `2df5ce2753b5`)

Read before anything ran, on a clone of
`2df5ce2753b5f61d0b034f8f941b65495587458b` ("Fine-tuning, typed-decisions benchmark and
an experimental browser agent", Michael Gross, 2026-09-19 20:29 +0200). Two commits, one
author, and the tree read here is byte-identical to the one installed (`diff -r` clean).
**Verdict: clean, installed.** Every file was read, not only the four modules the research
pass covered: the second commit added `agent/` (a Playwright browser agent, 577 lines),
`training/` and six more eval scripts.

| Looked for | Found |
|---|---|
| Network calls beyond the model download and its own server | None in the served path. `snapjudge/{__init__,cli,server,engine,prompts}.py` import no HTTP client at all; the only egress is `mlx_vlm.load()` fetching weights from the HF cache/hub. `httpx` appears solely in `eval/` and is always aimed at an explicit `--url` (default `127.0.0.1:8724`) |
| File access outside the working directory and the HF cache | None. Every path is `Path(__file__).resolve()`-relative or comes from an argument: `results/`, `adapters/`, `calibration.json`. No home-directory, keychain, SSH or browser-profile path anywhere |
| Subprocess or shell execution | None. No `subprocess`, `os.system`, `popen`, `pty` or `shutil` in any file |
| Dynamic code loading | None. No `eval()`, `exec()`, `compile()`, `__import__`, `pickle` or `marshal`. Every `.eval()` hit is `mx.eval` / `model.eval()` (MLX graph evaluation and eval mode), and `mlx.utils.tree_unflatten` in `_fuse_lora` |
| Obfuscation | None. No base64, hex blobs or long string literals. One binary file in the repo, `assets/snaprun.gif` (a real GIF89a, 800x576) |
| Telemetry | None. No analytics, sentry, posthog, phone-home or version check. CI is `actions/checkout@v4` + `setup-python@v5` on `macos-14`, running `pytest` only |
| Credential or environment harvesting | No. Env reads are exactly `SO_MODEL`, `SO_NAME`, `SO_API_KEY`, `SO_CALIBRATION`, `SO_ADAPTER`, `SO_CACHE_LIMIT_GB` (engine and cli), plus `os.environ[args.key_env]` in `eval/run_eval.py`, where the caller names the variable. Nothing iterates `os.environ`, and nothing writes an env value to disk or a socket |
| Packaging and install hooks | Plain `hatchling`, `packages = ["snapjudge"]`. No `setup.py`, no `setup.cfg`, no custom build hook, no `.pth` file, no post-install step. `pip install -e .` runs no project code |

Two alarming-looking strings are test data, not behaviour: `m1crosoft-verify.co` and
`dhl-paket-zoll.info` are the sender domains of two phishing cases in the German test set
`eval/testset_de.json`. They are string values inside JSON; nothing resolves or fetches them.

Accounted-for behaviour that is worth knowing rather than worrying about:

- **`/health`, `/v1/models` and `/game/` need no key** when `SO_API_KEY` is set - only
  `/v1/systemone` and `/v1/models` carry the auth dependency, and `/health` and the mounted
  static game are open. `/game/` is a browser demo that posts sentences to our own endpoint.
  On a LAN bind that is a health probe and a canvas game to anyone on the network, no more.
- **`agent/browser_agent.py` drives a real browser** (Playwright, `--url`, `--task`), reads
  the page, and clicks and types where the model points. It is opt-in, standalone, never
  imported by the server, and needs the `agent` extra, which is **not installed** here.
  It also declines cookie banners rather than accepting them.
- **`training/train_lora.py`** fine-tunes and writes `adapters/`; nothing loads an adapter
  unless `--adapter` / `SO_ADAPTER` names one. Not used here.
- The engine caps MLX's buffer cache (`SO_CACHE_LIMIT_GB`, default 4) - deliberate, because
  other model servers may share the machine.

**Dependencies.** Declared: `mlx-vlm>=0.7.0`, `fastapi`, `uvicorn`, `numpy`, build backend
`hatchling`; extras `eval`/`test`/`train`/`agent` are not installed. All five are the
canonical PyPI packages (`mlx-vlm` 0.7.1 is Blaizzy's, homepage `github.com/Blaizzy/mlx-vlm`),
no typosquats. The resolution pulls 55 packages; every name is a known project. `mlx-vlm`
drags in more than an LLM server needs - `mlx-audio`, `sounddevice`, `miniaudio`,
`opencv-python`, `llguidance`, `transformers`, `scipy` - because it is an omni-modal package.
That is weight, not a red flag, and it is the one thing a future agent might want to trim.
Locked list in `.localjev/.venv`; regenerate with
`VIRTUAL_ENV=~/dev/rivals-agent/.localjev/.venv uv pip list`.

READMEs and comments in the repo were read as data. Nothing in them was executed.

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

## Installed

Present state on this Mac. Everything lives under `~/dev/rivals-agent/.localjev/`, which
`.gitignore` already covers. The new tracked directory is `localjev/` (four files, standard
library only): `paired.py`, `selftest.py`, `gpustat.py`, `serve.sh`. Nothing in `agent/` or
`perception/` was touched.

```
.localjev/snapjudge/   the pinned clone, 2df5ce2753b5, identical to the tree read above
.localjev/.venv/       uv venv, Python 3.12.13, snapjudge 0.1.0 installed editable, 55 packages
.localjev/serve.log    the running server's log
.localjev/serve.pid    its pid
~/.jev-local-key       Bearer key, 0600, outside the repo. Never in argv, never in the doc
~/.cache/huggingface/  mlx-community/Qwen3.6-35B-A3B-4bit, 4 shards, 20.4 GB
```

How it got there, for a rebuild:

```sh
cd ~/dev/rivals-agent/.localjev
git clone https://github.com/Micha0827/snapjudge && (cd snapjudge && git checkout 2df5ce2753b5)
uv venv --python 3.12 .venv
cd snapjudge && VIRTUAL_ENV=../.venv uv pip install -e .
../.venv/bin/python -c "from huggingface_hub import snapshot_download as s; s('mlx-community/Qwen3.6-35B-A3B-4bit')"
openssl rand -hex 16 > ~/.jev-local-key && chmod 600 ~/.jev-local-key
```

### Start and stop

`localjev/serve.sh` is the whole interface; it reads the LAN address from the default
route rather than hard-coding it, keeps the key out of `argv`, nices the server to 5 and
waits for `/health` before returning.

```sh
localjev/serve.sh start     # prints the JEV_URL to export once the model is loaded
localjev/serve.sh status    # pid, resident size, /health
localjev/serve.sh stop
```

What it runs, if you would rather run it by hand:

```sh
SO_API_KEY="$(cat ~/.jev-local-key)" nice -n 5 \
  ~/dev/rivals-agent/.localjev/.venv/bin/snapjudge-serve \
  --model mlx-community/Qwen3.6-35B-A3B-4bit \
  --host 192.168.4.126 --port 8724 --name jev-local
```

**Bound to the LAN address only**, never `0.0.0.0` and no tunnel. One consequence that
costs a confusing minute otherwise: `127.0.0.1:8724` does **not** answer, because a bind to
one address serves only that address. Use `192.168.4.126` from the Mac too. That address is
this Mac's `en0` and it moves with the DHCP lease; `serve.sh` re-reads it every start, so
re-run `serve.sh status` rather than trusting a pasted URL. macOS asks once to allow
incoming connections.

The key is not in this doc. Read it where a command needs it:
`JEV_KEY="$(cat ~/.jev-local-key)"`.

### Smoke test

```sh
curl -s http://192.168.4.126:8724/health
JEV_KEY="$(cat ~/.jev-local-key)" JEV_URL=http://192.168.4.126:8724/v1/systemone JEV_MODEL=local \
  uv run python -m agent.jev -n 5 --timeout 2
# PC (PowerShell): curl.exe http://192.168.4.126:8724/health
```

`"debug": true` in a hand-built body adds timings, the top next tokens and `coverage`, the
probability mass that landed on allowed labels. A low coverage means the model wanted a
token that is not one of our labels.

### The brain lane's side (landed, not by this lane)

`agent/jev.py` already points anywhere: `Endpoint.from_env()` reads `JEV_URL`, `JEV_MODEL`
and `JEV_KEY`, `_Session.post` picks `HTTPConnection` or `HTTPSConnection` from the scheme
and uses its host, port and path, and `Authorization` is sent only when a key is set - the
OpenRouter key is demanded only for the default URL. So a local server needs **no code of
ours** to be measured: the stock `uv run python -m agent.jev` benchmark does it, and its
JSON now carries an `endpoint` block naming the URL, model and whether a Bearer was sent.
R5 is satisfied; R1-R4, R6 and R7 were already.

Still open, and worth a measurement before it is treated as a rule: `questions()` builds
the `target` criteria from per-tick facts (`"enemy, mid range, tag False"`), so that
question's head changes every call and cannot be a cached prefix. The same facts are
already in `state.targets`. Making the text static (`"target 0"`) should let the head
cache; the size of the saving is **unverified** until someone compares `debug.timing_ms`
and `debug.prefix_cache_hit` both ways. It is the brain lane's call and its file.

### What this lane added

Five files under `localjev/`, standard library only, none of them on the agent's hot path:

| File | Does |
|---|---|
| `serve.sh` | start / stop / status for the server, LAN-bound, key out of argv, long keep-alive |
| `paired.py` | the one thing `agent.jev` cannot do: the same `bench_states` sent to the local server **and** to real Jev, intents compared |
| `netprobe.py` | the network floor alone: `/health` on one kept-alive connection. Run it from the PC before blaming the server |
| `gpustat.py` | GPU utilization and GPU-visible memory from `ioreg`, since `powermetrics` needs root |
| `selftest.py` | offline check of `paired.py` against two stub System One servers; no model, no network off the loopback. `uv run python -m localjev.selftest` |

`paired.py`, `netprobe.py` and `selftest.py` are copied to `C:\rivals-agent\localjev\` on the
PC alongside the `agent/` copies, and the PC's `agent/jev.py` was refreshed to the Mac's
`5bafe854d807fcd8` so both machines build identical bodies. Compare with `Get-FileHash`
before trusting the PC copies; they are snapshots, not a checkout.

An earlier draft of this lane carried its own `LocalTransport`. It was deleted the moment
the brain lane's `Endpoint` landed: same job, one writer.

## Measured (2026-09-20, this Mac, M5 Max 128 GB)

`mlx-community/Qwen3.6-35B-A3B-4bit` behind snapjudge on `192.168.4.126:8724`, measured
with the stock `uv run python -m agent.jev` on the same synthetic States real Jev was
measured on, then the same States sent to both endpoints for agreement. The detector
training that owned the GPU finished at 17:25; every number below is from an otherwise
idle machine. 964 requests were served with no server-side error.

**The short version: it is about 1.7x faster than real Jev from the Mac and roughly a
wash from the PC, and it agrees with Jev on 61% of our States.** Speed is not the
problem; the LAN hop and the disagreement are.

### Two things that had to be fixed before anything could be measured

Both are recorded here because a fresh server will have both again.

1. **A one-option `choice` is rejected.** `agent/jev.py` asks "which target?" even when one
   hostile is visible, so `criteria` is `{"0": ...}`. snapjudge's pydantic validator demands
   at least two options and answers **HTTP 422**; real Jev answers it. On the first run this
   failed **50 of 60 calls** - only the intent-only States got through, and the 89 ms p50 that
   produced was measuring the easy tenth of the workload. Patched in the vendored clone
   (`.localjev/snapjudge/snapjudge/server.py`, `len(c) >= 2` -> `>= 1`, comment names this
   repo). The engine already handles it correctly: one option means no branching node, so it
   returns probability 1.0 and runs no rows. **Keep the patch on any reinstall**, or send it
   upstream. The better fix is client-side and belongs to the brain lane: see below.
2. **uvicorn closes an idle keep-alive connection after 5 s.** The next request on it raises
   `RemoteDisconnected`, which `agent/jev.py` counts as an `http` fallback and pays a tick
   for. Measured directly: gaps of 0.5, 2, 4 and 5.5 s are fine, 7 s fails. This is what the
   4-5 `http` fallbacks per async run were. The gate decides about 78% of ticks and holds are
   long, so quiet stretches over 5 s are normal in the live loop. `serve.sh` therefore runs
   `uvicorn ... --timeout-keep-alive 3600` directly rather than `snapjudge-serve`, whose CLI
   cannot pass the flag. After the change: 7 s and 15 s gaps both fine, and zero `http`
   fallbacks in every run since.

### Cold start

The model loads in 6.5 s, but the **first real request takes 6.3 s** while Metal compiles
its kernels; the second is 420 ms and the third 78 ms. `SOCKET_CAP_S` in `agent/jev.py` is
5 s, so the first call after a restart always fails and takes the next few with it. Warm
the server before pointing anything at it:

```sh
JEV_KEY="$(cat ~/.jev-local-key)" JEV_URL=http://192.168.4.126:8724/v1/systemone JEV_MODEL=local \
  uv run python -m agent.jev -n 5 --timeout 30 >/dev/null
```

### Round trip

Answered calls only. Real Jev's column is `docs/lanes/l5-brain.md`, same States, same day.

| From | Run | p50 | p95 | max | Fallbacks | Real Jev, same shape |
|---|---|---|---|---|---|---|
| Mac | blocking, 2 s, back to back, n=60 | 127-208 ms | 168-431 ms | 556 ms | none | 237-250 / 322-393 ms |
| Mac | blocking, 300 ms, 5 Hz, n=200 | 109-127 ms | 163-213 ms | 261 ms | **none** | 8% at 400 ms |
| Mac | blocking, 200 ms, 5 Hz, n=100 | 122 ms | 188 ms | 196 ms | 4% timeout | 77% at 200 ms |
| Mac | async, 10 Hz, 546 ticks | 85 ms | 480 ms | 699 ms | none | 227 / 349 / 437 ms |
| **PC** | blocking, 2 s, back to back, n=60 | **223 ms** | **283 ms** | 327 ms | none | **228 / 355 / 413 ms** |
| **PC** | blocking, 300 ms, 5 Hz, n=200 | 201 ms | 270 ms | 302 ms | 4% timeout | not measured |
| **PC** | async, 10 Hz, 546 ticks | 175 ms | 531 ms | 577 ms | none | 226 / 403 / 758 ms |

Two things the table hides:

- **Back to back is slower than paced.** At 5 Hz the Mac sits at p50 109-127 ms; back to
  back it drifts to 208 ms, because nothing lets the GPU catch up. The live loop is paced,
  so the paced row is the honest one. Run-to-run spread on the back-to-back p50 is wide
  (127-208 ms across three runs); the paced numbers repeat within about 20 ms.
- **The p95 on the async runs is not the server.** 480 ms (Mac) and 531 ms (PC) come from
  the handful of 3-question requests; the p50 of 85 ms (Mac) is what most ticks see.

### The LAN hop is half the PC's round trip

`GET /health` on one kept-alive connection, no model work at all
(`uv run python -m localjev.netprobe 192.168.4.126`):

| From | p50 | p95 | min | max |
|---|---|---|---|---|
| Mac (same machine) | **0.4 ms** | 0.6 ms | 0.2 ms | 0.7 ms |
| **PC, Wi-Fi** | **62.9 ms** | 90.0 ms | 48.0 ms | 128.3 ms |

Both machines are on 6 GHz with strong links (Mac 802.11be, -57 dBm, 1080 Mbps; PC
Wi-Fi 6E AX211, 83%, 817/1297 Mbps), and the Mac pings its own gateway at avg 53 ms with
10% loss, so **the access point is the bottleneck, not either radio**. That is a
pre-existing fact about this network, not something this lane introduced, and it caps
what any Mac-hosted server can do for the PC: ~63 ms of the PC's 201 ms p50 is air.

Wiring the PC to the router, or moving the server onto the PC, is worth more than any
remaining model tuning. Untried.

### Agreement with real Jev

The same `agent.jev.bench_states` sent to both endpoints, intents compared
(`uv run python -m localjev.paired`). Real Jev is `https://api.typesafe.ai/v1/systemone`
from `.env`.

| n | Agreement local vs Jev | Disagreements (Jev -> local) | With the scripted brain: local / Jev |
|---|---|---|---|
| 150 | **60.7%** | `burst->pull` 34, `engage->swing_to` 18, `engage->search` 7 | 52% / 67.3% |
| 100 | **62.0%** | `burst->pull` 22, `engage->swing_to` 12, `engage->search` 4 | 52% / 66.0% |

Stable across the two samples, and the disagreements are **systematic, not noise**: three
substitutions account for all of them. Where Jev commits to the full combo, the local model
takes the single pull; where Jev closes in, it swings away. Median confidence is 0.857
local against 0.900 for Jev, so the local model is slightly less peaked and not overconfident
about being different.

Neither is ground truth. The scripted brain is a heuristic, and the l5 caveat holds: nothing
here measures whether a `burst` is actually better than a `pull` in the range. What the table
does say is that **the local model is not a drop-in stand-in for Jev's judgement** - swapping
the endpoint changes about two decisions in five - while it *is* a drop-in for Jev's wire.

About 260 real-Jev calls were spent on all paired runs, roughly $0.006 at l5's measured
$0.000023 per call. `usage.cost` comes back absent from `api.typesafe.ai` (it was present
on the OpenRouter route), so `cost_usd_answered` reads 0.0 and spend has to be estimated.

### What it does to the non-blocking loop

`--async -n 546 --hz 10`, the same run l5 made against real Jev.

| | Local, Mac | Local, PC | Real Jev, PC (l5) |
|---|---|---|---|
| Decided by gate / scripted / **jev** / standing | 429 / 67 / **45** / 5 | 427 / 65 / **27** / 27 | 431 / 89 / **26** / n/a |
| **Jev's share of all ticks** | **9.2%** | 9.9% | 4.8% |
| Jev's share of ticks the gate let through | **42.7%** | 45.4% | 22.6% |
| Requests sent / answered | 51 / 50 | 32 / 31 | 31 / 30 |
| Age of the State an adopted answer was about, p50 | **100 ms** | 200 ms | 300 ms |
| Ticks whose intent differs from the scripted one | 0.7% | 1.1% | ~1% |
| `decide_jev` per-tick wall, max | 1 ms | 4 ms | 3 ms |

The real gain is here rather than in the p50: an answer lands in about one tick instead of
three, so the model gets to decide **roughly twice as often** (9-10% of ticks, 43-45% of the
ticks the gate opens, against 4.8% and 22.6%). The `standing` mechanism the brain lane added
since l5's run is in these numbers and is not in theirs, so the "decided by" rows are not a
clean like-for-like.

It never stalls the loop: the worst tick cost 4 ms.

### Memory and GPU load, because this is James's working machine

| State | Server RSS | GPU-visible in use | MLX allocated | GPU utilization |
|---|---|---|---|---|
| Loaded, idle | 19.6 GB | 1.0-1.4 GB | 32 GB | 12-15% (desktop baseline) |
| Answering at 10 Hz | 19.6 GB | swings 1.1-19.9 GB per request | 32 GB | median **69%**, peak 96% |
| Answering back to back | 19.6 GB | 20.3 GB | 31.8 GB | **97%** |

Read with `uv run python -m localjev.gpustat` (`ioreg`; `powermetrics` needs root).
System memory stayed 62% free throughout. The honest warning: **a live 10 Hz session keeps
the GPU around two-thirds busy and holds ~20 GB resident**. That is fine on 128 GB while
nothing else wants the GPU, and it is exactly what conflicts with a detector training run,
so the two cannot share the machine. `serve.sh` nices the server to 5, which helps the
desktop but not another GPU job.

### The question head does cache, and static target text makes it cache fully

The research pass left open whether the per-tick `target` criteria text
(`"enemy, mid range, tag False"`) defeats snapjudge's cached question prefix. Measured with
`"debug": true`, 40 bench States, **interleaved** so drift hits both variants equally:

| `target`/`anchor` criteria text | wall p50 | wall p95 | prefix cache hit |
|---|---|---|---|
| As `agent/jev.py` builds it | 176.6 ms | 312.1 ms | 34/40 |
| Static (`"target 0"`) | 171.0 ms | **217.9 ms** | **40/40** |

So: the cost is real but it is in the **tail**, not the median - the per-tick text has few
distinct values (a handful of range/tag combinations), so the 16-slot prefix LRU catches
most of them anyway, and the misses are what the p95 is made of. Static text buys about 30%
off p95 and nothing off p50.

A first, sequential A/B said the opposite (static *slower*). That was an artifact of running
the two variants in separate blocks, where the second inherited the first's warm caches.
**Interleave any A/B against this server**, or measure the cache, not the model.

### Verdict against the acceptance gate

The gate was: blocking fallback rate under 2% and round-trip p95 at or under 150 ms, and an
async run with `jev_share_of_choices` near 1 and few `stale` drops.

| Criterion | Mac | PC | Met |
|---|---|---|---|
| Blocking fallback rate under 2% at a 300 ms budget | 0% | 4% | Mac yes, PC no |
| Round-trip p95 at or under 150 ms | 163-213 ms | 270 ms | **no**, but well under Jev's 322-393 |
| `jev_share_of_choices` near 1 | 0.43 | 0.45 | **no** - but 2x real Jev's 0.23 |
| Few `stale` drops | 1 | 1 | yes |

**It misses the letter of the gate and beats the incumbent on every line of it.** The gate's
150 ms p95 was written before anyone knew the LAN hop alone costs the PC 63-90 ms; no
Mac-hosted server can meet it from the PC, whatever model it runs. `jev_share_of_choices`
near 1 was never reachable either: at 10 Hz an answer that takes 85 ms still lands a tick
late, and the gate closes over most of the story.

Recommendation to the lead, whose call this is: **keep it as the endpoint for latency work
and keep real Jev as the reference for judgement**, and treat the 61% agreement - not the
latency - as the open question. The cheap next steps, in order:

1. Wire the PC to the router, or run the server on the PC's 4080 SUPER instead. 63-90 ms of
   air is the largest single cost in the PC's path and no model change touches it.
2. Decide which of `burst` vs `pull` and `engage` vs `swing_to` is actually right in the
   range, by replaying both against real footage. Until then "agreement with Jev" is a
   similarity score, not an accuracy score.
3. Only then try `mlx-community/Qwen3.5-4B-MLX-4bit` (ladder step 1): it would roughly halve
   the Mac-side latency, which is already the small half of the PC's budget, at an unknown
   cost in agreement. Untried.

## Unverified

Four of the original seven are now measured: M5 Max logit-read latency, the question-head
cache, the PC-Mac LAN round trip, and agreement with Jev on our States. What is left:

- **Whether the local model's choices are actually worse.** 61% agreement with Jev is a
  similarity score. `burst` vs `pull` and `engage` vs `swing_to` need judging against real
  footage before either endpoint is called right.
- **Quality of any Qwen model on Spider-Man intent choice**; no benchmark covers it, and
  ours is 150 synthetic States, not perception output.
- **`mlx-community/Qwen3.5-4B-MLX-4bit`** (ladder step 1): latency and agreement, untried.
- **Whether serving on the PC's 4080 SUPER beats the Wi-Fi hop.** Untried, and the game owns
  that GPU while it runs, so it may only be an option between sessions.
- Whether the one-option-`choice` patch is wanted upstream, and whether snapjudge's author
  would take it.
- Whether GitHub30/OpenJev runs on MPS; whether SemIf ships a Jev-wire server.
- razorback16's weight licence (README: Apache-2.0; JoshuaSP: Google's terms).
- jevmlx returning probabilities for options outside the top three.

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
