# CLAUDE.md — Mac Eye Control

## Project

Mac Eye Control — hands-free macOS computer control via eye gaze and head movements.
Built on Python-Gaze-Face-Tracker (MediaPipe + OpenCV). See PRODUCT.md for full requirements.

---

## Tech Stack

| Tool | Purpose |
|---|---|
| Python 3.x | Language |
| OpenCV (`cv2`) | Video capture, drawing |
| MediaPipe | Face mesh, iris tracking (468 landmarks) |
| NumPy | Math, array ops |
| `pyautogui` | Mouse movement, clicking, scrolling |
| `pynput` | Alternative to pyautogui if needed on macOS |
| `tkinter` | Calibration UI window |
| `json` | Config and calibration persistence |

---

## Project Structure

```
Python-Gaze-Face-Tracker/
├── src/
│   ├── tracking/
│   │   ├── __init__.py
│   │   ├── face_mesh.py        # MediaPipe wrapper
│   │   ├── iris_tracker.py     # Iris tracking logic
│   │   ├── blink_detector.py   # Blink detection (EAR-based)
│   │   └── head_pose.py        # Head pose estimation (pitch/yaw/roll)
│   ├── calibration/
│   │   ├── __init__.py
│   │   ├── calibration.py      # Calibration flow (9-point)
│   │   └── mapping.py          # Eye features → screen coords mapping
│   ├── control/
│   │   ├── __init__.py
│   │   ├── cursor.py           # Mouse cursor movement
│   │   ├── clicker.py          # Double blink click logic
│   │   └── scroller.py         # Head tilt scroll logic
│   ├── ui/
│   │   ├── __init__.py
│   │   └── calibration_ui.py   # Fullscreen calibration window (tkinter)
│   └── utils/
│       ├── __init__.py
│       ├── angle_buffer.py     # Rolling average (from AngleBuffer.py)
│       └── config.py           # Config loader/saver
├── config/
│   └── default_config.json     # Versioned default parameters
├── data/
│   └── calibration.json        # Auto-generated, gitignored
├── logs/                       # CSV logs, gitignored
├── tests/
│   └── __init__.py
├── tools/
│   └── mediapipe_landmarks_test.py  # Dev utility
├── docs/
│   └── overview.md
├── main.py                     # Entry point (thin orchestrator)
├── AngleBuffer.py              # Legacy — do not use, use src/utils/angle_buffer.py
├── requirements.txt
├── README.md
├── PRODUCT.md
└── CLAUDE.md
```

---

## Development Phases

Work in this order. Do not start a phase until the previous one is stable.

### Phase 1 — Calibration
- Show fullscreen window with 9 calibration points (3x3 grid)
- For each point: display dot, wait for user to fixate, record `(iris_dx, iris_dy, pitch, yaw)` averaged over ~1 second
- Fit a mapping model from eye features to screen coordinates (start with polynomial regression or simple interpolation)
- Save result to `calibration.json`
- Load on startup if file exists; skip calibration flow

### Phase 2 — Cursor Control
- Use calibration mapping to convert current eye features → predicted `(screen_x, screen_y)`
- Move mouse cursor via `pyautogui.moveTo()`
- Apply smoothing (extend existing `AngleBuffer` pattern or use exponential moving average)
- Cursor must always be visible and follow gaze in real time

### Phase 3 — Double Blink Click
- Detect blink using existing EAR logic
- Track blink timestamps; if two blinks occur within 0.5s → fire left click
- Single blinks must NOT trigger click
- Show brief on-screen indicator when click fires

### Phase 4 — Head Tilt Scroll
- Use smoothed pitch from existing head pose estimation
- Define `SCROLL_THRESHOLD_UP` and `SCROLL_THRESHOLD_DOWN` (degrees beyond neutral)
- If pitch exceeds threshold: scroll in that direction via `pyautogui.scroll()`
- Scroll speed = linear function of pitch magnitude beyond threshold
- Neutral zone = no scroll

### Phase 5 — Config & Polish
- All thresholds in `config.json` (blink interval, scroll thresholds, scroll speed, smoothing, camera index)
- Hotkey or on-screen button to pause/resume gaze control
- Hotkey to trigger recalibration
- Clean console output (no spam per frame)

---

## Key Parameters (defaults)

```json
{
  "camera_index": 0,
  "blink_double_interval_sec": 0.5,
  "scroll_threshold_pitch_up": 15,
  "scroll_threshold_pitch_down": -15,
  "scroll_speed": 5,
  "smoothing_window": 10,
  "calibration_dwell_sec": 1.0,
  "calibration_points": 9
}
```

---

## macOS Notes

- `pyautogui` requires **Accessibility permissions** in System Settings → Privacy & Security → Accessibility
- MacBook built-in webcam index is `0`
- Do not use `cv2.imshow` for the main control overlay — it blocks the event loop. Use a separate thread or avoid fullscreen OpenCV windows during active control
- Calibration window should be `tkinter` fullscreen to cover the entire display

---

## Rules

- Do not modify `AngleBuffer.py` — it works, extend it if needed
- Do not break existing `main.py` logic — refactor incrementally
- Keep each phase in its own module; `main.py` orchestrates
- No hardcoded screen resolutions — always query via `pyautogui.size()`
- Do not use `time.sleep()` in the main tracking loop — it will drop frames
- Ask before adding new dependencies not listed in this file
