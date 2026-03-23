# SKY Yoga AI Coach — Setup & Developer Guide

An AI-powered yoga coach that uses MediaPipe to track user poses in real-time and provides feedback against a reference video.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Project Overview](#project-overview)
3. [How the System Works](#how-the-system-works)
4. [Project Structure](#project-structure)
5. [For Developers — Adding New Exercises](#for-developers--adding-new-exercises)
6. [Creating Your Exercise File](#creating-your-exercise-file)
7. [Phase Timestamps](#phase-timestamps)
8. [Pose Checking & Rep Counting](#pose-checking--rep-counting)
9. [Testing Your Exercise](#testing-your-exercise)
10. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Requirements
- Python 3.8+
- Webcam
- Internet connection (for video streaming)

### Installation & Running

```bash
# Clone or navigate to the project
cd yoga_trainer

# Create virtual environment (optional but recommended)
python -m venv venv
source venv/Scripts/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

### Controls
- **SPACE** — Pause / resume reference video
- **Q** — Quit application

The app displays a 50/50 split screen:
- **Left** — Your camera feed with skeleton tracking and feedback
- **Right** — Reference video from the mentor

---

## Project Overview

This system is designed for yoga/exercise training with real-time pose feedback:

- **Real-time pose detection** using MediaPipe Pose Landmarker
- **Video-based instruction** with reference mentor video
- **Automatic rep counting** detecting exercise completion
- **Adaptive feedback** that pauses video on form errors
- **Multi-exercise support** with flexible phase-based structure

---

## How the System Works

### Video Flow

```
Reference video plays from timestamp
         ↓
main.py detects which exercise is active by timestamp
         ↓
Loads appropriate WorkoutController class
         ↓
Controller's _PHASES list determines current sub-exercise
         ↓
Coach state machine transitions: WATCH → PREPARE → ACTIVE → HOLD
         ↓
For ACTIVE state:
  check_pose()  → validates form (may pause video on error)
  detect_rep()  → counts completed reps
         ↓
Skeleton rendering & feedback messages shown to user
```

### Coach State Machine

| State | Meaning | Behavior |
|-------|---------|----------|
| **WATCH** | Mentor is demonstrating | Video plays freely, no evaluation |
| **PREPARE** | 3-second warning | "Get ready in 3... 2... 1..." |
| **ACTIVE** | User is performing | Full pose checking + rep counting |
| **ZOOM** | Close-up/detail shot | Video plays, no evaluation |
| **HOLD** | Form error occurred | Video pauses, 10-second cooldown |

### Error Handling

- **Form error** — Skeleton turns RED, message appears
- **After 12 consecutive bad frames** — Video pauses automatically
- **After 10 seconds in HOLD** — Video resumes regardless of form

---

## Project Structure

```
yoga_trainer/
│
├── main.py                        ← Application entry point
├── requirements.txt               ← Python dependencies
├── pose_landmarker_heavy.task     ← MediaPipe model
│
├── core/                          ← Engine (do not modify)
│   ├── base_controller.py         ← Coach state machine
│   ├── pose_engine.py             ← MediaPipe wrapper
│   ├── ui_render.py               ← Screen rendering
│   ├── video_controller.py        ← Video playback
│   ├── motion_tracker.py          ← Movement detection
│   ├── camera.py                  ← Webcam wrapper
│   ├── utils.py                   ← Helper functions
│   └── exercise_registry.py       ← Auto-loads exercises
│
└── exercises/                     ← Exercise implementations
    ├── _TEMPLATE.PY               ← Copy this for new exercises
    ├── hand_exercise.py           ← Example (completed)
    ├── leg_exercise.py
    ├── neuro_exercise.py
    └── [more exercises...]
```

---

## For Developers — Adding New Exercises

### Overview

Each exercise is a Python file in the `exercises/` folder that:
1. Defines **phase timestamps** from the video
2. Implements **form checking** (rule-based pose validation)
3. Implements **rep detection** (counts completed repetitions)

The system **automatically discovers** new exercise files — no registration needed.

### Step-by-Step Guide

#### Step 1: Watch Your Video Section

Before writing code, watch your exercise section (usually 2-5 minutes) and note:

- **Timestamps** — when mentor starts, when user starts, when it ends
- **Body parts** — which joints/landmarks matter
- **Correct form** — what does good posture look like?
- **Common mistakes** — what should trigger a warning?
- **Rep count** — how many reps does mentor demonstrate?

#### Step 2: Create Your Exercise File

```bash
# Copy the template
cp exercises/_TEMPLATE.PY exercises/my_exercise.py
```

Edit and set:
```python
EXERCISE_KEY = "my_exercise"  # Must match main.py EXERCISE_TIMELINE
```

Update `EXERCISE_TIMELINE` in `main.py`:
```python
EXERCISE_TIMELINE = [
    {"key": "hand",        "start": 14},
    {"key": "my_exercise", "start": 500},  # Add this line
    # ...
]
```

---

## Creating Your Exercise File

#### Step 3: Define Phases

List all sub-movements in `_PHASES`:

```python
_PHASES = [
    {
        "id":               "p1_raise",
        "name":             "Raise Arms",
        "start":            500,      # Video timestamp: mentor starts
        "active":           510,      # Video timestamp: user starts
        "end":              550,      # Video timestamp: phase ends
        "target":           5,        # Rep count target (0 = no counting)
        "watch_msg":        "Raise both arms overhead",
        "check_landmarks":  [11, 12, 15, 16],  # Landmark indices needed
    },
    {
        "id":               "p2_hold",
        "name":             "Hold Position",
        "start":            550,
        "active":           560,
        "end":              600,
        "target":           3,
        "watch_msg":        "Hold position steady",
        "check_landmarks":  [11, 12, 15, 16],
    },
]
```

#### Step 4: Implement Form Checking

The `check_pose()` method provides real-time feedback:

```python
def check_pose(self, user_lm, w: int, h: int, phase: dict) -> tuple:
    """
    Returns: (is_error: bool, message: str | None)
    
    (False, None)          → Good form, no message
    (False, "message")     → Tip/guidance, skeleton GREEN
    (True,  "message")     → Form error, skeleton RED, pauses after 12 frames
    """
    pid = phase["id"]
    
    if pid == "p1_raise":
        return self._check_raise(user_lm, w, h)
    
    return (False, None)

def _check_raise(self, lm, w, h):
    # Always check visibility FIRST
    if not visible(lm, 11, 12, 15, 16):
        return (False, None)
    
    # Get pixel coordinates
    left_wrist = px(lm, 15, w, h)
    right_wrist = px(lm, 16, w, h)
    nose = px(lm, 0, w, h)
    
    # Check if wrists are above nose (raised)
    if lm[15].y > nose[1] or lm[16].y > nose[1]:
        return (False, "Raise your arms higher")
    
    # Check if palms are joined
    gap = dist(left_wrist, right_wrist)
    sw = shoulder_width(lm, w, h)
    if gap > sw * 0.3:
        return (False, "Join your palms closer together")
    
    return (False, None)  # Good form
```

#### Step 5: Implement Rep Counting

The `detect_rep()` method increments `self.rep_count` when a rep is completed:

```python
def detect_rep(self, user_lm, w: int, h: int):
    """
    Called every ACTIVE frame. Must use self._active_phase, not _get_phase().
    """
    p = self._active_phase
    if not p:
        return
    
    pid = p["id"]
    
    if pid == "p1_raise":
        self._rep_raise(user_lm, w, h)

def _rep_raise(self, lm, w, h):
    """
    State machine example:
    REST → UP (arms raised) → DOWN (arms lowered) → counted as 1 rep
    """
    if not visible(lm, 15, 16, 23, 24):
        return
    
    # Check if wrists are above hips (UP position)
    is_up = lm[15].y < lm[23].y and lm[16].y < lm[23].y
    
    if self._raise_state == "REST" and is_up:
        self._raise_state = "UP"
    
    elif self._raise_state == "UP" and not is_up:
        self._raise_state = "REST"
        self.rep_count += 1  # Increment rep count
```

---

## Phase Timestamps

### How to Find Timestamps

Use a video player (VLC, YouTube) to identify exact timestamps:

```
start  : First frame mentor shows the movement
         Example: "Okay, now raise your arms" → 14:23 (video time)

active : Mentor finishes explaining, user should start performing
         Example: 3 seconds after "start" for PREPARING phase
         Usually: start + 10 seconds is a safe default

end    : Last frame of this phase / first frame of next phase
         Must be: end < next_phase.start (or equal if adjacent)
```

### Example Timeline

```
Video: 10:00-10:20  → Mentor explains arm raise (start=600, active=612)
Video: 10:20-10:45  → Mentor demonstrates 5 reps (end=645)
Video: 10:45-11:00  → Mentor rests, transitions (start=645 for next phase)
```

Convert to seconds:
- 10:00 = 600 seconds
- 10:20 = 620 seconds
- 10:45 = 645 seconds

---

## Pose Checking & Rep Counting

### Landmark Reference

MediaPipe provides 33 landmarks. Main ones:

```
0   Nose          11  L Shoulder   12  R Shoulder
13  L Elbow       14  R Elbow      15  L Wrist      16  R Wrist
23  L Hip         24  R Hip        25  L Knee       26  R Knee
27  L Ankle       28  R Ankle
```

**Coordinate system (0.0 to 1.0):**
- x: 0=left, 1=right
- y: 0=top, 1=bottom (YES, inverted!)

### Utility Functions

```python
from core.utils import visible, angle, dist, px, shoulder_width

# Check if landmarks are visible (confidence threshold)
if not visible(lm, 11, 12, 15, 16):
    return (False, None)

# Convert normalized coords to pixel coords
pixel_pos = px(lm, 15, w, h)  # Returns (x, y) in pixels

# Calculate distance between two landmarks
d = dist(px(lm, 15, w, h), px(lm, 16, w, h))

# Calculate angle at joint (point b is the vertex)
a = angle(point_a, point_b, point_c)  # Returns degrees

# Get shoulder width (for normalizing distances)
sw = shoulder_width(lm, w, h)
```

### Best Practices

✅ **DO:**
- Check `visible()` before accessing landmarks
- Normalize distances by `shoulder_width()`
- Use state machines for multi-frame decisions
- Increment rep count additively: `self.rep_count += 1`

❌ **DON'T:**
- Hardcode pixel distances (screen-size dependent)
- Use `self._get_phase()` in `detect_rep()` (use `self._active_phase`)
- Add your own debouncing (base_controller handles 12-frame threshold)
- Reset `self.rep_count` (system handles it)

---

## Testing Your Exercise

### Manual Testing

```bash
# Run with your exercise active
python main.py

# Controls:
# - SPACE to pause video (useful for frame-by-frame checking)
# - Q to quit
```

### Debug Checklist

1. **Verify timestamps**
   - Is "active" time in the ACTIVE coaching phase?
   - Do phases match what's showing on screen?

2. **Check visibility**
   - Are the landmarks you need visible in your camera feed?
   - Try moving closer/farther from camera

3. **Test rep counting**
   - Does counter increment at the right moment?
   - Should counter = 0 at start or 1 after first complete rep?

4. **Verify feedback messages**
   - Do error messages appear when forms are wrong?
   - Are messages clear and actionable?

### Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Landmarks not visible | Body too far/off-screen | Get in front of camera |
| Rep counter stuck at 0 | Wrong state machine logic | Add print() statements to debug |
| Video pauses unexpectedly | form errors detected | Check `check_pose()` logic |
| "Wrong pose" during correct form | Threshold too strict | Relax angle/distance checks |

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'cv2'"
```bash
pip install -r requirements.txt
```

### "pose_landmarker_heavy.task not found"
The model file must be in the project root. Download from MediaPipe if missing:
```bash
# Check if it exists
ls pose_landmarker_heavy.task

# If not, place the file in project root
```

### Video won't play
- Ensure internet connection (if using URL)
- Check `VIDEO_SOURCE` in `main.py`
- Verify video file exists (if local file)

### Skeleton not showing
- Ensure webcam is accessible
- Check camera permissions
- Try different lighting
- Move body fully into frame

### Exercise not loading
- Verify `EXERCISE_KEY` matches `main.py` `EXERCISE_TIMELINE`
- Check for Python syntax errors: `python -m py_compile exercises/my_exercise.py`
- Restart application to reload exercise registry

---

## Reference

### Full Exercise Template Structure

```python
import time
from core.base_controller import BaseController
from core.utils import angle, dist, px, visible, shoulder_width
from core.motion_tracker import MotionTracker

EXERCISE_KEY = "my_exercise"

# Timing constants
HOLD_SEC = 10.0
REST_SEC = 4.0

_PHASES = [
    {
        "id": "p1_name",
        "name": "Display Name",
        "start": 100,
        "active": 110,
        "end": 150,
        "target": 5,
        "watch_msg": "Watch the mentor...",
        "check_landmarks": [11, 12, 15, 16],
    },
]

class WorkoutController(BaseController):
    def __init__(self):
        super().__init__()
        self._state = "REST"

    def phases(self) -> list:
        return _PHASES

    def on_phase_change(self, phase: dict):
        self._state = "REST"

    def check_pose(self, user_lm, w: int, h: int, phase: dict) -> tuple:
        if not visible(user_lm, 11, 12, 15, 16):
            return (False, None)
        # Your form checking logic here
        return (False, None)

    def detect_rep(self, user_lm, w: int, h: int):
        p = self._active_phase
        if not p:
            return
        # Your rep counting logic here
        pass
```

---

## Support

For issues or questions:
1. Check this README
2. Review `exercises/hand_exercise.py` for a working example
3. Check error messages in terminal output
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
| `leg` | `leg_exercise.py` | 11:07 |
| `neuro` | `neuro_exercise.py` | 17:10 |
| `eye` | `eye_exercise.py` | 23:50 |
| `kapalabhati` | `kapalabhati_exercise.py` | 29:31 |
| `makarasana` | `makarasana_exercise.py` | 31:17 |
| `massage` | `massage_exercise.py` | 41:57 |
| `acupressure` | `acupressure_exercise.py` | 44:49 |
| `relaxation` | `relaxation_exercise.py` | 50:33 |

---

*Look at `exercises/hand_exercise.py` for a complete working example with all patterns.*