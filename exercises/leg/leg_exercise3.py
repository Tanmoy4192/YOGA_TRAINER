"""
exercises/leg_exercise.py — Leg Exercises
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
POSE 5 — Seated Ankle Rotations (Parallel)

Starting position:
  Sit on floor. Legs extended forward.
  Feet spread slightly apart (to allow full circular motion).
  Both hands on floor behind your body.

Movement:
  Rotate both ankles in a circular motion in the same direction.
  (e.g., Both sweep Left, Down, Right, Up)
  1 Full Circular Sweep = 1 rep. Target: 10 reps (e.g., 5 CW, 5 CCW).

REP DETECTION APPROACH:
  Problem: 2D cameras struggle to see the "depth" when toes point away.
  Solution: Use the Horizontal (X-axis) extremes to track the circle.
    As the foot draws a circle, it must pass through a maximum LEFT 
    and maximum RIGHT position relative to the ankle.
    
    When rotating LEFT:
      left_foot_index.x  < left_ankle.x
      right_foot_index.x < right_ankle.x
    When rotating RIGHT:
      left_foot_index.x  > left_ankle.x
      right_foot_index.x > right_ankle.x

  State Machine (Direction Agnostic):
    CENTER -> hits LEFT/RIGHT -> hits OPPOSITE side -> returns CENTER = 1 Rep.
    This naturally captures both Clockwise and Anticlockwise parallel circles!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from core.base_controller import BaseController
from core.utils import calculate_angle, dist, lm_px

EXERCISE_KEY = "leg"

# How many consecutive frames the feet must hold a position to avoid noise
HOLD_FRAMES = 5

_PHASES = [
    {
        "id":        "leg_p5_setup",
        "name":      "Get Into Position",
        "start":     0, #12.46
        "active":    10, #12.56
        "end":       20, #13.17
        "target":    10,
        "watch_msg": "Sit with legs straight. Spread your feet slightly so they have room to draw full circles.",
        "check_landmarks": [15, 16, 23, 24, 25, 26, 27, 28],
    },
    {
        "id":        "leg_p5_ankle_rotation",
        "name":      "Ankle Rotations — 10 Reps",
        "start":     20,#13.17
        "active":    25,#13.17
        "end":       200,#13.42
        "target":    10,
        "watch_msg": "Draw big circles with your toes. Rotate both ankles in the same direction.",
        "check_landmarks": [23, 24, 25, 26, 27, 28, 31, 32],
    },
]


class WorkoutController(BaseController):

    def __init__(self):
        super().__init__()
        # State tracking for the circular ankle sweep
        self._rotation_state = "CENTER"
        self._first_side     = None
        self._left_count     = 0
        self._right_count    = 0
        self._center_count   = 0

    def phases(self) -> list:
        return _PHASES

    def on_phase_change(self, phase: dict):
        self._rotation_state = "CENTER"
        self._first_side     = None
        self._left_count     = 0
        self._right_count    = 0
        self._center_count   = 0

    @property
    def current_phase_name(self) -> str:
        p = self._get_phase(self._video_pos)
        return p["name"] if p else "Ankle Rotations"

    @property
    def coach_state(self) -> str:
        return self._coach_state

    # ── dispatcher ───────────────────────────────────────────────────
    def check_pose(self, user_lm, ref_lm, w, h, phase) -> tuple:
        pid = phase["id"]
        if pid == "leg_p5_setup":
            return self._check_setup(user_lm, w, h)
        elif pid == "leg_p5_ankle_rotation":
            return self._check_ankle_rotation(user_lm, w, h)
        return False, None

    def detect_rep(self, user_lm, w, h):
        p = self._get_phase(self._video_pos)
        if p and p["id"] == "leg_p5_ankle_rotation":
            self._rep_ankle_rotation(user_lm, w, h)

    # ══════════════════════════════════════════════════════════════════
    # SETUP — guide user into seated parallel-leg position
    # ══════════════════════════════════════════════════════════════════
    def _check_setup(self, lm, w, h) -> tuple:
        lh = lm_px(lm, 23, w, h); rh = lm_px(lm, 24, w, h)
        lk = lm_px(lm, 25, w, h); rk = lm_px(lm, 26, w, h)
        la = lm_px(lm, 27, w, h); ra = lm_px(lm, 28, w, h)
        lw = lm_px(lm, 15, w, h); rw = lm_px(lm, 16, w, h)

        # 1. Knees must be straight
        if calculate_angle(lh, lk, la) < 155:
            return True, "Straighten your left leg out flat"
        if calculate_angle(rh, rk, ra) < 155:
            return True, "Straighten your right leg out flat"

        # 2. Hands should be behind hips
        hip_mid_x = (lh[0] + rh[0]) / 2
        if lw[0] > hip_mid_x + w * 0.15 or rw[0] < hip_mid_x - w * 0.15:
            return True, "Place both hands flat on the floor behind you for support"

        # 3. Feet need to be slightly spread (for circular clearance)
        ankle_dist = dist(la, ra)
        hip_w      = dist(lh, rh) or 1
        ratio      = ankle_dist / hip_w
        if ratio < 0.8:
            return True, "Spread your feet a bit so they don't collide while rotating"
        if ratio > 2.5:
            return True, "Bring your legs a little closer together"

        return False, "Good position — hold still to begin."

    # ══════════════════════════════════════════════════════════════════
    # ANKLE POSITION DETECTION
    # Compare both foot_index X positions relative to their ankles.
    # Returns "LEFT", "RIGHT", or "CENTER"
    # ══════════════════════════════════════════════════════════════════
    def _get_ankle_position(self, lm) -> str:
        # Check landmark visibility
        if min(lm[27].visibility, lm[28].visibility, lm[31].visibility, lm[32].visibility) < 0.35:
            return "UNKNOWN"

        l_ankle_x = lm[27].x; r_ankle_x = lm[28].x
        l_foot_x  = lm[31].x; r_foot_x  = lm[32].x

        thr = 0.025  # 2.5% of normalized frame width threshold

        l_points_left  = l_foot_x < l_ankle_x - thr
        r_points_left  = r_foot_x < r_ankle_x - thr

        l_points_right = l_foot_x > l_ankle_x + thr
        r_points_right = r_foot_x > r_ankle_x + thr

        if l_points_left and r_points_left:
            return "LEFT"
        if l_points_right and r_points_right:
            return "RIGHT"
        
        return "CENTER"

    # ══════════════════════════════════════════════════════════════════
    # ANKLE ROTATION CHECK — coach messages and constraints
    # ══════════════════════════════════════════════════════════════════
    def _check_ankle_rotation(self, lm, w, h) -> tuple:
        lh = lm_px(lm, 23, w, h); rh = lm_px(lm, 24, w, h)
        lk = lm_px(lm, 25, w, h); rk = lm_px(lm, 26, w, h)
        la = lm_px(lm, 27, w, h); ra = lm_px(lm, 28, w, h)
        done = self.rep_count

        # Constraint: Isolate the ankle by keeping legs straight
        if calculate_angle(lh, lk, la) < 145 or calculate_angle(rh, rk, ra) < 145:
            return True, "Keep your legs straight — make the circles using only your ankles."

        if done >= 10:
            return False, "Excellent work! You have completed all ankle rotations."

        # Guide based on state
        state = self._rotation_state
        if state == "CENTER":
            return False, f"Start drawing a circle with your toes  {done}/10"
        elif state == "REACHED_FIRST_SIDE":
            return False, f"Keep going, sweep them around  {done}/10"
        elif state == "REACHED_SECOND_SIDE":
            return False, f"Finish the circle, bring them back to the start  {done}/10"

        return False, None

    # ══════════════════════════════════════════════════════════════════
    # REP COUNTING — Circular Sweep Tracking
    # State sequence required for 1 rep:
    # CENTER -> hits LEFT/RIGHT -> hits OPPOSITE side -> returns CENTER
    # ══════════════════════════════════════════════════════════════════
    def _rep_ankle_rotation(self, lm, w, h):
        pos = self._get_ankle_position(lm)

        if pos == "UNKNOWN":
            return

        # Frame accumulators
        if pos == "LEFT":
            self._left_count   += 1
            self._right_count   = 0
            self._center_count  = 0
        elif pos == "RIGHT":
            self._right_count  += 1
            self._left_count    = 0
            self._center_count  = 0
        elif pos == "CENTER":
            self._center_count += 1
            self._left_count    = 0
            self._right_count   = 0

        left_held   = self._left_count >= HOLD_FRAMES
        right_held  = self._right_count >= HOLD_FRAMES
        center_held = self._center_count >= HOLD_FRAMES

        # State transitions
        if self._rotation_state == "CENTER":
            if left_held:
                self._rotation_state = "REACHED_FIRST_SIDE"
                self._first_side  = "LEFT"
            elif right_held:
                self._rotation_state = "REACHED_FIRST_SIDE"
                self._first_side  = "RIGHT"

        elif self._rotation_state == "REACHED_FIRST_SIDE":
            if self._first_side == "LEFT" and right_held:
                self._rotation_state = "REACHED_SECOND_SIDE"
            elif self._first_side == "RIGHT" and left_held:
                self._rotation_state = "REACHED_SECOND_SIDE"

        elif self._rotation_state == "REACHED_SECOND_SIDE":
            if center_held:
                self._rotation_state = "CENTER"
                self._first_side  = None
                self.rep_count   += 1  # 1 Full circular sweep complete!