"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
POSE — Massage (~35:00 → 44:48)

Movement:
  Perform self-massage on head, face, neck, arms, legs.

REP DETECTION APPROACH:
  Detect continuous hand movement using wrist motion.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from core.base_controller import BaseController
from core.utils import calculate_angle, dist, lm_px, visible, shoulder_width

EXERCISE_KEY = "massage"

HOLD_FRAMES = 8

_PHASES = [
    {
        "id":        "ms_p1_massage",
        "name":      "Massage — Continuous",
        "start":     3024,
        "active":    3037,
        "end":       3195,
        "target":    10,
        "watch_msg": "Perform gentle self-massage on head, face, neck, arms and legs",
        "check_landmarks": [11, 12, 15, 16],
    },
]


class WorkoutController(BaseController):

    def __init__(self):
        super().__init__()
        self._move_count = 0
        self._prev_lm    = None

    def phases(self) -> list:
        return _PHASES

    def on_phase_change(self, phase: dict):
        self._move_count = 0
        self._prev_lm    = None

    @property
    def current_phase_name(self) -> str:
        p = self._get_phase(self._video_pos)
        return p["name"] if p else "Massage"

    @property
    def coach_state(self) -> str:
        return self._coach_state

    # ── dispatcher ───────────────────────────────────────────────────
    def check_pose(self, user_lm, ref_lm, w, h, phase) -> tuple:
        return self._check_massage(user_lm, w, h)

    def detect_rep(self, user_lm, w, h):
        p = self._active_phase
        if p and p["id"] == "ms_p1_massage":
            self._rep_massage(user_lm)

    # ══════════════════════════════════════════════════════════════════
    # MASSAGE CHECK
    # ══════════════════════════════════════════════════════════════════
    def _check_massage(self, lm, w, h) -> tuple:
        if not visible(lm, 11, 12, 15, 16):
            return False, None

        lw = lm_px(lm, 15, w, h); rw = lm_px(lm, 16, w, h)
        nose = lm_px(lm, 0, w, h)

        sw = shoulder_width(lm, w, h)

        if dist(lw, nose) > sw * 1.5 and dist(rw, nose) > sw * 1.5:
            return True, "Bring your hands closer to your upper body"

        if self.rep_count >= 1:
            return False, "Good — continue massage"

        return False, "Keep moving your hands and massage your body"

    # ══════════════════════════════════════════════════════════════════
    # MOVEMENT DETECTION
    # ══════════════════════════════════════════════════════════════════
    def _rep_massage(self, lm):
        if not visible(lm, 15, 16):
            return

        if self._prev_lm is None:
            self._prev_lm = lm
            return

        lw_move = abs(lm[15].x - self._prev_lm[15].x) + abs(lm[15].y - self._prev_lm[15].y)
        rw_move = abs(lm[16].x - self._prev_lm[16].x) + abs(lm[16].y - self._prev_lm[16].y)

        if lw_move + rw_move > 0.02:
            self._move_count += 1
        else:
            self._move_count = max(0, self._move_count - 1)

        if self._move_count >= HOLD_FRAMES:
            self.rep_count += 1

        self._prev_lm = lm