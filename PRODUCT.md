# Mac Eye Control — Product Requirements

## Overview

**Mac Eye Control** is a macOS application that enables hands-free computer control using eye gaze and head movements tracked via a built-in MacBook webcam. Built on top of Python-Gaze-Face-Tracker (MediaPipe + OpenCV).

Target user: personal use / experimentation.

---

## Core Interactions

| Action | Trigger |
|---|---|
| Move cursor | Gaze direction |
| Left click | Double blink within ~0.5s |
| Scroll up | Head pitch up (above threshold) |
| Scroll down | Head pitch down (below threshold) |
| Pause/resume control | To be defined |

---

## Features

### F1 — Gaze-to-Screen Calibration
- On first launch: full calibration sequence (9 points on screen)
- User looks at each point for a fixed duration; system records iris + head pose data
- Calibration result saved to `calibration.json`
- On subsequent launches: calibration loaded automatically from file
- Option to recalibrate at any time (button or hotkey)

### F2 — Cursor Control
- Mouse cursor moves in real time following the user's gaze
- Smoothing applied to prevent jitter
- Cursor is always visible so the user can see where they are looking

### F3 — Double Blink Click
- Two blinks detected within ~0.5 seconds = left mouse click
- Single blinks (natural) do not trigger click
- Visual feedback on screen when click is registered (brief indicator)

### F4 — Head Tilt Scroll
- Head pitch above a comfortable threshold → scroll up
- Head pitch below a comfortable threshold → scroll down
- Neutral head position = no scroll
- Scroll speed proportional to pitch magnitude beyond threshold
- Threshold set high enough to avoid triggering during normal head movement

### F5 — Configuration
- All thresholds and parameters stored in a config file (e.g. `config.json`)
- Parameters: blink interval, scroll threshold, scroll speed, smoothing window, camera index
- No need to edit source code to tune behavior

---

## Platform
- macOS only (MacBook built-in webcam)
- Python 3.x

---

## Out of Scope (for now)
- IR camera support
- Eye gesture shortcuts (wink, etc.)
- On-screen gaze keyboard
- Multi-monitor support
- Windows / Linux support
