"""
exercises/_template.py — Template for creating new exercises

COPY THIS FILE to create a new exercise.

Example: Add a leg exercise
  1. cp exercises/_template.py exercises/leg_exercise.py
  2. Set EXERCISE_KEY = "leg"
  3. Copy the phase timestamps from the mentor video into _PHASES
  4. Implement check_pose() using angle(), dist(), shoulder_width() from core.utils
  5. Implement detect_rep() to count reps
  6. Optionally override on_phase_change() to reset state machines
  7. Restart the app — exercise is auto-discovered

────────────────────────────────────────────────────────────────────────────────
CORE RULES (NON-NEGOTIABLE)
────────────────────────────────────────────────────────────────────────────────

1. check_pose(user_lm, w, h, phase) → (is_error, message)
   - NO ref_lm parameter (reference evaluation is banned)
   - NO similarity scores (use body-scale-normalized distances only)
   - Return (True, "message") for hard error (pauses after 12 frames)
   - Return (False, "message") for soft warning (shown but no pause)
   - Return (False, None) for good form

2. Body measurements MUST be normalized by shoulder_width(lm, w, h)
   - WRONG: if dist(left_wrist, right_wrist) > w * 0.09
   - CORRECT: if dist(left_wrist, right_wrist) / shoulder_width(lm, w, h) > 0.30

3. Always check visibility FIRST
   - from core.utils import visible
   - if not visible(lm, 11, 12, 13): return (False, None)

4. Angle checks use angle(a, b, c) from core.utils
   - angle(shoulder, elbow, wrist) checks elbow bend
   - if angle(...) < 90: return (True, "Straighten your arm")

5. Error streak is handled by base_controller (12 frame threshold)
   - Never implement your own debouncing
   - Just return (True, msg) and let base class handle pause timing

6. Rep counting is ADDITIVE
   - For rotations: detect cycle completion, add to rep_count
   - Example: rep_count += cycle_tracker.cycle_count() - self._last_cycle
   - Never overwrite: rep_count = ...

7. State machines reset on phase change
   - Call self.rep_count = 0 in on_phase_change()
   - Call tracker.reset() for motion trackers
   - BreathDetector.reset() for breath-based holds

────────────────────────────────────────────────────────────────────────────────
PHASE SCHEMA
────────────────────────────────────────────────────────────────────────────────

Each phase dict must have:
  id (str):              unique identifier within exercise
  name (str):            shown in UI banner ("Raise Arms Overhead")
  start (float):         video timestamp when phase begins (seconds)
  active (float):        video timestamp when user evaluation starts
  end (float):           video timestamp when phase ends
  target (int):          minimum reps to complete (0 = untimed, no enforcement)
  watch_msg (str):       message shown during WATCH phase
  check_landmarks (list): indices of landmarks needed for this phase

Optional fields:
  zoom (bool):           True = skip evaluation, user just watches
  side (str):            "right"/"left"/"both"/"knees" for sided movements

────────────────────────────────────────────────────────────────────────────────
EXAMPLE MINIMAL EXERCISE
────────────────────────────────────────────────────────────────────────────────
"""

from core.base_controller import BaseController
from core.utils import angle, dist, px, visible, shoulder_width


EXERCISE_KEY = "example"  # ← Change this to your exercise key

_PHASES = [
    {
        "id": "p1_raise",
        "name": "Raise Arms",
        "start": 0,
        "active": 10,
        "end": 50,
        "target": 3,
        "watch_msg": "Watch — raise arms overhead",
        "check_landmarks": [11, 12, 13, 14, 15, 16],
    },
]


class WorkoutController(BaseController):
    """
    Exercise controller. Implement check_pose() and detect_rep().
    All other state management is handled by BaseController.
    """

    def __init__(self):
        """Initialize controller and state machines."""
        super().__init__()
        # Add exercise-specific trackers here if needed
        # Example: self._wrist_tracker = MotionTracker(1.5, 12)

    def phases(self) -> list:
        """Return list of phases for this exercise."""
        return _PHASES

    def on_phase_change(self, phase: dict):
        """
        Called when transitioning to a new phase.
        Reset any state machines here.
        """
        # Example:
        # if self._wrist_tracker:
        #     self._wrist_tracker.reset()
        pass

    def check_pose(self, user_lm, w: int, h: int, phase: dict) -> tuple:
        """
        Evaluate user form in current phase.

        Args:
            user_lm: MediaPipe landmarks
            w, h: frame dimensions
            phase: current phase dict

        Returns:
            (is_error: bool, message: str | None)
        """

        # ─── CHECK VISIBILITY FIRST ──────────────────────────────────────
        required = phase.get("check_landmarks", [11, 12, 13, 14, 15, 16])
        if not visible(user_lm, *required):
            return (False, None)

        # ─── EVALUATE FORM ───────────────────────────────────────────────

        # Example 1: Check if arms are raised
        # Arms raised = wrists above hips
        if user_lm[15].y < user_lm[23].y and user_lm[16].y < user_lm[23].y:
            # Arms are up — check if they're straight
            l_shoulder = px(user_lm, 11, w, h)
            l_elbow = px(user_lm, 13, w, h)
            l_wrist = px(user_lm, 15, w, h)

            elbow_angle = angle(l_shoulder, l_elbow, l_wrist)
            if elbow_angle < 150:
                return (True, "Straighten your left arm")

            # All checks passed
            return (False, None)
        else:
            # Arms not raised — guidance
            return (False, "Raise your arms overhead")

    def detect_rep(self, user_lm, w: int, h: int):
        """
        Detect and count completed reps.
        Called every frame during ACTIVE phase.

        Increment self.rep_count when you detect a rep.
        """
        # Example: if wrists go from below hips to above head, count a rep
        if user_lm[15].y < user_lm[0].y and user_lm[16].y < user_lm[0].y:
            # Both wrists are above nose (fully raised)
            # You could add a state machine here to count only complete cycles:
            # if self._arm_raised_phase == "DOWN":
            #     self._arm_raised_phase = "UP"
            # elif self._arm_raised_phase == "UP" and (both wrists below hips):
            #     self._arm_raised_phase = "DOWN"
            #     self.rep_count += 1
            pass

        # For now, just pass — rep counting happens in check_pose() or a separate tracker


# ────────────────────────────────────────────────────────────────────────────
# DEVELOPER CHECKLIST
# ────────────────────────────────────────────────────────────────────────────
#
# Before deploying a new exercise:
#
# [ ] EXERCISE_KEY is set (no underscores, matches timeline in main.py)
# [ ] _PHASES has correct video timestamps (from mentor video)
# [ ] check_pose() uses visible() first to guard against NaN
# [ ] check_pose() uses angle() from core.utils (not math.acos)
# [ ] check_pose() uses shoulder_width() to normalize all distances
# [ ] check_pose() returns (bool, str|None) for ALL code paths
# [ ] detect_rep() increments rep_count incrementally (never overwrites)
# [ ] on_phase_change() resets state machines
# [ ] NO imports of pose_similarity, ReferenceAnalyzer, or similarity functions
# [ ] NO ref_lm parameter in check_pose()
# [ ] Error streak logic relies on base_controller (no custom debouncing)
#
# ────────────────────────────────────────────────────────────────────────────