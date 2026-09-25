Frozen parameters (A): edges [0.06059320594627363, 0.10755754546016058, 0.16996028513718056, 0.351656956463779]; k [1, 1, 1, 1.6005068343947064, 1.242973089376128]; pitch_fix3-params.json 6f8dba7b04336c3fd4ce5dcd2acaa8b5a6e4578678643dedb7d942b1549bcff3

Evaluable distinct pitch rows per session and true band (support floor 500):
- 232304: calibrated 17,626; extrapolated 13,928
- 021320: calibrated 72,374; extrapolated 51,878
- 025230: calibrated 8,043; extrapolated 5,145

## Judge

| True band | Pooled before A: 1s / 2s / abstention / in-bound | Pooled after A: 1s / 2s / abstention / in-bound | (1) |
|---|---|---|---|
| calibrated | 0.837 / 0.978 / 0.002 / 0.999 | **0.905 / 0.986 / 0.015 / 0.999** | meets |
| extrapolated | 0.634 / 0.904 / 0.007 / 0.957 | **0.750 / 0.960 / 0.026 / 0.963** | meets |

(2) Bounds per checkpoint, pooled over the three sessions (answered within the predicted regime's bound, after A):

| Checkpoint | Calibrated | Extrapolated | (2) |
|---|---|---|---|
| T (yaw-t0) | 0.999 | 0.967 | met |
| T1 (yaw-t1) | 0.999 | 0.965 | met |
| T2 (yaw-t2) | 1.000 | 0.956 | met |
| s0 (a1-beta-s0) | 1.000 | 0.951 | met |
| s1 (a1-beta-s1) | 0.999 | 0.971 | met |
| s2 (a1-beta-s2) | 0.999 | 0.965 | met |
| a4 (a4-beta) | 1.000 | 0.965 | met |

(3) Yaw identical row for row on all 21 files: met

(1) coverage met; (2) bounds met; (3) yaw met -> **PASS**
reading: A is confirmed on fresh held-out sessions; the Gate 2 precondition closes, and the deployment change (A in policy.idm.train._camera) is written for review

## Reported beside (not judged)

Per session, pooled over the seven checkpoints (before -> after; 1s / 2s / abstention / in-bound):

| Session | True band | Before A | After A |
|---|---|---|---|
| 232304 | calibrated | 0.831 / 0.975 / 0.004 / 0.998 | 0.903 / 0.984 / 0.018 / 0.999 |
| 232304 | extrapolated | 0.578 / 0.869 / 0.009 / 0.935 | 0.697 / 0.941 / 0.031 / 0.943 |
| 021320 | calibrated | 0.839 / 0.979 / 0.002 / 0.999 | 0.905 / 0.986 / 0.014 / 0.999 |
| 021320 | extrapolated | 0.648 / 0.912 / 0.007 / 0.963 | 0.763 / 0.964 / 0.025 / 0.968 |
| 025230 | calibrated | 0.837 / 0.982 / 0.002 / 0.999 | 0.901 / 0.988 / 0.013 / 0.999 |
| 025230 | extrapolated | 0.646 / 0.907 / 0.006 / 0.964 | 0.764 / 0.962 / 0.028 / 0.971 |

Per checkpoint, pooled over the three sessions:

| Checkpoint | True band | Before A | After A |
|---|---|---|---|
| T | calibrated | 0.830 / 0.982 / 0.000 / 0.998 | 0.902 / 0.989 / 0.006 / 0.999 |
| T | extrapolated | 0.609 / 0.890 / 0.002 / 0.963 | 0.737 / 0.955 / 0.012 / 0.967 |
| T1 | calibrated | 0.849 / 0.986 / 0.002 / 0.999 | 0.921 / 0.994 / 0.009 / 0.999 |
| T1 | extrapolated | 0.665 / 0.922 / 0.004 / 0.962 | 0.768 / 0.967 / 0.016 / 0.965 |
| T2 | calibrated | 0.815 / 0.972 / 0.003 / 1.000 | 0.889 / 0.981 / 0.009 / 1.000 |
| T2 | extrapolated | 0.637 / 0.902 / 0.008 / 0.951 | 0.752 / 0.961 / 0.022 / 0.956 |
| s0 | calibrated | 0.928 / 0.996 / 0.009 / 1.000 | 0.977 / 0.999 / 0.052 / 1.000 |
| s0 | extrapolated | 0.642 / 0.930 / 0.029 / 0.934 | 0.758 / 0.974 / 0.093 / 0.951 |
| s1 | calibrated | 0.782 / 0.960 / 0.001 / 0.999 | 0.853 / 0.970 / 0.010 / 0.999 |
| s1 | extrapolated | 0.677 / 0.919 / 0.003 / 0.967 | 0.785 / 0.965 / 0.018 / 0.971 |
| s2 | calibrated | 0.848 / 0.984 / 0.001 / 0.999 | 0.918 / 0.991 / 0.010 / 0.999 |
| s2 | extrapolated | 0.637 / 0.902 / 0.003 / 0.962 | 0.756 / 0.963 / 0.015 / 0.965 |
| a4 | calibrated | 0.810 / 0.969 / 0.000 / 0.999 | 0.874 / 0.979 / 0.006 / 1.000 |
| a4 | extrapolated | 0.572 / 0.859 / 0.000 / 0.962 | 0.696 / 0.935 / 0.008 / 0.965 |

Per session x checkpoint:

| Session | Checkpoint | True band | Before A | After A |
|---|---|---|---|---|
| 232304 | T | calibrated | 0.822 / 0.976 / 0.001 / 0.997 | 0.898 / 0.986 / 0.007 / 0.998 |
| 232304 | T | extrapolated | 0.548 / 0.846 / 0.004 / 0.941 | 0.682 / 0.933 / 0.015 / 0.945 |
| 232304 | T1 | calibrated | 0.843 / 0.981 / 0.002 / 0.997 | 0.917 / 0.993 / 0.012 / 0.997 |
| 232304 | T1 | extrapolated | 0.607 / 0.893 / 0.005 / 0.941 | 0.713 / 0.952 / 0.020 / 0.946 |
| 232304 | T2 | calibrated | 0.801 / 0.968 / 0.004 / 1.000 | 0.885 / 0.978 / 0.012 / 1.000 |
| 232304 | T2 | extrapolated | 0.581 / 0.870 / 0.010 / 0.927 | 0.700 / 0.944 / 0.026 / 0.934 |
| 232304 | s0 | calibrated | 0.920 / 0.994 / 0.014 / 1.000 | 0.972 / 0.998 / 0.060 / 1.000 |
| 232304 | s0 | extrapolated | 0.582 / 0.906 / 0.035 / 0.909 | 0.702 / 0.962 / 0.106 / 0.931 |
| 232304 | s1 | calibrated | 0.794 / 0.964 / 0.001 / 0.998 | 0.866 / 0.976 / 0.013 / 0.999 |
| 232304 | s1 | extrapolated | 0.625 / 0.888 / 0.005 / 0.950 | 0.738 / 0.946 / 0.019 / 0.955 |
| 232304 | s2 | calibrated | 0.833 / 0.977 / 0.002 / 0.998 | 0.911 / 0.986 / 0.014 / 0.999 |
| 232304 | s2 | extrapolated | 0.579 / 0.866 / 0.005 / 0.940 | 0.701 / 0.945 / 0.019 / 0.944 |
| 232304 | a4 | calibrated | 0.802 / 0.964 / 0.000 / 0.999 | 0.872 / 0.975 / 0.008 / 0.999 |
| 232304 | a4 | extrapolated | 0.524 / 0.818 / 0.000 / 0.940 | 0.644 / 0.909 / 0.011 / 0.944 |
| 021320 | T | calibrated | 0.830 / 0.984 / 0.000 / 0.999 | 0.903 / 0.990 / 0.005 / 0.999 |
| 021320 | T | extrapolated | 0.622 / 0.901 / 0.002 / 0.969 | 0.749 / 0.960 / 0.011 / 0.972 |
| 021320 | T1 | calibrated | 0.848 / 0.987 / 0.002 / 0.999 | 0.921 / 0.994 / 0.009 / 0.999 |
| 021320 | T1 | extrapolated | 0.679 / 0.930 / 0.004 / 0.967 | 0.782 / 0.971 / 0.014 / 0.970 |
| 021320 | T2 | calibrated | 0.819 / 0.973 / 0.002 / 1.000 | 0.892 / 0.982 / 0.009 / 1.000 |
| 021320 | T2 | extrapolated | 0.652 / 0.910 / 0.008 / 0.957 | 0.764 / 0.965 / 0.021 / 0.962 |
| 021320 | s0 | calibrated | 0.930 / 0.996 / 0.008 / 1.000 | 0.977 / 0.999 / 0.051 / 1.000 |
| 021320 | s0 | extrapolated | 0.657 / 0.937 / 0.027 / 0.940 | 0.771 / 0.977 / 0.089 / 0.955 |
| 021320 | s1 | calibrated | 0.780 / 0.959 / 0.001 / 0.999 | 0.850 / 0.968 / 0.010 / 0.999 |
| 021320 | s1 | extrapolated | 0.690 / 0.927 / 0.003 / 0.971 | 0.796 / 0.970 / 0.018 / 0.975 |
| 021320 | s2 | calibrated | 0.852 / 0.985 / 0.001 / 0.999 | 0.921 / 0.992 / 0.010 / 0.999 |
| 021320 | s2 | extrapolated | 0.651 / 0.912 / 0.003 / 0.967 | 0.771 / 0.968 / 0.013 / 0.970 |
| 021320 | a4 | calibrated | 0.812 / 0.969 / 0.000 / 0.999 | 0.876 / 0.980 / 0.005 / 1.000 |
| 021320 | a4 | extrapolated | 0.583 / 0.869 / 0.000 / 0.967 | 0.708 / 0.941 / 0.007 / 0.969 |
| 025230 | T | calibrated | 0.840 / 0.984 / 0.000 / 0.998 | 0.905 / 0.991 / 0.004 / 0.999 |
| 025230 | T | extrapolated | 0.636 / 0.897 / 0.001 / 0.969 | 0.765 / 0.960 / 0.011 / 0.972 |
| 025230 | T1 | calibrated | 0.865 / 0.991 / 0.002 / 0.999 | 0.929 / 0.995 / 0.007 / 0.999 |
| 025230 | T1 | extrapolated | 0.676 / 0.920 / 0.004 / 0.970 | 0.781 / 0.965 / 0.015 / 0.973 |
| 025230 | T2 | calibrated | 0.801 / 0.976 / 0.003 / 1.000 | 0.877 / 0.982 / 0.008 / 1.000 |
| 025230 | T2 | extrapolated | 0.644 / 0.911 / 0.005 / 0.953 | 0.769 / 0.966 / 0.023 / 0.962 |
| 025230 | s0 | calibrated | 0.927 / 0.997 / 0.007 / 1.000 | 0.979 / 0.998 / 0.047 / 1.000 |
| 025230 | s0 | extrapolated | 0.650 / 0.931 / 0.028 / 0.942 | 0.772 / 0.970 / 0.099 / 0.962 |
| 025230 | s1 | calibrated | 0.778 / 0.969 / 0.001 / 0.998 | 0.846 / 0.977 / 0.008 / 0.999 |
| 025230 | s1 | extrapolated | 0.687 / 0.921 / 0.001 / 0.976 | 0.794 / 0.971 / 0.018 / 0.979 |
| 025230 | s2 | calibrated | 0.845 / 0.985 / 0.001 / 0.999 | 0.911 / 0.990 / 0.009 / 0.999 |
| 025230 | s2 | extrapolated | 0.644 / 0.898 / 0.003 / 0.973 | 0.760 / 0.962 / 0.016 / 0.976 |
| 025230 | a4 | calibrated | 0.805 / 0.973 / 0.000 / 1.000 | 0.864 / 0.982 / 0.005 / 1.000 |
| 025230 | a4 | extrapolated | 0.586 / 0.874 / 0.001 / 0.968 | 0.710 / 0.940 / 0.014 / 0.973 |

Yaw raw-mu direction agreement on moving rows (|true| >= 0.5 deg), a transfer check:

| Checkpoint | 232304 | 021320 | 025230 |
|---|---|---|---|
| T | 0.975 (n 13,242) | 0.973 (n 51,922) | 0.979 (n 5,085) |
| T1 | 0.948 (n 13,242) | 0.957 (n 51,922) | 0.960 (n 5,085) |
| T2 | 0.970 (n 13,242) | 0.973 (n 51,922) | 0.978 (n 5,085) |
| s0 | 0.936 (n 13,242) | 0.946 (n 51,922) | 0.949 (n 5,085) |
| s1 | 0.970 (n 13,242) | 0.971 (n 51,922) | 0.973 (n 5,085) |
| s2 | 0.970 (n 13,242) | 0.971 (n 51,922) | 0.977 (n 5,085) |
| a4 | 0.978 (n 13,242) | 0.979 (n 51,922) | 0.980 (n 5,085) |

Input sha256:
- yaw-t0-on-232304-predictions.jsonl d96ea2dff9643e77f4c2b61eb37d0949e78cd715411785b34bdf5ec64631dd06
- yaw-t1-on-232304-predictions.jsonl dd6aab0b4dfd2cb4addb4200360cd66be947bd5b652d562ad0c47957842316f3
- yaw-t2-on-232304-predictions.jsonl a83ab254619424f538398071dce91b769073fd7a30558ebea19356d642601eb9
- a1-beta-s0-on-232304-predictions.jsonl 6e8961d57b5c0ffaafcb39177deabf6e65c0af0cb8a541efc3b13395411353fd
- a1-beta-s1-on-232304-predictions.jsonl 6b1babd7e4e7ed6d4125bf4dd3fe2c1307097eae84bd461207aadbbe88c086b0
- a1-beta-s2-on-232304-predictions.jsonl 7105aed8864fde00777c10a0f12e2d952cb2327dcb0fc3c472bd3396deea7351
- a4-beta-on-232304-predictions.jsonl 6f65dd8331faca6e12da4a29e24089b02593edf83e90f278a611a145e2e04d0b
- yaw-t0-on-021320-predictions.jsonl c5b0fbd31f4cbb505647b2d982eaa2e8f559ea3ffb57fbdfaa602affd2973e47
- yaw-t1-on-021320-predictions.jsonl 87251b518129f70a84d0d19e9e9ea5ebb6ac068fae47e3a5f6900427f929b296
- yaw-t2-on-021320-predictions.jsonl 79d2bde976faf061262467d2be6e4eb7c18bf1330c6523d0826fb79e0e56f855
- a1-beta-s0-on-021320-predictions.jsonl 0dde6f31c798817d42d229db9b91b60f677a9c16627a53fea59b9fbb7643fd8c
- a1-beta-s1-on-021320-predictions.jsonl 4d43c30dd6e510376495f0ef744bb63a7402018105438e47ee54ac37c322991d
- a1-beta-s2-on-021320-predictions.jsonl 456dbc6027fe817f68b245882122ea91b5a379deb1a4a3c98f85c0e3ae815d5f
- a4-beta-on-021320-predictions.jsonl f92a9f19acb57a2704459e72a48cb605aef066df07fa43101ae9b6c1062f3582
- yaw-t0-on-025230-predictions.jsonl ca5e61dccc9afad62fbb34587d2e10217684126cfce1536575b8ebf4d37dec78
- yaw-t1-on-025230-predictions.jsonl 41348aa6ab66d394b9ad91b0d113b397761849976cbf6236b9e1ade6aaf5ffd0
- yaw-t2-on-025230-predictions.jsonl 8e783c86b5b58fe9ac4bdb4ca1dd43f7d92356ca4f5f80fa981993c3cb570295
- a1-beta-s0-on-025230-predictions.jsonl 2dd4e585f97a335abf3d16e9a1c39274a4d36c1b50e0d8c024cbb8e54a8fe37b
- a1-beta-s1-on-025230-predictions.jsonl 5363a6bd93791f4a55eaa0f835750a69f9b9dc0221fbf27c5aa7e2fba03f52cf
- a1-beta-s2-on-025230-predictions.jsonl 3cde58379ff4f38f321e0c61921ff8e5fe3fe81753368f211ada5187c0c827ae
- a4-beta-on-025230-predictions.jsonl 2398d014e0feaf25eab476945e94e809c9b8493d7ac770a20daa13b6fb74a757
