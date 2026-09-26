# admission-owner: option B on the late take, check (1) done; check (4) cannot meet its tolerance from this take (decision)

**James's words** are recorded in the registry row's `note`: "the binds are definitely the same in any meaningful way,
otherwise id notice a muscle memory difference which i didn't". The row now reads *pending the lead's option B checks*.
The tally row is `pending`, and the tally is regenerated. The late motor quote is back to the single `fbe6693` line: I
had removed the `83c05f1` quote under option A. Under B the take needs its own per-session motor text, which I'll add
with the settings-change cut.

## Check (1): effective bindings for every pressed key, done (decode-free)

- **Method:** `late/bindings_equivalence.py` (`6fc8b2fd…`), output `late/bindings-equivalence.json` (`9f2adb9b…`).
  - Per action id and slot: Spider-Man's (1036) value if set, else the account default's (hero 0), else the game default.
  - Primary and secondary are the same binding. Gamepad slots are ignored.
  - A key's binding is the set of ids it triggers, compared across accounts.
  - Pressed keys come from `inputs.jsonl` after the cut (second Esc 5.438 s + 2 s = 7.438 s), counting press transitions
    with focus reset.
- **Result: no semantic difference on any pressed key.**

  | Pressed (count) | Campaign ids | Main ids | Verdict |
  |---|---|---|---|
  | Space 1,363 · A 895 · D 601 · W 565 · S 344 · C 150 · Alt 6 · Q 4 · Tab 3 · V 1 · LWin 1 · Mouse1 334 · Mouse2 874 | none set | none set | equal: the same game default on both |
  | E 235 | 20 | 20 | equal (explicit) |
  | F 111 | 15 | 15 | equal (explicit) |
  | Caps Lock 1, wheel-up 45 | 133 | 133 | equal (primary and secondary swapped: representational) |
  | Mouse4 18 | 99 | 99 | equal (explicit) |
  | Mouse5 23 | 14 (secondary) | 14 (secondary) | equal (explicit) |
  | **LeftShift 400** | 16 | none set | **default-dependent**: the campaign sets 16 = LeftShift; main leaves 16's keyboard slot to the game default. Check (2) settles it on frames. |

- **The 29 differences:**
  - **Representational (13):**
    - the Simple Swing swap (133);
    - gamepad-only keys (133, 16, 20, 48, 99, 172–174, BattleComm 2);
    - main's hero-0 fallbacks that 1036 overrides the same way.
  - **Semantic on unpressed keys:**
    - 15 + R;
    - 22 = Tilde;
    - 36 = B;
    - 143–146 (One–Four, NumPad1–4) against 147–148 (Five–Six, NumPad5–6);
    - 144's NumPadTwo;
    - 7 = One (campaign) against the default (main).

    None of R, Tilde, B, the number row or the numpad is pressed after the cut.
  - **Default-dependent on a pressed key:** 16 (LeftShift) only.
  - **Motor (4):** acceleration off (against on at threshold 1.0), with align and smoothing unset. This is check (4)'s
    job.
  - The full list is in the JSON.
- **Residual, stated:** 18 slots are set on one account and default on the other. If an unknown default bound a pressed
  key to an extra action, the files could not show it; the two cases are Q (4 presses) and V (1). James's statement and
  check (2) cover this.

## Check (4): the gain at the calibration record's tolerance is not measurable from this take

- **The established method** (030045) is still-to-still. The camera rotation between two still views bracketing a turn
  gives only the excess over whole revolutions, so the estimator's ~3 % focal error touches a few degrees, not 360°.
  - Its stated tolerance is ±0.02–0.08 % per class, and ±0.25 % for the slow class (the parallax correction).
  - On a full turn that is ±0.3–0.9°.
  - It needs the camera to rotate without translating: in 030045 James stood still, and a mere 8° of pitch parallax
    cost ±0.8°.
- **In this take** (input log only, after the cut): 179 still windows of at least 0.35 s, and **4** turns between still
  views within 3 % of a whole revolution (at 746, 837, 945 and 1,434 s).
  - All four have movement keys held at the still ends, and 3.6–9.9 s of play between them.
  - The hero translates, so parallax enters the rotation fit, of the kind that already cost ±0.8° on the calibration
    take.
  - None can deliver ±0.9°.
- **The per-pair estimator** summed over motion carries the ~3 % focal error. A relative comparison against an admitted
  session's same-estimator ratio could reach roughly 1 %. That tells 1.89 from any other sensitivity on file (1.63, 2.0,
  3.83: all ≥ 5 % away) but not the stated tolerance.

**Options:**
- **(a) Hold,** as your rule says when (4) cannot pass.
- **(b) Relax (4) to a relative per-pair check at about 1 %.** That distinguishes a wrong sensitivity; together with
  the file's 1.89 and James's statement, it covers sensitivity. It does **not** cover acceleration-off exactly: the
  030045 record showed acceleration at 1.00 had no measurable effect, but only on the campaign account.
- **(c) Recommended, and time-critical: a 1-minute calibration take on the main account, now, while the game is open.**
  James repeats 030045's protocol on the main account's Spider-Man, in the range, as a separate recording: stand still,
  four rightward 360° turns at rising speed, each ending on a still view.
  - It measures the main profile's gain (acceleration off) with the established method and its tolerance.
  - The take's own frames can then add a consistency check at about 1 % (b).
  - It is registered as a calibration entry, never a split. I run 030045's pipeline on it after the processes close.
  - Limit: it measures the settings as they are now, not during the take. The saved file (written 23:35, after the
    take) shows 1.89 and acceleration off, and James changed nothing after the opening Esc pair.

**Meanwhile:** the settings-change cut (5) and the regime and frame checks (2, 3) wait on your answer; the latter need a
decode after the game and OBS close anyway. I'm writing the lane-doc entry for today's batch.
