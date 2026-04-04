# Feature: Cursor Accuracy MVP

## Status
Ready for Development

## Problem Statement

The current cursor control system produces a cursor that is usable for large targets but
unreliable for everyday macOS navigation. Users cannot consistently hit toolbar icons
(~32x32 pt), menu bar items, or dock icons because of three compounded problems:

1. **Residual jitter at rest.** Even when the user holds a steady gaze, the cursor
   oscillates 5-15 px around the target. This is caused by raw EMA smoothing with a
   fixed alpha (0.08) applied to noisy per-frame iris coordinates that are computed from
   integer-rounded MediaPipe landmark positions.

2. **Slow approach + overshoot on large saccades.** When the user redirects gaze across
   the screen, the EMA carries history from the old position. The cursor creeps toward
   the new target over 20-30 frames (~1 second at 30 fps) instead of snapping quickly.
   Users overcorrect, causing positional oscillation near the destination.

3. **No magnetic pull toward known UI target zones.** Once the cursor is within a few
   pixels of an icon or menu item, micro-tremor pushes it off target. There is no
   mechanism to assist convergence on small interactable areas.

None of these problems were addressed in the Phase 2 implementation. The client-bugs doc
(Issue 3) planned EMA and deadzone basics, which are now in place, but those alone are
insufficient for reliable icon-level targeting. This document covers the next layer of
improvements required to make the cursor genuinely usable for common macOS tasks.

---

## User Story

As a user relying solely on gaze for cursor control, I want the cursor to reach and
hold position on a menu bar item or dock icon so that I can reliably trigger a double-
blink click without the cursor drifting away between fixation and click.

**Scenario A — Menu bar navigation**
1. User looks at the Apple menu icon in the top-left corner.
2. Cursor travels from center-screen to the corner within approximately 0.5 seconds.
3. Cursor settles and stays within the icon bounds while the user prepares to double-blink.
4. Double-blink fires; click lands on the icon, not adjacent empty space.

**Scenario B — Dock icon activation**
1. User looks at a specific dock icon at the bottom.
2. Cursor approaches from an upper region of the screen.
3. After 3-4 frames near the icon, cursor locks to it rather than bouncing between
   adjacent icons.
4. User double-blinks; correct application is activated.

**Scenario C — Returning to rest position**
1. User holds gaze on a fixed text cursor in a document.
2. They naturally blink once (not a double-blink).
3. During and after the blink, the cursor does not drift more than 5 px from the text
   cursor position.

---

## Acceptance Criteria

1. After gaze fixation is established on a stationary target (verified by
   `GazeFixationDetector.is_fixated()` returning True), cursor movement in the next 10
   frames must remain within a 6 px radius of the settled position (measured in logical
   screen points on a 1280x800 surface).

2. When gaze moves from one screen corner to the opposite corner (a saccade of ~1400
   logical px), the cursor must reach within 30 px of the destination within 20 frames
   (667 ms at 30 fps). This verifies that dual-speed EMA raises alpha during large
   movements.

3. After criterion 2 is met (cursor within 30 px), the cursor must not overshoot the
   destination by more than 15 px in any subsequent frame. This verifies the fast-alpha
   phase reverts to slow-alpha before overshooting.

4. When the predicted gaze position is within the snap radius (`cursor_snap_radius_px`,
   default 20 pt) of any registered snap zone center, the final cursor output must be
   the snap zone center, not the raw EMA output. Measurable: place a snap zone at
   (100, 100), inject a predicted position of (112, 108) — cursor must land on (100, 100).

5. When the predicted gaze position is outside all snap zones, cursor output must be the
   raw EMA output (no snap attraction applied). Measurable: with snap zone at (100, 100)
   and predicted position at (200, 200), cursor must land within 2 px of (200, 200).

6. Iris noise filter: `get_iris_positions()` must clip each iris coordinate component to
   a rolling median of the last 5 frames. A single-frame spike (>10 px deviation from
   the median) must not move the final cursor output by more than 2 px.

7. Deadzone remains active: cursor must not move when the EMA-smoothed position changes
   by less than `cursor_deadzone_px` (default 8 px) in both axes simultaneously.

8. All new parameters are present in `config/default_config.json` with values matching
   the defaults listed in the Configuration section of this document.

9. No existing acceptance criteria for Phase 2 (cursor follows gaze), Phase 3 (double-
   blink click), and Phase 4 (head-tilt scroll) are broken by these changes. The full
   existing test suite must pass.

10. The cursor control loop still completes within the 33 ms frame budget. Measured by
    logging frame processing time; median must be below 20 ms, p99 below 30 ms, with
    snap zone list containing up to 50 zones.

