"""
exercises/_TEMPLATE.PY — Complete Template for New SKY Yoga Exercises

QUICK START: Steps 1-8 to create a new exercise
═════════════════════════════════════════════════════════════════════════

Step 1: Copy this file to your exercise
  $ cp exercises/_TEMPLATE.PY exercises/my_exercise.py

Step 2: Change EXERCISE_KEY at the top
  Set EXERCISE_KEY = "my_exercise" to match main.py EXERCISE_TIMELINE

Step 3: Watch your video section
  Note timestamps and rep counts before you code

Step 4: Fill _PHASES list with timestamps and metadata

Step 5: Implement check_pose() for form validation
  Returns (is_error: bool, message: str | None)

Step 6: Implement detect_rep() for rep counting
  Increment self.rep_count += 1 when rep is completed

Step 7 (Optional): Override on_phase_change() to reset state

Step 8: Restart application
  exercise_registry.py auto-discovers all exercises/*.py files
  No registration needed!

═════════════════════════════════════════════════════════════════════════

CRITICAL RULES — DO NOT SKIP
═════════════════════════════════════════════════════════════════════════

check_pose() MUST:
  ✓ Call visible() FIRST before accessing landmarks
  ✓ Normalize distances by shoulder_width()
  ✓ Use angle() from core.utils
  ✓ Always return (bool, str | None) tuple
  ✗ Never add custom debouncing
  ✗ Never use similarity scoring

detect_rep() MUST:
  ✓ Use self._active_phase (NOT self._get_phase)
  ✓ Increment: self.rep_count += 1 (never assign)
  ✗ Never reset self.rep_count (base_controller handles it)

on_phase_change() MUST:
  ✓ Reset all motion trackers (.reset())
  ✓ Reset all state machines
  ✗ Never reset self.rep_count

═════════════════════════════════════════════════════════════════════════
"""

import time
from core.base_controller import BaseController
from core.utils import angle, dist, px, visible, shoulder_width
from core.motion_tracker import MotionTracker


# EXERCISE CONFIGURATION
# ═════════════════════════════════════════════════════════════════════════

EXERCISE_KEY = "example"  # Required: match key in main.py EXERCISE_TIMELINE


# CONSTANTS
# ═════════════════════════════════════════════════════════════════════════

# For hold-based exercises
HOLD_TARGET_SEC = 10.0
REST_SEC = 4.0

# For position-based thresholds (normalized by shoulder width)
WRIST_JOIN_RATIO = 0.25
ARM_SPREAD_RATIO = 1.50


# PHASES DEFINITION
# ═════════════════════════════════════════════════════════════════════════

_PHASES = [
    {
        "id": "p1_example_hold",
        "name": "Arms Raised Hold",
        "start": 0,         # Video second: mentor begins
        "active": 10,       # Video second: user starts
        "end": 60,          # Video second: phase ends
        "target": 3,        # Reps required (0 = observation only)
        "watch_msg": "Raise both arms overhead, join palms, hold 4 breaths",
        "check_landmarks": [11, 12, 15, 16, 23, 24],
    },
    {
        "id": "p2_rotation",
        "name": "Wrist Rotation",
        "start": 60,
        "active": 70,
        "end": 100,
        "target": 5,
        "side": "right",   # "right" | "left" | "both"
        "watch_msg": "Extend arm down, rotate wrist in full circles",
        "check_landmarks": [12, 14, 16, 24],
    },
    {
        "id": "p3_zoom",
        "name": "Watch Detail",
        "start": 100,
        "active": 100,
        "end": 115,
        "target": 0,
        "zoom": True,      # Skip all evaluation
        "watch_msg": "Watch closely",
        "check_landmarks": [],
    },
]


# WORKOUT CONTROLLER
# ═════════════════════════════════════════════════════════════════════════

