# SKY Yoga AI Coach — Developer README

## Table of Contents
1. [Project Overview](#1-project-overview)
2. [How the System Works](#2-how-the-system-works)
3. [Project Structure](#3-project-structure)
4. [For Contributors — Writing Your Exercise File](#4-for-contributors--writing-your-exercise-file)
5. [Watching the Video — What to Note](#5-watching-the-video--what-to-note)
6. [Rules, Reps, and Timestamps](#6-rules-reps-and-timestamps)
7. [When to Use Similarity vs Rule-Based Logic](#7-when-to-use-similarity-vs-rule-based-logic)
8. [Integration Guide — For Project Lead](#8-integration-guide--for-project-lead)
9. [Common Mistakes](#9-common-mistakes)
10. [Quick Reference](#10-quick-reference)

---

## 1. Project Overview

This is an AI yoga coach that plays a 1-hour reference video and tracks the user's pose in real time using MediaPipe. The system:

- Plays the mentor's video
- Detects the user's body via webcam
- Compares the user's pose against what the mentor is doing right now
- Gives real-time coaching feedback on screen
- Pauses the video if the user is doing it wrong
- Counts reps automatically
- Resumes the video when the user corrects their form

The full video has 9 exercise sections. Each section is one developer's responsibility.

---

## 2. How the System Works

```
Video plays from URL
        ↓
main.py reads current video timestamp every frame
        ↓
Looks up which exercise section is active (EXERCISE_TIMELINE)
        ↓
Loads that exercise's WorkoutController
        ↓
WorkoutController checks video timestamp against its own _PHASES list
        ↓
Determines coach state:
  WATCH   → mentor demonstrating → video plays freely, no checking
  PREPARE → 3 seconds warning    → "Get ready in 3... 2... 1..."
  ACTIVE  → user performs        → full pose checking + rep counting
  ZOOM    → close-up shot        → skip all checks, video plays freely
        ↓
ACTIVE state:
  check_pose()  → rule-based feedback → may pause video (red skeleton)
  detect_rep()  → counts reps every frame
        ↓
UI shows: phase name, coach message, rep counter (done/target)
```

### Video Control Logic

```
check_pose returns (True,  "message") → error → after 10 bad frames → video PAUSES
check_pose returns (False, "message") → tip   → video PLAYS
check_pose returns (False, None)      → good  → video PLAYS
```

---

## 3. Project Structure

```
yoga_trainer/
│
├── main.py                        ← Orchestrator. DO NOT TOUCH.
├── CONTRIBUTING.md                ← Developer guide
├── README.md                      ← This file
├── requirements.txt
├── pose_landmarker_heavy.task     ← MediaPipe model file
│
├── core/                          ← Engine. DO NOT TOUCH.
│   ├── base_controller.py         ← Coach state machine base class
│   ├── breath_detector.py         ← Detects breathing cycles
│   ├── camera.py                  ← Webcam wrapper
│   ├── exercise_registry.py       ← Auto-loads all exercises/ files
│   ├── motion_tracker.py          ← Detects movement + rotation cycles
│   ├── pose_engine.py             ← MediaPipe wrapper + skeleton drawing
│   ├── reference_analyzer.py      ← Extracts pose from video frame
│   ├── ui_renderer.py             ← All screen drawing
│   ├── utils.py                   ← calculate_angle(), dist(), lm_px()
│   └── video_controller.py        ← Video playback (URL + local)
│
└── exercises/                     ← ONE FILE PER DEVELOPER
    ├── _TEMPLATE.py               ← Copy this to start your exercise
    ├── hand_exercise.py           ← Dev 1 (done — use as reference)
    ├── leg_exercise.py            ← Dev 2
    ├── neuro_exercise.py          ← Dev 3
    ├── eye_exercise.py            ← Dev 4
    ├── kapalabhati_exercise.py    ← Dev 5
    ├── makarasana_exercise.py     ← Dev 6
    ├── massage_exercise.py        ← Dev 7
    ├── acupressure_exercise.py    ← Dev 8
    └── relaxation_exercise.py    ← Dev 9
```

---

## 4. For Contributors — Writing Your Exercise File

### The only 3 things you write

```
1. _PHASES list        → timestamps + metadata for each sub-exercise
2. check_pose()        → rule-based pose feedback
3. detect_rep()        → rep counting
```

Everything else is handled by the system automatically.

### Minimal working example

```python
from core.base_controller import BaseController
from core.utils import calculate_angle, dist, lm_px

EXERCISE_KEY = "leg"   # must match main.py EXERCISE_TIMELINE

_PHASES = [
    {
        "id":        "leg_raise",
        "name":      "Leg Raise",
        "start":     550,   # video seconds: mentor starts
        "active":    562,   # video seconds: user starts
        "end":       640,   # video seconds: phase ends
        "target":    5,     # rep count
        "watch_msg": "Watch — raise leg straight, keep balance",
        "check_landmarks": [23, 24, 25, 26, 27, 28],
    },
]


class WorkoutController(BaseController):

    def phases(self) -> list:
        return _PHASES

    def check_pose(self, user_lm, ref_lm, w, h, phase) -> tuple:
        lh = lm_px(user_lm, 23, w, h)   # left hip
        lk = lm_px(user_lm, 25, w, h)   # left knee
        la = lm_px(user_lm, 27, w, h)   # left ankle
        angle = calculate_angle(lh, lk, la)
        if angle < 160:
            return True, "Keep your leg straight"
        return False, None

    def detect_rep(self, user_lm, w, h):
        raised = user_lm[27].y < user_lm[23].y   # ankle above hip
        if raised and self.phase == "DOWN":
            self.phase = "UP"
        if not raised and self.phase == "UP":
            self.phase = "DOWN"
            self.rep_count += 1
```

---

## 5. Watching the Video — What to Note

**This is the most important step. Do not skip it.**

Before writing a single line of code, watch your entire video section carefully and write down the following for each sub-exercise:

### Timestamps to record

| Field | What it means | How to find it |
|-------|--------------|----------------|
| `start` | When the mentor begins explaining/demonstrating | First frame the mentor shows the movement |
| `active` | When the user should START doing it | Usually 5–15 seconds after mentor starts, after they finish explaining |
| `end` | When this sub-exercise ends | Last frame of this movement before mentor transitions to next |

### Movement details to record

- **What body parts move?** → determines which landmarks to check
- **What is the starting position?** → needed for reset logic
- **What does correct form look like?** → write as rules
- **What are common mistakes?** → write as error messages
- **How many repetitions does the mentor count?** → set as `target`
- **Is there a close-up / zoom shot?** → set `"zoom": True` for that segment
- **Is it a hold or a dynamic movement?** → determines rep counting approach

### Example notes for leg exercises

```
9:10 – 9:20  : Mentor explains leg exercise, standing position, talking
9:20 – 9:35  : Mentor demonstrates leg raise — left leg, 5 times
9:35 – 9:37  : Short pause, mentor changes position
9:37 – 9:50  : Right leg raise, 5 times
9:50 – 10:00 : Both legs, knee bend, 5 times
10:00 – 10:05: Close-up of feet position (ZOOM — set zoom: True)
10:05 – 10:28: Heel raise, 5 times
```

This translates directly to your `_PHASES` list.

---

## 6. Rules, Reps, and Timestamps

### How to write rules (check_pose)

Rules come directly from observing the mentor. For each sub-exercise ask:

**What must be true when the pose is correct?**

Write these as angle checks, distance checks, or position checks.
If any rule fails → return `(True, "correction message")`.
If all rules pass → return `(False, None)`.

### Rule types

**Angle rule** — joint must be at a certain angle:
```python
# Knee should be straight during leg raise (~175-180 degrees)
lh  = lm_px(lm, 23, w, h)
lk  = lm_px(lm, 25, w, h)
la  = lm_px(lm, 27, w, h)
angle = calculate_angle(lh, lk, la)
if angle < 170:
    return True, "Keep your leg straight"
```

**Distance rule** — body parts must be certain distance apart:
```python
# Feet must be shoulder-width apart
ls  = lm_px(lm, 11, w, h)
rs  = lm_px(lm, 12, w, h)
la  = lm_px(lm, 27, w, h)
ra  = lm_px(lm, 28, w, h)
shoulder_w = dist(ls, rs) or 1
feet_d     = dist(la, ra)
if feet_d / shoulder_w < 0.8:
    return True, "Place feet shoulder-width apart"
```

**Position rule** — body part must be above/below another:
```python
# Wrist must be above shoulder during arm raise
# Normalized coords: smaller y = higher on screen
if user_lm[15].y > user_lm[11].y:
    return True, "Raise your arm higher"
```

**Stability rule** — body part must NOT be moving:
```python
# Head must stay still during eye exercises
# Use MotionTracker from core.motion_tracker
if self._head_tracker.is_moving():
    return True, "Keep your head still"
```

**Movement rule** — body part MUST be moving:
```python
# During rotation, wrist must be moving
if not self._wrist_tracker.is_moving():
    return True, "Rotate your wrist in circles"
```

### How to write rep counting (detect_rep)

Rep counting strategy depends on the movement type:

**Type 1 — Up/down movement** (leg raise, arm raise):
```python
# Rep = goes up then comes back down
raised = user_lm[27].y < user_lm[23].y  # ankle above hip
if raised and self.phase == "DOWN":
    self.phase = "UP"
if not raised and self.phase == "UP":
    self.phase = "DOWN"
    self.rep_count += 1
```

**Type 2 — Wide/close movement** (T-pose, spread arms):
```python
# Rep = arms spread wide then come back together
lwr = lm_px(lm, 15, w, h); rwr = lm_px(lm, 16, w, h)
wide = dist(lwr, rwr) > w * 0.45
if wide and self.phase == "CLOSE":
    self.phase = "WIDE"
if not wide and self.phase == "WIDE":
    self.phase = "CLOSE"
    self.rep_count += 1
```

**Type 3 — Rotation** (wrist circles, knee circles):
```python
# Use MotionTracker to count rotation cycles
from core.motion_tracker import MotionTracker

# In __init__:
self._tracker = MotionTracker(window_sec=1.5, min_arc_px=12)
self._last_cycles = 0

# In detect_rep:
self._tracker.update(user_lm[16].x * w, user_lm[16].y * h)
c = self._tracker.cycle_count()
new = c - self._last_cycles
if new > 0:
    self.rep_count += new
    self._last_cycles = c
```

**Type 4 — Breath-based hold** (held poses with breath counting):
```python
# Use BreathDetector from core.breath_detector
from core.breath_detector import BreathDetector

# In __init__:
self._breath = BreathDetector(min_breath_sec=2.0)

# In check_pose (update tracker):
self._breath.update((user_lm[11].y + user_lm[12].y) / 2)

# In detect_rep:
self._hold_breaths += self._breath.new_breaths()
if self._hold_breaths >= 4:   # 4 breaths = 1 hold complete
    self.rep_count += 1
    self._hold_breaths = 0
```

**Type 5 — Side-to-side** (torso rotation, neck roll):
```python
# Rep = rotate right then rotate left = 1 rep
# Use shoulder width narrowing as rotation signal
ls_x = user_lm[11].x * w
rs_x = user_lm[12].x * w
sw   = abs(ls_x - rs_x)
if self._baseline is None:
    self._baseline = sw; return
rotated = sw < self._baseline * 0.82  # shoulder width narrows when body rotates
if rotated and self.phase == "CENTER":
    self.phase = "ROTATED"
if not rotated and self.phase == "ROTATED":
    self.phase = "CENTER"
    self.rep_count += 1
```

### Rep counts from the mentor (from the video)

Watch carefully — the mentor either verbally counts or the video has text overlays. Here are the confirmed rep counts for each exercise:

| Exercise section | Sub-exercise | Reps |
|-----------------|--------------|------|
| Hand | Raise arms overhead | 3 |
| Hand | T-pose breathe | 5 |
| Hand | Right hand CW rotation | 5 |
| Hand | Left hand CW rotation | 5 |
| Hand | Right hand CCW rotation | 5 |
| Hand | Left hand CCW rotation | 5 |
| Hand | Both hands CW rotation | 5 |
| Hand | Both hands CCW rotation | 5 |
| Hand | Arm swing (foot forward) | 10 |
| Hand | Upper body rotation | 5 |
| Hand | Knee rotation | 9 (3 CW + 3 CCW + 3 CW) |
| Leg | *(watch video and note)* | — |
| Others | *(watch video and note)* | — |

> **Rule:** When in doubt about rep count — watch the video, count what the mentor does, use that number as `target`.

---

## 7. When to Use Similarity vs Rule-Based Logic

This is the most important design decision. Use the wrong approach and the system breaks.

### Rule-Based Logic

**Use for all exercises by default.**

Rule-based logic checks specific joint angles, distances, and positions.
It is reliable, fast, and doesn't depend on what the mentor is doing right now.

```python
# Rule-based: check the user's own body only
angle = calculate_angle(hip, knee, ankle)
if angle < 90:
    return True, "Bend your knee more"
```

✅ Use rule-based when:
- The movement is dynamic (user moving)
- The video has zoom-in shots during the movement
- You know exactly what the correct pose looks like (specific angles/positions)
- The exercise has a clear start/end position

❌ Do NOT use rule-based as the only check when:
- The correct form is subtle and hard to describe with angles alone
- The exercise has many simultaneous constraints

---

### Similarity (Pose Matching)

**Use only for static held poses where the user must match the mentor exactly.**

Similarity compares the user's full body shape against the reference video frame using cosine similarity. It returns a score from 0.0 (completely different) to 1.0 (identical).

```python
# Similarity is handled automatically by base_controller
# Set USE_SIMILARITY = True in your WorkoutController class:

class WorkoutController(BaseController):
    USE_SIMILARITY = True   # ← enables similarity checking
    SIMILARITY_THRESHOLD = 0.84  # ← how strict (0.0-1.0)
```

✅ Use similarity when:
- The pose is **static** and **held** (not moving)
- Full body is visible in the reference video during that phase
- The rule-based checks alone are not enough to verify the full posture
- Example: Makarasana (lying pose), Relaxation pose, static standing balance poses

❌ Do NOT use similarity when:
- The exercise is **dynamic** (arms rotating, legs moving)
- The video shows a **close-up** (mentor's feet not visible, etc.)
- The mentor is in a **different position** than the user at the same moment
- The reference video **zooms in** during the movement

**CRITICAL: Never use similarity during movement phases.**
If the video shows mentor with arms down but user has arms up (they're mid-movement), similarity will always fail and say "follow the mentor" even though the user is doing it correctly.

### Summary Table

| Exercise type | Use similarity? | Use rule-based? |
|--------------|----------------|----------------|
| Dynamic movement (rotations, raises) | ❌ No | ✅ Yes |
| Static held pose (Makarasana, Relaxation) | ✅ Yes | ✅ Yes |
| Zoom-in shot | ❌ No | ❌ No (skip all) |
| Breathing exercise (Kapalabhati) | ❌ No | ✅ Yes + breath detector |
| Eye exercises | ❌ No | ✅ Yes (head still + eye movement) |
| Massage / Acupressure | ❌ No | ✅ Yes (hand position) |

---

## 8. Integration Guide — For Project Lead

When a developer says their exercise file is ready, here is the exact process to integrate it.

### Step 1 — Receive their file

They send you `exercises/leg_exercise.py`.
Place it in the `exercises/` folder. That's all.

The exercise registry (`core/exercise_registry.py`) automatically scans the `exercises/` folder on startup and loads every file that has `EXERCISE_KEY` and `WorkoutController` defined.

**No import statements needed. No registration needed. It just works.**

### Step 2 — Add to EXERCISE_TIMELINE in main.py

Open `main.py` and find `EXERCISE_TIMELINE`. Add their exercise key and start timestamp:

```python
EXERCISE_TIMELINE = [
    {"key": "hand",        "start":   67},   # already done
    {"key": "leg",         "start":  727},   # ← add this line
    {"key": "neuro",       "start": 1037},   # ← add this line
    ...
]
```

`start` = the video timestamp (in seconds) when their exercise section begins in the full 1-hour video.

> **Note:** The exercise file's internal `_PHASES` timestamps are relative to the compressed test clip. For the full 1-hour video, the developer must add the offset (e.g. +727 seconds for leg exercises) to all their phase timestamps, OR you define an offset in `EXERCISE_TIMELINE` and the base controller applies it automatically.

### Step 3 — Verify it loads

Run the project and check the console output at startup:

```
[Registry] Loaded: 'hand'  ← hand_exercise.py
[Registry] Loaded: 'leg'   ← leg_exercise.py   ← should appear
```

If it does not appear, the file has a syntax error or is missing `EXERCISE_KEY` / `WorkoutController`.

### Step 4 — Test their section

Seek the video to their section timestamp and watch the behaviour:

- Does WATCH state show correctly before they start?
- Does ACTIVE state engage at the right time?
- Does check_pose give sensible feedback?
- Does rep counter increment correctly?
- Does the video pause when form is wrong and resume when corrected?

### Step 5 — Checklist before merging

- [ ] `EXERCISE_KEY` matches the key in `EXERCISE_TIMELINE`
- [ ] All `_PHASES` have `id`, `name`, `start`, `active`, `end`, `target`, `watch_msg`
- [ ] `check_pose` returns `(bool, str | None)` tuple — never a plain string
- [ ] `detect_rep` uses `self.rep_count += 1` — not any other variable
- [ ] Zoom-in segments have `"zoom": True`
- [ ] No imports from outside `core/` except standard library

---

## 9. Common Mistakes

### check_pose returns wrong type
```python
# WRONG — returns a string, not a tuple
return "Keep your leg straight"

# CORRECT
return True, "Keep your leg straight"
```

### Using pixel offset instead of normalized coords
```python
# WRONG — fragile, breaks at different camera distances
if wrist_y > hip_y - 20:   # 20 pixels is meaningless

# CORRECT — normalized, works at any distance
if user_lm[15].y > user_lm[23].y:   # wrist below hip
```

### Similarity used during movement
```python
# WRONG — causes "follow the mentor" during dynamic movement
class WorkoutController(BaseController):
    USE_SIMILARITY = True   # ← during a rotation exercise

# CORRECT — keep False for all movement phases
class WorkoutController(BaseController):
    USE_SIMILARITY = False   # default, leave it
```

### Timestamps not accounting for video offset
```python
# If testing with the compressed 10-min clip:
"start": 22,   "active": 30   # timestamps in clip = OK for local test

# But for full 1-hour video, add the offset to every timestamp:
"start": 89,   "active": 97   # 22 + 67 = 89  (hand exercises offset)
```

### rep_count increments multiple times per rep
```python
# WRONG — increments every frame when leg is raised
if ankle_y < hip_y:
    self.rep_count += 1   # fires ~30 times per second!

# CORRECT — state machine, only increments on transition
if raised and self.phase == "DOWN":
    self.phase = "UP"
if not raised and self.phase == "UP":
    self.phase = "DOWN"
    self.rep_count += 1   # fires exactly once per rep
```

---

## 10. Quick Reference

### Landmark indices

```
HEAD:    0=nose  7=L.ear   8=R.ear
ARMS:   11=L.shoulder  12=R.shoulder  13=L.elbow  14=R.elbow
        15=L.wrist     16=R.wrist
HANDS:  17=L.pinky  19=L.index  21=L.thumb
        18=R.pinky  20=R.index  22=R.thumb
LEGS:   23=L.hip   24=R.hip   25=L.knee  26=R.knee
        27=L.ankle 28=R.ankle 29=L.heel  30=R.heel
        31=L.foot  32=R.foot
```

### Helper functions

```python
lm_px(lm, idx, w, h)           # → (x_px, y_px)
calculate_angle(a, b, c)        # → degrees at joint b
dist(p1, p2)                    # → pixel distance
```

### Normalized position checks (use lm[idx].x / lm[idx].y)

```python
# Smaller y = higher on screen
arm_raised    = user_lm[15].y < user_lm[11].y   # wrist above shoulder
leg_raised    = user_lm[27].y < user_lm[23].y   # ankle above hip
hands_joined  = dist(lm_px(lm,15,w,h), lm_px(lm,16,w,h)) < w * 0.08
feet_together = dist(lm_px(lm,27,w,h), lm_px(lm,28,w,h)) < w * 0.10
```

### check_pose return values

```python
return True,  "message"   # wrong pose → pause video → red skeleton
return False, "message"   # correct pose, show tip → play video → green
return False, None        # perfect → play video → green → "Good form"
```

### Exercise assignment

| Key | File | Video timestamp |
|-----|------|----------------|
| `hand` | `hand_exercise.py` ✅ | 1:07 |
| `leg` | `leg_exercise.py` | 12:07 |
| `neuro` | `neuro_exercise.py` | 17:10 |
| `eye` | `eye_exercise.py` | 23:50 |
| `kapalabhati` | `kapalabhati_exercise.py` | 29:31 |
| `makarasana` | `makarasana_exercise.py` | 31:17 |
| `massage` | `massage_exercise.py` | 41:57 |
| `acupressure` | `acupressure_exercise.py` | 44:49 |
| `relaxation` | `relaxation_exercise.py` | 50:33 |

---

*Look at `exercises/hand_exercise.py` for a complete working example with all patterns.*