---

## Scope

### In scope
- Dual-speed (adaptive) EMA in `CursorController` that raises alpha during fast gaze
  movement and reverts to slow alpha once movement falls below a velocity threshold.
- Per-frame iris spike filter in `IrisTracker` (rolling median of last N frames per
  coordinate; spike = deviation > configurable threshold).
- Static snap-to-zone mechanism in `CursorController`: a list of rectangular zones
  (each defined by center + half-width + half-height in logical screen points); when
  EMA output falls inside a zone, snap to zone center.
- A `SnapZoneRegistry` helper that loads zones from config or from a separately provided
  JSON file, and provides an O(n) lookup given a cursor position.
- New config keys for all new parameters (see Configuration section).
- Unit tests covering each acceptance criterion above.

### Out of scope
- Dynamic snap zone inference (automatically learning icon positions from usage patterns).
- Retina-aware automatic zone generation by reading screen accessibility metadata.
- Gaze prediction / Kalman filter (more complex; belongs in a future accuracy pass).
- Calibration model changes (polynomial degree, more calibration points).
- Per-user profile persistence for snap zones.
- Scroll or click behavior changes.
- Multi-monitor support.
- IR camera or hardware-level improvements.

---

## Technical Analysis

### Current state

**`src/control/cursor.py` — CursorController**
- Single fixed EMA: `ema = alpha * new + (1-alpha) * ema` where `alpha = 0.08` (config
  key `smoothing_alpha`).
- Flat deadzone: skip move if `|dx| < deadzone_px AND |dy| < deadzone_px`.
- No awareness of gaze velocity; alpha never changes during a saccade.
- No snap-to-zone logic.

**`src/tracking/iris_tracker.py` — get_iris_positions**
- Computes iris center via `cv2.minEnclosingCircle` on 4 landmark points (indices 474-477
  left, 469-472 right).
- Returns `int32` center coordinates; integer truncation introduces up to 1 px rounding
  noise per axis per frame.
- No temporal filtering; every frame's value is used raw.
- dx/dy is computed as vector from outer eye corner to iris center. Corner is a single
  landmark, which is itself subject to MediaPipe jitter (~0.5-1 px).

**`src/calibration/mapping.py` — GazeMapper**
- Ridge regression with degree-2 polynomial features on 4 inputs: `(iris_dx, iris_dy,
  pitch, yaw)`.
- 9-point calibration produces ~36 features after polynomial expansion; Ridge alpha=1.0
  regularizes well for this sample size.
- No per-prediction confidence score; bad frames produce silent outliers fed into EMA.

**`AngleBuffer.py` / `src/utils/angle_buffer.py`**
- Simple rolling mean buffer of fixed size. Used for head-pose smoothing.
- Not used for cursor output (cursor uses EMA instead).

**`src/tracking/fixation_detector.py` — GazeFixationDetector**
- Frame-to-frame movement threshold (default 2.5 px). Fixation confirmed after 20
  consecutive stable frames.
- Currently used only inside `CalibrationSession`. Not wired into the live control loop.

**`config/default_config.json`**
- `smoothing_alpha: 0.08` — intentionally conservative (was tuned down from 0.15 to
  reduce jitter from Issue 3).
- `cursor_deadzone_px: 8` — reasonably sized but currently prevents cursor from moving
  when inside small targets.

### Affected modules

| Module | Change required |
|---|---|
| `src/tracking/iris_tracker.py` | Add `IrisFilter` class with rolling median buffer; `get_iris_positions` stays pure, filter applied by caller in main loop or as a wrapper |
| `src/control/cursor.py` | Replace fixed EMA with dual-speed adaptive EMA; add `SnapZoneRegistry` lookup; add `set_snap_zones()` method |
| `src/control/snap_zones.py` | New file — `SnapZoneRegistry` class |
| `config/default_config.json` | Add new config keys |
| `main.py` | Instantiate `IrisFilter`; optionally load snap zones from config; wire iris filter output to `gaze_mapper.predict()` |

### New modules required

**`src/control/snap_zones.py`**
Responsibility: manage a list of rectangular snap zones in logical screen point space.
Exposes:
- `SnapZoneRegistry(zones: list[dict])` — each dict has keys `cx`, `cy`, `hw`, `hh`
  (center x/y, half-width, half-height, all in logical points).
- `snap(x: float, y: float) -> tuple[float, float] | None` — returns snapped center if
  point falls inside any zone, else None.
- `load_from_config(config: dict) -> SnapZoneRegistry` — reads `snap_zones` key from
  config (empty list by default).

