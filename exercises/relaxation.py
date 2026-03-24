"""
exercises/relaxation.py — SKY Yoga Relaxation Exercise

POSE — Relaxation / Savasana (58:10 → end)

Position:
  Lie on back in a relaxed position (Savasana/Corpse Pose).
  Legs extended, arms at sides, entire body relaxed.
  Focus on stillness and deep breathing.

Movement:
  No active movement - maintain stillness and relaxation.

REP DETECTION APPROACH:
  Detect sustained stillness using low movement across body landmarks.
  One rep counted when full stillness is maintained for the duration.
"""

from core.base_controller import BaseController
from core.utils import dist, px, visible

EXERCISE_KEY = "relaxation"

# Movement threshold for detecting stillness
MOVEMENT_THRESHOLD = 0.01
STILLNESS_FRAMES = 10  # frames of stillness to count as active/good

_PHASES = [
    {
        "id": "rel_p1_position",
        "name": "Get Into Position",
        "start": 3490,  # ~58:10 from timeline
        "active": 3495,
        "end": 3510,
        "target": 0,
        "watch_msg": "Lie on your back with legs extended. Arms at sides. Let your entire body relax completely.",
        "check_landmarks": [23, 24, 25, 26, 27, 28],
    },
    {
        "id": "rel_p1_savasana",
        "name": "Savasana — Complete Relaxation",
        "start": 3510,
        "active": 3515,
        "end": 4048,  # End of video
        "target": 1,
        "watch_msg": "Close your eyes, breathe naturally, and remain completely still. Let all tension dissolve.",
        "check_landmarks": [23, 24, 25, 26, 27, 28],
    },
]


class WorkoutController(BaseController):
    """
    Relaxation Exercise Controller.
    Monitors body stillness and maintains a relaxed posture.
    """

    def __init__(self):
        super().__init__()
        self._stillness_count = 0
        self._prev_lm = None

    def phases(self) -> list:
        """Return all phases for this exercise."""
        return _PHASES

    def on_phase_change(self, phase: dict):
        """Called when transitioning to a new phase."""
        self._stillness_count = 0
        self._prev_lm = None

    @property
    def current_phase_name(self) -> str:
        """Return the name of the current phase."""
        p = self._get_phase(self._video_pos)
        return p["name"] if p else "Relaxation"

    # ── dispatcher ───────────────────────────────────────────────────────
    def check_pose(self, user_lm, w, h, phase) -> tuple:
        """
        Check pose correctness.
        Returns: (is_correct, error_message)
        """
        return self._check_relaxation(user_lm, w, h)

    def detect_rep(self, user_lm, w, h):
        """Detect and count reps based on sustained stillness."""
        p = self._active_phase
        if p and p["id"] == "rel_p1_savasana":
            self._detect_stillness(user_lm)

    # ══════════════════════════════════════════════════════════════════════════
    # RELAXATION POSE CHECK
    # ══════════════════════════════════════════════════════════════════════════
    def _check_relaxation(self, lm, w, h) -> tuple:
        """
        Verify that user is in a relaxed lying position.
        Check that key joints are visible and body is low/flat.
        """
        # Verify key landmarks are visible
        if not visible(lm, 23, 24, 25, 26, 27, 28):
            return False, "Body position not clearly visible. Stay in position."

        # Get landmark positions in pixels
        left_hip = px(lm, 23, w, h)
        right_hip = px(lm, 24, w, h)
        left_knee = px(lm, 25, w, h)
        right_knee = px(lm, 26, w, h)
        left_ankle = px(lm, 27, w, h)
        right_ankle = px(lm, 28, w, h)

        # Calculate average hip position (should be relatively low in frame for lying down)
        hip_y = (left_hip[1] + right_hip[1]) / 2
        knee_y = (left_knee[1] + right_knee[1]) / 2
        ankle_y = (left_ankle[1] + right_ankle[1]) / 2

        # In a lying position, hips should be roughly level with knees and ankles
        hip_knee_diff = abs(hip_y - knee_y)
        hip_ankle_diff = abs(hip_y - ankle_y)

        # Allow generous tolerance for relaxed position
        if hip_knee_diff > h * 0.15 or hip_ankle_diff > h * 0.20:
            return False, "Position is not relaxed. Extend your legs more."

        if self.rep_count >= 1:
            return False, "Good — stay relaxed and still"

        return False, "Remain completely still and relaxed"

    # ══════════════════════════════════════════════════════════════════════════
    # STILLNESS DETECTION
    # ══════════════════════════════════════════════════════════════════════════
    def _detect_stillness(self, lm):
        """
        Detect sustained stillness by comparing landmark movement over time.
        Count movement across multiple key joints.
        """
        if not visible(lm, 23, 24, 25, 26, 27, 28):
            self._stillness_count = 0
            self._prev_lm = None
            return

        if self._prev_lm is None:
            self._prev_lm = lm
            return

        # Calculate total movement across key landmarks
        total_movement = 0.0
        for idx in [23, 24, 25, 26, 27, 28]:
            dx = lm[idx].x - self._prev_lm[idx].x
            dy = lm[idx].y - self._prev_lm[idx].y
            total_movement += abs(dx) + abs(dy)

        # Average movement per joint
        avg_movement = total_movement / 6

        # Check if movement is below threshold (stillness)
        if avg_movement < MOVEMENT_THRESHOLD:
            self._stillness_count += 1
        else:
            self._stillness_count = max(0, self._stillness_count - 1)

        # Award rep when stillness threshold is reached
        if self._stillness_count >= STILLNESS_FRAMES:
            self.rep_count += 1
            self._stillness_count = 0  # Reset for potential additional reps

        self._prev_lm = lm
