# Calibration take `20260923T204707-487Z-45572-2`: settings pinned, yaw measured, pitch not measurable

**Take.** `C:\Users\volpe\Videos\2026-09-23 15-47-07.mkv`, HEVC, 118.7 s, media sha256 `e8259ef8...0bc09`.

**Artifact.** `data/human/calibration/20260923T204707-487Z-45572-2/`:
- `calibration.json` `c52b0f18...`;
- freeze `artifact-hashes.json` `f6a41535...` (clean check);
- 9 native settings-frame crops, each pinned with the full frame's decoded-BGR sha256;
- the scripts.

**Registration.** A calibration session in the registry's new `calibration_sessions` list: its own group, never in a
split. The importer's own registry check still passes.

**Recorder.** Integrity ok. 14,242 of 14,242 frames matched, 2 unwritten tail packets, +21 ms, 0.333 ms residual. The
first-16-packet forward prediction matches exactly (the anchor holds; HEVC).

**Content, from the input log and frames:**

| File time | Content |
|---|---|
| 0-57 s | play |
| 59.0-70.9 s | a slow 360° yaw turn |
| 73-86 s | the pitch sweep |
| 88.5-116.5 s | the settings look (Esc into Settings; keyboard, then controller pages) |

## 1. Settings, read from native frames (campaign settings identity)

- **Mouse.** Horizontal 1.89 / vertical 1.89, no inversion. **Mouse Smoothing on. Mouse Acceleration on**, activation
  threshold 1, factor 1.00. Raw Input on; high-polling optimization off.
- **Hero (Spider-Man).** Targeting Sensitivity While Aloft 100. **Hold to Swing on. Simple Swing off; its key is Caps.**
  Hold to Wall Crawl on; Hold to Run on Walls off; wall crawling "Advance Vertically Upwards"; Attack Range Hint on.
- **Keyboard bindings.**
  - Movement W/A/S/D, Space jump, LCtrl slow walk (hold).
  - LMB Spider-Power, RMB Web-Cluster.
  - **Melee: V and Mouse 5.**
  - F Get Over Here, LShift Web-Swing, **E and 2 Amazing Combo**, Q Ultimate.
  - **Team-Up A = C; Team-Up B = X.**
  - **Get Over Here Targeting: Mouse 4 and 2.**
- **Controller (all heroes, stick).** Horizontal 265, vertical 75, profile Default; reticle Circle; vibration on, 80.
  The controller button page reads "controller required", which is consistent with no pad.
- **FOV.** Not shown; the Display tab was not opened.

**What this changes against earlier records:**
1. **Mouse 5 is confirmed as a second melee binding**, as you decided.
2. **Mouse 4 (X1) is Get Over Here Targeting.** The single X1 press in 171533, and the 3 in 051828, are a real
   targeting control, not noise. It stays `unsupported` (no fit action) unless the fit lane adds it.
3. **"2"** is a second binding of both Amazing Combo and Get Over Here Targeting. I am not aliasing it (it is
   ambiguous). It stays unsupported.
4. **X** (Team-Up B) and **LCtrl** (slow walk) are unsupported.
5. **Swing.** The 09-23 statement "default swing settings" matches these frames: hold to swing on, simple swing off.

## 2. Yaw: 0.0330738° per count

- **Method.** The pre-turn view (a still frame at 58.60 s) is compared with every frame of the turn: phase
  correlation on the upper scene band, with the static practice-range overlay masked.
- **The view comes back between the two final rest positions:** −1.161 px at +10,891 counts and +1.629 px at +10,876
  counts (at 640 px width, phase response 0.85).
- **Result.** Zero horizontal shift at **10,884.8 counts per 360°**, so **0.0330738°/count**.
- **Uncertainty.** About ±2 counts (±0.02 %). Both ends are still frames, so latency does not enter.
- **Cross-check.** The value equals 0.0175 × 1.89 = 0.033075 to 0.01 %. 0.0175 is the factor common sensitivity
  converters use for this game; I have not verified it against a primary source.
- **Open: speed dependence.** Acceleration shows as on (factor 1.00) and smoothing is on. The closure integrates
  this turn's speeds (about 200-1,400 counts/s). Frame-pair pixels per count fall about 20 % from slow to fast
  (r = −0.38), which may be acceleration or a measurement artefact (parallax, perspective across the band).
  **Settling it needs two more 360° turns from James: one slow, one fast.**

## 3. Pitch: not measurable from this take (header `pitch_deg_per_count: null`)

- **Why.** The third-person camera orbits the hero on pitch, so vertical image shift does not track rotation, and
  frame-pair phase correlation fails. The sweep also went past both limits, so counts were lost at each clamp.
- **Observed.**
  - Up from the start, the view stops at −1,941 to −1,965 counts.
  - From the top limit, the down limit is reached within 4,624 counts; the extra +119 counts move the image 0.2 px.
  - The end view is about 1° below the start, although the net count total is +182.
- **What the clamps give.** Only (pitch range) / gain. If the pitch gain equals the yaw gain, the range between
  limits is 152.9°, but that is not established.
- **Next take for pitch.** A sweep that stays inside the limits and returns to a still start view, or a published
  pitch range. Until then the fit masks pitch labels, as the reader already allows.

## 4. What happens next

- **The header calibration for every same-settings session** is
  `{yaw_deg_per_count: 0.0330738, pitch_deg_per_count: null, source: calibration.json}`. That covers DPI 800 and
  sensitivity 1.89, which is every campaign session so far.
- **Next, in your order:**
  1. Rewrite the 171533 step file with this calibration and the melee alias (Mouse 5), noting the hash change in its
     freeze.
  2. Assemble 051828: the independent review is in, and the no-pad attestation goes into its `settings.json`.
  3. 200129.
  4. Take 2.
