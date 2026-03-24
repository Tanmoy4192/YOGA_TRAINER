"""
exercises/makarsana.py — Makarsana
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
POSE — Makarsana (31:19 → ~35:00)

Starting position:
  Lie on stomach. Legs slightly apart.
  Hands folded under head. Full body relaxed.

Movement:
  No movement — maintain stillness.

REP DETECTION APPROACH:
  Detect STILLNESS using sustained low movement across landmarks.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from core.base_controller import BaseController
from core.utils import calculate_angle, dist, lm_px, visible

EXERCISE_KEY = "makarsana"

HOLD_FRAMES = 8

_PHASES = [
    {
        "id":        "mk_p1_setup",
        "name":      "Get Into Position",
        "start":     2418,
        "active":    2460,
        "end":       2490,
        "target":    3,
        "watch_msg": "Lie on your stomach, keep legs slightly apart, place hands under your head",
        "check_landmarks": [23, 24, 25, 26, 27, 28],
    },
    {
        "id":        "mk_p1_hold",
        "name":      "Makarsana — Relaxation",
        "start":     2490,
        "active":    2506,
        "end":       2545,
        "target":    1,
        "watch_msg": "Stay completely still and relaxed",
        "check_landmarks": [23, 24, 25, 26, 27, 28],
    },
]


class WorkoutController(BaseController):

    def __init__(self):
        super().__init__()
        self._still_count = 0
        self._prev_lm     = None

    def phases(self) -> list:
        return _PHASES

    def on_phase_change(self, phase: dict):
        self._still_count = 0
        self._prev_lm     = None

    @property
    def current_phase_name(self) -> str:
        p = self._get_phase(self._video_pos)
        return p["name"] if p else "Makarsana"

    @property
    def coach_state(self) -> str:
        return self._coach_state

    # ── dispatcher ───────────────────────────────────────────────────
    def check_pose(self, user_lm, ref_lm, w, h, phase) -> tuple:
        pid = phase["id"]
        if pid == "mk_p1_setup":
            return self._check_setup(user_lm, w, h)
        elif pid == "mk_p1_hold":
            return self._check_hold(user_lm, w, h)
        return False, None

    def detect_rep(self, user_lm, w, h):
        p = self._active_phase
        if p and p["id"] == "mk_p1_hold":
            self._rep_hold(user_lm)

    # ══════════════════════════════════════════════════════════════════
    # SETUP
    # ══════════════════════════════════════════════════════════════════
    def _check_setup(self, lm, w, h) -> tuple:
        if not visible(lm, 23, 24, 25, 26, 27, 28):
            return False, None

        lh = lm_px(lm, 23, w, h); rh = lm_px(lm, 24, w, h)
        lk = lm_px(lm, 25, w, h); rk = lm_px(lm, 26, w, h)
        la = lm_px(lm, 27, w, h); ra = lm_px(lm, 28, w, h)

        if calculate_angle(lh, lk, la) < 150:
            return True, "Keep your left leg straight and relaxed"
        if calculate_angle(rh, rk, ra) < 150:
            return True, "Keep your right leg straight and relaxed"

        if dist(la, ra) / (dist(lh, rh) or 1) < 0.5:
            return True, "Keep your legs slightly apart"

        return False, "Good position — stay still and relax"

    # ══════════════════════════════════════════════════════════════════
    # HOLD CHECK
    # ══════════════════════════════════════════════════════════════════
    def _check_hold(self, lm, w, h) -> tuple:
        if not visible(lm, 23, 24, 25, 26, 27, 28):
            return False, None

        lh = lm_px(lm, 23, w, h); rh = lm_px(lm, 24, w, h)
        lk = lm_px(lm, 25, w, h); rk = lm_px(lm, 26, w, h)
        la = lm_px(lm, 27, w, h); ra = lm_px(lm, 28, w, h)

        if calculate_angle(lh, lk, la) < 145:
            return True, "Do not bend your left leg"
        if calculate_angle(rh, rk, ra) < 145:
            return True, "Do not bend your right leg"

        if dist(la, ra) / (dist(lh, rh) or 1) < 0.5:
            return True, "Keep your legs relaxed and slightly apart"

        if self.rep_count >= 1:
            return False, "Well done — you are fully relaxed"

        return False, "Stay completely still and relax your body"

    # ══════════════════════════════════════════════════════════════════
    # STILLNESS DETECTION
    # ══════════════════════════════════════════════════════════════════
    def _rep_hold(self, lm):
        if not visible(lm, 23, 24, 25, 26, 27, 28):
            return

        if self._prev_lm is None:
            self._prev_lm = lm
            return

        movement = 0
        for i in [23, 24, 25, 26, 27, 28]:
            movement += abs(lm[i].x - self._prev_lm[i].x) + abs(lm[i].y - self._prev_lm[i].y)

        if movement < 0.01:
            self._still_count += 1
        else:
            self._still_count = max(0, self._still_count - 1)

        if self._still_count >= HOLD_FRAMES:
            self.rep_count += 1

        self._prev_lm = lmS