**`src/tracking/iris_filter.py`**
Responsibility: temporal noise reduction on iris coordinate stream.
Exposes:
- `IrisFilter(window: int, spike_threshold_px: float)` — rolling median buffer per axis.
- `update(dx: float, dy: float) -> tuple[float, float]` — push new values, return
  filtered (dx, dy). On spike detection, returns previous median instead of raw value.

### Data flow

```
Camera frame (physical pixels, Retina ~2560x1600)
    |
    v
MediaPipe FaceMesh — landmark positions in physical pixel space (img_w x img_h)
    |
    v
get_iris_positions() — returns raw iris dx/dy in physical pixel space (int32)
    |
    v
IrisFilter.update(raw_dx, raw_dy)
    — rolling median of last 5 frames in physical pixel space
    — spike filter clips single-frame outliers
    — output: filtered (iris_dx, iris_dy) still in physical pixel space
    |
    v
HeadPoseEstimator.estimate() — pitch, yaw in degrees (no coordinate space issue)
    |
    v
GazeMapper.predict(filtered_dx, filtered_dy, pitch, yaw)
    — polynomial regression output: (pred_x, pred_y) in logical screen points
      (pyautogui logical space: 1280x800 on Retina 16" MacBook)
    |
    v
CursorController.move(pred_x, pred_y)
    [1] Clamp to screen bounds (logical points)
    [2] Dual-speed EMA:
        - compute velocity = distance(new_pos, ema_pos)
        - if velocity > cursor_fast_velocity_threshold_px: use alpha_fast
        - else: use alpha_slow (existing smoothing_alpha)
        - ema = alpha * new + (1-alpha) * ema
    [3] Deadzone check (unchanged logic)
    [4] SnapZoneRegistry.snap(ema_x, ema_y)
        - if inside a zone: output = zone center (logical points)
        - else: output = ema position (logical points)
    [5] pyautogui.moveTo(output_x, output_y)
        — pyautogui accepts logical points; Retina scaling is handled by pyautogui/macOS
```

**Retina display impact:** All processing from GazeMapper output onward is in logical
screen points. `pyautogui.size()` returns logical dimensions (e.g. 1280x800 on a 2560x1600
Retina display). `pyautogui.moveTo()` takes logical points. No explicit Retina scaling
factor is needed at the cursor output stage — the OS handles it. However, iris dx/dy
values from MediaPipe are in physical pixel space (camera resolution, typically 640x480
for the built-in webcam, not Retina). The GazeMapper was trained on these physical-pixel
iris values and logical screen coordinates, so it already encodes the implicit mapping.
No new code in this feature introduces coordinate space confusion.

### Key algorithms or logic

**Dual-speed adaptive EMA**

The core idea is a velocity-gated alpha switch. On every frame:

1. Compute Euclidean distance between the incoming clamped prediction and the current EMA
   state. Call this `velocity_px`.
2. If `velocity_px > cursor_fast_velocity_threshold_px` (config default: 80), use
   `cursor_alpha_fast` (config default: 0.35). This allows the cursor to chase fast
   saccades without 30-frame lag.
3. If `velocity_px <= cursor_fast_velocity_threshold_px`, use `smoothing_alpha` (existing
   key, default: 0.08). This is the "hold still and settle" mode with heavy smoothing.
4. Apply EMA with the chosen alpha.

This two-state model avoids the need for a PID controller or Kalman filter while
addressing both the lag-on-saccade and jitter-at-rest problems.

The velocity threshold is in EMA space (distance from current EMA to incoming prediction),
not raw signal velocity. This prevents a momentary noise spike from falsely triggering
fast mode.

**Iris spike filter (rolling median)**

A deque of length `iris_filter_window` (default: 5) is maintained per axis (dx, dy).
On each frame:
1. Push the new raw value into the deque.
2. Compute the median of the deque.
3. If `|raw - median| > iris_spike_threshold_px` (default: 8.0), the raw value is
   considered a spike; return the previous median instead of updating with the raw value.
4. Otherwise, return the current median.

Median is preferred over mean because it is resistant to the isolated outlier frames that
MediaPipe occasionally produces when the eye is partly occluded or caught mid-blink.
Window of 5 frames adds less than 83 ms of latency at 30 fps — imperceptible to users.

**Snap zones**

Each snap zone is an axis-aligned rectangle defined by `(cx, cy, hw, hh)` in logical
screen points. On each frame after the EMA step (but before the deadzone check in the
call to `pyautogui.moveTo`):

