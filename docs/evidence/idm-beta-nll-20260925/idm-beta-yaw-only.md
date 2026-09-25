# scoreboard-fix: β-NLL on yaw only (Y1-Y3), against its pre-registered judge (VUH-1353)

2026-09-25.
- **Pre-registration:** the part-A addendum "**Addendum: β-NLL on yaw only**", LF sha256
  `d6f63ff6b87df5c0e5516fd4695e6569bfa0f606c7558730f0d21250465aa1d6`. The lead confirmed the one-sided pitch reading
  and committed it.
- **Runs:** `--beta-nll 0.5 --beta-nll-axes yaw`, seed 0, 3 epochs, MPS; code `23a142f` (branch
  `idm/beta-yaw-only-20260925`, clean). One niced queue, exit 0 after 66 min.
- **Not done:** no commits to main, no Linear, no game input.

## Result: FAIL on all three components

| Component (all required) | Result | Met? |
|---|---|---|
| (1) Yaw learned (≥ 0.85 held out and in-sample) on both folds | Y1, fold 051828: **0.911 / 0.926**, learned. Y2, fold 205528: **0.686 / 0.702**, **not learned** | **no** |
| (2) Gate 1 yaw on 171533 (Y3): direction ≥ 0.99, abstention ≤ 1 % | direction **0.978**, abstention 0.7 % | **no** |
| (3) Gate 1 pitch (Y3): moving median ≤ 0.528°, extrapolated 1σ coverage ≥ 0.70 | moving median **0.654°**, extrapolated 1σ **0.654** | **no** |

**Pre-registered reading:** fail, so **the lead decides for β-NLL on both axes, with the pitch cost on record.**

## Gate 1 on 171533 next to the earlier arms (same `fe5c9ca`-lineage harness)

| Figure | Plain (re-scored `loso-171533`) | β-NLL both axes (A4) | **β-NLL yaw only (Y3)** |
|---|---|---|---|
| Yaw moving median | 0.352° | 0.263° | 0.365° |
| Yaw direction | 0.964 | 0.995 | 0.978 |
| Yaw 1 s sum median | 3.35° | 2.84° | 4.36° |
| Yaw > 4× median | 0.867° | 0.502° | 0.633° |
| Yaw abstention | 3.7 % | 0.3 % | 0.7 % |
| Pitch moving median | 0.508° | 0.568° | **0.654°** |
| Pitch direction | 0.859 | 0.887 | 0.812 |
| Pitch 1 s sum median | 2.35° | 2.98° | 3.77° |
| Pitch extrapolated within 1σ / 2σ | 0.734 / 0.930 | 0.604 / 0.882 | 0.654 / 0.905 |
| Pitch calibrated within 1σ / 2σ | 0.827 / 0.941 | 0.866 / 0.982 | 0.792 / 0.920 |
| Yaw calibrated / extrapolated within 1σ | 0.674 / 0.730 | 0.802 / 0.734 | 0.626 / 0.702 |

**Also:**
- **Yaw on the folds** (raw μ, held out / in-sample): Y1 0.911 / 0.926, Y2 0.686 / 0.702. Both-axes β-NLL learned
  6 of 6 seeds at 0.94–0.98.
- **Pitch agreement held out:** Y1 0.838, Y2 **0.592**.
- **Edges at 0.5 on 171533:** jump F1 0.231 (AUC 0.941); amazing_combo and web_cluster F1 0.

## My reading

- **Yaw-only β-NLL is worse than both-axes β-NLL on yaw, and worse than plain on pitch.** It is not a middle
  ground, so the targeted alternative that A2 named does not work as designed.
  - Yaw was learned on one fold, and only partly on the other (0.69).
  - Gate 1 yaw falls short of both-axes β-NLL on every figure.
  - Pitch is worse than **both** earlier arms on moving error (0.654° against 0.508° and 0.568°) and on direction.
- **One untested explanation:** weighting only the yaw term changes the relative scale of the two camera losses in
  the shared trunk. With the both-axes weight the two stay on one scale; with the yaw-only weight they do not. I have
  not measured this. It would take a per-axis loss-scale log.