class WorkoutController(BaseController):
    """
    Main controller for this exercise.
    Implement check_pose(), detect_rep(), and optionally on_phase_change().
    """

    def __init__(self):
        super().__init__()
        self._tracker_r = MotionTracker(window_sec=1.5, min_arc_px=12)
        self._tracker_l = MotionTracker(window_sec=1.5, min_arc_px=12)
        self._hold_state = "REST"
        self._hold_start = None
        self._rest_start = None

    def phases(self) -> list:
        """Required: return the _PHASES list."""
        return _PHASES

    def on_phase_change(self, phase: dict):
        """Optional: reset state machines when phase changes."""
        self._tracker_r.reset()
        self._tracker_l.reset()
        self._hold_state = "REST"
        self._hold_start = None
        self._rest_start = None

    def check_pose(self, user_lm, w: int, h: int, phase: dict) -> tuple:
        """
        Validate form during ACTIVE state.
        Returns: (is_error: bool, message: str | None)
        """
        pid = phase["id"]

        if pid == "p1_example_hold":
            return self._check_hold(user_lm, w, h)
        elif pid == "p2_rotation":
            return self._check_rotation(user_lm, w, h, phase)

        return (False, None)

    def detect_rep(self, user_lm, w: int, h: int):
        """
        Count reps during ACTIVE state.
        Use self._active_phase to read current phase (never self._get_phase).
        """
        p = self._active_phase
        if not p:
            return

        pid = p["id"]

        if pid == "p1_example_hold":
            self._rep_hold(user_lm, w, h)
        elif pid == "p2_rotation":
            self._rep_rotation(p)

        # Update trackers for rotation detection
        self._tracker_r.update(user_lm[16].x * w, user_lm[16].y * h)
        self._tracker_l.update(user_lm[15].x * w, user_lm[15].y * h)

    # ─────────────────────────────────────────────────────────────────────
    # PATTERN 1: HOLD-BASED REP
    # ─────────────────────────────────────────────────────────────────────

    def _is_in_hold_position(self, lm, w, h) -> bool:
        """Check if user is in target hold position."""
        if not visible(lm, 0, 15, 16, 11, 12):
            return False
        if lm[15].y >= lm[0].y or lm[16].y >= lm[0].y:
            return False
        sw = shoulder_width(lm, w, h)
        gap = dist(px(lm, 15, w, h), px(lm, 16, w, h)) / sw
        return gap < WRIST_JOIN_RATIO

    def _is_in_rest_position(self, lm) -> bool:
        """Check if user is in rest position."""
        if not visible(lm, 15, 16, 23, 24):
            return False
        hip_y = (lm[23].y + lm[24].y) / 2
        return lm[15].y > hip_y and lm[16].y > hip_y

    def _check_hold(self, lm, w, h) -> tuple:
        """Form feedback for hold phase."""
        if not visible(lm, 11, 12, 15, 16, 23, 24):
            return (False, None)

        now = time.time()
        st = self._hold_state

        if st == "REST":
            return (False, "Get into position to begin")

        if st == "HOLDING":
            held = (now - self._hold_start) if self._hold_start else 0.0
            remaining = max(0.0, HOLD_TARGET_SEC - held)
            if not self._is_in_hold_position(lm, w, h):
                return (False, f"Hold released after {held:.0f}s")
            if remaining > 0:
                return (False, f"Hold — {remaining:.0f}s remaining")
            return (False, "Hold complete!")

        if st == "RESTING":
            rested = (now - self._rest_start) if self._rest_start else 0.0
            remaining = max(0.0, REST_SEC - rested)
            if remaining > 0:
                return (False, f"Rest — {remaining:.0f}s more")
            return (False, "Ready — get into position for next rep")

        return (False, None)

    def _rep_hold(self, lm, w, h):
        """Count hold-based reps using state machine."""
        now = time.time()
        st = self._hold_state

        if st == "REST":
            if self._is_in_hold_position(lm, w, h):
                self._hold_state = "HOLDING"
                self._hold_start = now

        elif st == "HOLDING":
            if self._hold_start is None:
                self._hold_start = now
            held = now - self._hold_start
            if held >= HOLD_TARGET_SEC or self._is_in_rest_position(lm):
                self._hold_state = "RESTING"
                self._rest_start = now

        elif st == "RESTING":
            if self._rest_start is None:
                self._rest_start = now
            if now - self._rest_start >= REST_SEC:
                self.rep_count += 1
                self._hold_state = "REST"
                self._hold_start = None
                self._rest_start = None

    # ─────────────────────────────────────────────────────────────────────
    # PATTERN 2: ROTATION-BASED REP
    # ─────────────────────────────────────────────────────────────────────

    def _check_rotation(self, lm, w, h, phase) -> tuple:
        """Form check for rotation exercises."""
        side = phase.get("side", "right")

        if side in ("right", "both") and visible(lm, 12, 14, 16, 24):
            if not self._tracker_r.is_moving():
                return (False, "Rotate your right hand in circles")

        return (False, f"Keep rotating — {self.rep_count} / {phase.get('target', 5)}")

    def _rep_rotation(self, phase: dict):
        """Count rotation reps from MotionTracker cycles."""
        side = phase.get("side", "right")
        target = phase.get("target", 5)

        if side == "right":
            c = self._tracker_r.cycle_count()
            if c > 0:
                self.rep_count = min(c, target)