1. Iterate over all registered zones (O(n), n typically 0-20 for a single-monitor setup).
2. Check if `|ema_x - cx| <= hw AND |ema_y - cy| <= hh`.
3. If yes, replace the output with `(cx, cy)` — the zone center.
4. If multiple zones match (overlapping zones), use the first match in list order.

The deadzone check is applied to the snapped output, not the raw EMA, so that when the
cursor is snapped to a zone center it is genuinely stable and the deadzone does not fight
the snap.

### Performance impact

All three additions run inside the 30 fps tracking loop.

- Iris spike filter: deque append + median of 5 values = O(1) per axis. Negligible (<0.1 ms).
- Dual-speed EMA: two comparisons + one multiply-add. Negligible (<0.1 ms).
- Snap zone lookup: linear scan of zone list. At 20 zones: ~2 microseconds. At 50 zones:
  still well under 0.5 ms. Acceptable.

No blocking I/O, no background threads needed. Total added computation is well within
the existing 33 ms budget.

### Configuration

New keys to add to `config/default_config.json`:

| Key | Default | Unit | Description |
|---|---|---|---|
| `cursor_alpha_fast` | 0.35 | dimensionless (0-1) | EMA alpha used when gaze velocity exceeds threshold. Higher = more responsive during saccades. |
| `cursor_fast_velocity_threshold_px` | 80 | logical screen points | Velocity above this switches to fast-alpha EMA mode. |
| `iris_filter_window` | 5 | frames | Rolling median window size for iris coordinate smoothing. |
| `iris_spike_threshold_px` | 8.0 | camera pixels | Single-frame iris deviation beyond which the value is treated as a spike and rejected. |
| `snap_zones` | [] | list of objects | List of snap zone objects. Each: `{"cx": N, "cy": N, "hw": N, "hh": N}` in logical screen points. Default is empty (no snapping). |

Existing keys that remain but whose defaults are reviewed:

| Key | Current default | Notes |
|---|---|---|
| `smoothing_alpha` | 0.08 | Unchanged. Now used as "slow alpha" in dual-speed mode. |
| `cursor_deadzone_px` | 8 | Unchanged. Applied to snapped output. |

### External dependencies

No new pip packages required. All logic uses Python stdlib (`collections.deque`,
`statistics.median` or `numpy`) and existing project dependencies. `numpy` is already
listed in requirements.

---

## Impact on existing features

**F2 — Cursor Control (Phase 2)**
Direct overlap. This feature replaces the EMA logic in `CursorController.move()`.
The interface signature `move(screen_x, screen_y) -> tuple | None` is unchanged.
The new behavior is strictly backward-compatible: with `cursor_alpha_fast = smoothing_alpha`
and `cursor_fast_velocity_threshold_px = 0`, behavior is identical to current. The default
config produces different (better) behavior, but no existing tests assume specific pixel
positions at specific frames.
Classification: **dependency / extension**.

**F3 — Double Blink Click (Phase 3)**
`DoubleBlinkClicker` calls `pyautogui.click()` at the current cursor position, which is
set by `CursorController`. If snap zones are active, the cursor is more likely to be
precisely on a target when the user blinks, improving click accuracy. No code in the
clicker module is changed.
Classification: **safe coexistence, positive interaction**.

**F4 — Head Tilt Scroll (Phase 4)**
No interaction. Scroll uses pitch from `HeadPoseEstimator`, which is not touched by
this feature.
Classification: **safe coexistence**.

**F1 — Calibration (Phase 1)**
`CalibrationSession` calls `get_iris_positions()` and manually averages values. The iris
spike filter lives in `IrisFilter`, a separate object; the raw `get_iris_positions()`
function is unchanged. The calibration session could optionally use `IrisFilter` during
the collection phase (Phase 2 of calibration — the 30-frame collection loop) to produce
cleaner samples, but this is **out of scope for this document** to avoid scope creep.
Classification: **safe coexistence**. Optional future improvement noted.

**F5 — Configuration (Phase 5)**
New config keys must be added to `default_config.json`. This is consistent with Phase 5
requirements. The config loader (`src/utils/config.py`) uses `dict.get()` with defaults,
so existing installations without the new keys will use the code-level defaults.
Classification: **dependency — config keys must be added**.

---

## Risks & Open Questions

### Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Dual-speed EMA's fast alpha causes overshoot if threshold is too low | Medium | Medium | Default threshold (80 px) set conservatively; expose as config key for per-user tuning; acceptance criterion 3 directly tests no-overshoot |
| Snap zones are empty by default, making the feature invisible to users who do not configure them | High | Low | Feature still delivers value via iris filter and adaptive EMA without any zones configured. Document how to add zones to config. |
| Iris spike filter window of 5 frames adds ~83 ms of additional effective latency | Low | Low | At 30 fps, 5-frame median introduces at most 2-frame (66 ms) effective lag. This is acceptable given jitter reduction benefit. Can be reduced to 3 frames if user perceives lag. |
| Rolling median computation via `statistics.median` on a list of 5 is slower than numpy sort on the same data | Low | Low | Use `numpy.median()` on the existing numpy deque array; cost is negligible either way at this window size. |
| Snap zones defined in logical points become misaligned if user moves macOS windows | Medium | Medium | Document that zones are static; add note that zones must be reconfigured when screen layout changes. Dynamic zone tracking is explicitly out of scope. |
| `get_iris_positions` returns `int32` centers — integer quantization adds 0.5 px effective noise floor per axis | Medium | Low | Iris filter median does not eliminate quantization noise, but smooths it over 5 frames. Switching to float output from `cv2.minEnclosingCircle` (which returns float) would be a clean fix, but changes the public return type — flagged as open question below. |

### Open questions

1. Should `get_iris_positions()` return `float` iris coordinates (as `cv2.minEnclosingCircle`
   actually produces) instead of truncating to `int32`? This would eliminate quantization
   noise with zero algorithmic cost but changes the public return type and any downstream
   code that expects integers. Decision needed before implementation begins.

2. Should the calibration session's 30-frame collection phase (Phase 2 of calibration in
   `calibration.py`) also use `IrisFilter` to produce cleaner calibration samples? This
   would improve the accuracy of the regression model without requiring more calibration
   points. Low implementation cost but slightly changes calibration behavior — needs
   explicit user decision.

3. What is the appropriate snap zone definition for a standard macOS setup? Should the
   feature ship with a default zones file covering common macOS UI regions (menu bar strip,
   dock zone) or remain empty by default? Pre-filling zones adds immediate usability but
   makes assumptions about screen resolution and layout.

4. The velocity threshold for dual-speed EMA (80 px default) was estimated analytically.
   Does it need empirical tuning on a real MacBook before becoming a committed default?
   If the user can do a 15-minute test session, this value should be validated and
   adjusted before the feature is merged.

---

## Definition of Done

- [ ] Feature implemented per acceptance criteria (all 10 criteria satisfied)
- [ ] `IrisFilter` class implemented in `src/tracking/iris_filter.py` with unit tests
      covering: normal operation, spike rejection, window initialization from cold start
- [ ] `SnapZoneRegistry` class implemented in `src/control/snap_zones.py` with unit tests
      covering: point inside zone, point outside zone, point inside multiple overlapping
      zones (first match wins), empty zone list (returns None)
- [ ] `CursorController.move()` updated with dual-speed EMA; unit tests covering:
      slow-alpha path, fast-alpha path, alpha reversion after velocity drops, snap zone
      application, deadzone still applies to snapped output
- [ ] New config keys present in `config/default_config.json` with correct defaults
- [ ] `main.py` updated to instantiate `IrisFilter`, pass filtered iris values to
      `gaze_mapper.predict()`, and pass snap zone config to `CursorController`
- [ ] No regressions in existing functionality (full test suite passes)
- [ ] Frame processing time measured; median < 20 ms, p99 < 30 ms with 50 snap zones
- [ ] Open question 1 (float vs int32 iris coordinates) resolved and decision documented
      in this file before implementation begins
- [ ] PRODUCT.md not changed (this feature improves existing F2, no new product feature)

---

## Implementation Phases

These phases are ordered to minimize risk and allow incremental testing.

### Phase A — Iris spike filter (lowest risk, isolated module)
Create `src/tracking/iris_filter.py`. Write unit tests. Wire into `main.py` before
`gaze_mapper.predict()`. Validate that live cursor jitter decreases without affecting
responsiveness. Config keys: `iris_filter_window`, `iris_spike_threshold_px`.

### Phase B — Dual-speed adaptive EMA (core smoothing improvement)
Modify `CursorController.move()`. Add `cursor_alpha_fast` and
`cursor_fast_velocity_threshold_px` to config. Write unit tests. Validate that large
saccades reach destination in < 20 frames and that at-rest jitter remains suppressed.

### Phase C — Snap zones (optional enhancement, requires user config)
Create `src/control/snap_zones.py`. Add `snap_zones` to config (empty list default).
Integrate into `CursorController.move()` after EMA step. Write unit tests. Validate
with a manually configured test zone on a known screen location.

Phases A and B can be implemented in a single development pass. Phase C may be deferred
to a separate iteration if snap zone configuration UX is not ready.