- **The caveat that matters:** every run here is seed 0, and A2 showed pitch is seed-fragile on its own (held-out
  pitch 0.62–0.85 across seeds, under either loss). So Y3's pitch figures carry that spread. Y2's 0.592 held-out
  pitch sits inside it.
  - That doesn't change the registered reading: the judge was fixed before the runs.
  - It does mean pitch comparisons between single-seed arms (0.508 against 0.568 against 0.654) are weaker evidence
    than yaw's 6-of-6 against 2-of-6.
- **For your both-axes decision:**
  - **For β-NLL on both axes:** yaw learned 6 of 6 against 2 of 6; A3's calibration improves in both bands with the
    bounds holding 6 of 6; and A4's Gate 1 yaw is better on every figure.
  - **Against it:** the pitch cost, which is a moving median of +0.06° and extrapolated 1σ coverage 0.604 at A4.
  - **If you take it, one pitch-side follow-up would be a small fix:** recalibrate the stated pitch std in the
    extrapolated band (the abstention bounds are separate), measured across three seeds. That is not proposed as a
    run here.

## Hashes (all 10 checked across the wire)

**Runs** (in `C:\Users\volpe\repos\rivals-agent\data\idm\runs\`, gitignored, with `yo.log` and `yo.exit`):

| Run | Fold | Train examples | Fit | Checkpoint | report.json |
|---|---|---|---|---|---|
| Y1 `yo-051828` | 051828 | 144,932 | 1,209 s | `cbd774f4e210565a8a2bf2f0718a11d605eac891ff6871049ac4b28946deeed3` | `f6acc79aadeb9f115405b534e60969784db887e8c9844f0e3f5e4bb6ae428d3c` |
| Y2 `yo-205528` | 205528 | 130,180 | 1,071 s | `c5dd530134a2f927f4186e1adee9c68dc0de0989054b5f9443d9b021133e665f` | `ab85adc7301531fd308be51bd3336761ded73e5203b1fb0262eadbc4ca44cadd` |
| Y3 `yo-171533` (Gate 1) | 171533 | 160,772 | 1,339 s | `ce0aa86b2cea99e7216a46ab6dafb7060ce52e6fa83bf5914170c0554d603da5` | `60cd9ed113dbd7bce6d7a150d6027b323057b68c179912f323ed1b4eb8c15f9b` |

Every report records `camera_loss {"kind": "beta_nll", "beta": 0.5, "axes": "yaw"}` and code `23a142f`, clean.

**Per-row predictions** (`scratchpad\idm-diag\`):

| File | sha256 |
|---|---|
| `yo-051828-on-051828-predictions.jsonl` | `4a644cc086a35ef8d6b04d58fc3d8fec55b4ce378971d495c0dc933966a97913` |
| `yo-051828-on-171533-predictions.jsonl` | `57d0761bb04fe8d641d8be8eb646b998edeb44488081e0091e29dffe1fd08f6f` |
| `yo-205528-on-205528-predictions.jsonl` | `49dc655803a613cdffc08865d322c74f2cd37062519585e04b23bee48c5dcbed` |
| `yo-205528-on-171533-predictions.jsonl` | `6b7fe56c885b300f91c6791f101bfa9d3401de8d0d24675e58baab63f541b042` |

**Scripts:**

| File | sha256 |
|---|---|
| `judge_yo.py` | `c683e5df3966f08bf89163c2ce05abc16e8f4564a702cb81c48805262329fc24` |
| `judge_yo-out.md` | `71abc189683acec2423b2a0099ed57324154b81d1d6e611d41048bb8d8450b48` |
| Mac `yo.zsh` | `54d56895a7bf87a0fe2009994de24135df5282653abcd13ee4e24a502b8d5e74` |
| Mac `chain3.zsh` | `d3a4d9111b7d1c8253ceff253d6580eb23c260a0b60824e57e75f9696183f350` |

**The code:** branch `idm/beta-yaw-only-20260925` at `23a142fb99861fab1a984bd60833b70b93187eb2`, pushed and not on
main.
- It adds `--beta-nll-axes {both, yaw}`, default `both`, which is `d10f583` bit for bit. A test covers the axis
  split and the default.
- 79 tests pass and ruff is clean.
- With this result there is no case to land it, unless you want the option kept for a later per-axis experiment.

**The Mac is idle.** Everything tonight is handed back: `idm-beta-nll-2.md`, `idm-beta-nll-2-a4.md`,
`idm-edge-input.md`, `idm-edge-input-2.md` and this file.
