# Calibration — Mac Eye Control

## Overview

Calibration maps the user's iris position and head pose to screen coordinates.
The system collects samples at 9 known screen positions and fits a polynomial
regression model (degree 2, Ridge regularization) that converts
`(iris_dx, iris_dy, pitch, yaw)` → `(screen_x, screen_y)` in real time.

Calibration data is saved to `data/calibration.json` and loaded automatically
on the next launch. If the file is missing or corrupted, calibration runs
automatically at startup.

---

## Triggering Calibration

| Trigger | When |
|---|---|
| **Automatic** | No `data/calibration.json` found, or file is corrupted |
| **Manual — key `R`** | User presses R during normal operation |

When `R` is pressed:
1. Head pose is reset automatically (equivalent to pressing `C`)
2. Full 9-point calibration runs
3. New model is fitted and saved, replacing the previous file
4. Gaze control resumes with the new calibration

---

## Head Pose Reset — Key `C`

Before calibrating, the system needs a "zero" baseline for head orientation.

**What it does:** saves the current head pitch/yaw/roll as the neutral position.
All subsequent pitch/yaw values used for gaze mapping and scroll control are
measured *relative* to this baseline.

**When to press C:**
- Sit in your normal working posture and look straight ahead
- Press `C` — the current head position is recorded as zero
- The on-screen message "Head pose reset — look straight ahead" confirms it

**Why it matters:** if calibration is done with the head tilted, gaze control
will be offset. Resetting head pose before calibration ensures the neutral
gaze direction aligns with the center of the screen.

> `R` resets head pose automatically before starting calibration.

---

## Calibration Window — Step by Step

### Grid layout

9 points are shown in a 3×3 grid at 10%, 50%, and 90% of the screen dimensions:

```
[1] [2] [3]   ← y = 10%
[4] [5] [6]   ← y = 50%
[7] [8] [9]   ← y = 90%
 ↑   ↑   ↑
10% 50% 90%
```

### For each point

**Phase 1 — Gaze fixation detection**

The system waits until you are genuinely looking at the dot with open eyes.
It does NOT proceed on a fixed timer.

| State | Hint text | Arc colour |
|---|---|---|
| Eyes closed | "Open your eyes!" | — |
| Eyes open, gaze not on dot | "Look at the dot..." | — |
| Gaze shifted, stabilising | "Look at the dot..." | Orange filling |
| Gaze > 50% stable | "Hold still..." | Orange filling |
| Not first point, gaze hasn't moved | "Look at the NEW dot!" | — |

Rules enforced during Phase 1:

- **Eyes must be open.** Eye Aspect Ratio (EAR) is measured every frame.
  Closed eyes produce frozen iris landmarks that mimic perfect fixation —
  the system detects this and resets the counter.

- **Gaze must shift between points.** For points 2–9, the iris must move
  at least `calibration_gaze_shift_px` pixels (default: 3 px) from the
  previous fixation before the new fixation counter starts. This prevents
  the user from staying on one dot and having all 9 points recorded there.

- **Consecutive stable frames required.** The frame-to-frame iris movement
  must stay below `fixation_movement_threshold` (default: 2.5 px) for
  `fixation_window_frames` consecutive frames (default: 20, ≈ 0.67 s at 30 fps).
  Any movement above the threshold resets the counter to zero.

**Phase 2 — Data collection**

Once fixation is confirmed, a green arc counts down while
`calibration_collect_frames` frames (default: 30, ≈ 1 s) are recorded.
Frames where eyes are closed are skipped — they do not count toward the total.

The recorded values are averaged:
- `iris_dx`, `iris_dy` — average iris offset from eye corner (pixels)
- `pitch`, `yaw` — average head angles (degrees, relative to reset baseline)
- `screen_x`, `screen_y` — known screen position of the calibration dot

---

## Model

After all 9 samples are collected, `GazeMapper` fits a scikit-learn pipeline:

```
PolynomialFeatures(degree=2) → Ridge(alpha=1.0)
```

Input features: `[iris_dx, iris_dy, pitch, yaw]`
Output: `[screen_x, screen_y]`

The fitted model is serialised with `pickle`, base64-encoded, and stored in
`data/calibration.json` alongside the raw samples.

---

## Config Parameters

All parameters are in `config/default_config.json`.

| Parameter | Default | Description |
|---|---|---|
| `calibration_points` | `9` | Number of calibration points (3×3 grid) |
| `calibration_collect_frames` | `30` | Frames to collect per point after fixation |
| `calibration_dwell_sec` | `1.0` | Legacy — not used in current fixation-based flow |
| `fixation_window_frames` | `20` | Consecutive stable frames required for fixation |
| `fixation_movement_threshold` | `2.5` | Max allowed frame-to-frame iris delta (px) before reset |
| `calibration_gaze_shift_px` | `3` | Min iris shift required when moving to next point |
| `calibration_path` | `data/calibration.json` | Where calibration is saved/loaded |

### Tuning tips

**Fixation too hard to achieve (arc keeps resetting):**
- Increase `fixation_movement_threshold` to `3.5–4.0`
- Decrease `fixation_window_frames` to `15`

**Fixation too easy (passes without really looking at dot):**
- Decrease `fixation_movement_threshold` to `1.5–2.0`
- Increase `fixation_window_frames` to `25–30`
- Increase `calibration_gaze_shift_px` to `5`

**Collection phase too long:**
- Decrease `calibration_collect_frames` to `20`

---

## Files

| File | Description |
|---|---|
| `src/calibration/calibration.py` | `CalibrationSession` — orchestrates the full flow |
| `src/calibration/mapping.py` | `GazeMapper` — model fit, predict, save, load |
| `src/tracking/fixation_detector.py` | `GazeFixationDetector` — consecutive-frame stability check |
| `src/tracking/blink_detector.py` | `BlinkDetector.is_eyes_open()` — EAR-based eye state |
| `src/ui/calibration_ui.py` | `CalibrationUI` — fullscreen tkinter window |
| `data/calibration.json` | Auto-generated calibration file (gitignored) |
