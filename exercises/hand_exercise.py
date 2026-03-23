"""
exercises/hand_exercise.py — Complete SKY Yoga Hand Exercises

"""

import time
from core.base_controller import BaseController
from core.utils import angle, dist, px, visible, shoulder_width
from core.motion_tracker import MotionTracker

EXERCISE_KEY = "hand"

P1_HOLD_TARGET_SEC = 10.0   # ideal hold duration
P1_HOLD_SHORT_SEC  = 3.0    # below this = "too short" warning
P1_REST_TARGET_SEC = 4.0    # rest between reps

_PHASES = [
    {
        "id": "p1_raise_hold",
        "name": "Raise Arms & Hold",
        "start": 12,
        "active": 23,
        "end": 150,
        "target": 3,
        "watch_msg": "Raise both arms overhead, join palms, hold for 4 breaths, then lower arms to rest",
        "check_landmarks": [11, 12, 13, 14, 15, 16, 23, 24, 27, 28],
    },
    {
        "id": "p2_t_pose",
        "name": "T-Pose Breathe",
        "start": 150,
        "active": 160,
        "end": 230,
        "target": 5,
        "check_landmarks": [11, 12, 13, 14, 15, 16],
    },
    {
        "id": "p3_right_cw",
        "name": "Right Hand Clockwise",
        "start": 230,
        "active": 240,
        "end": 256,
        "target": 5,
        "side": "right",
        "check_landmarks": [12, 14, 16],
    },
    {
        "id": "p4_right_ccw",
        "name": "Right Hand Counter-Clockwise",
        "start": 256,
        "active": 256,
        "end": 272,
        "target": 5,
        "side": "right",
        "check_landmarks": [12, 14, 16],
    },
    {
        "id": "p5_left_cw",
        "name": "Left Hand Clockwise",
        "start": 272,
        "active": 274,
        "end": 290,
        "target": 5,
        "side": "left",
        "check_landmarks": [11, 13, 15],
    },
    {
        "id": "p6_left_ccw",
        "name": "Left Hand Counter-Clockwise",
        "start": 290,
        "active": 292,
        "end": 312,
        "target": 5,
        "side": "left",
        "check_landmarks": [11, 13, 15],
    },
    {
        "id": "p7_both_cw",
        "name": "Both Hands Clockwise",
        "start": 312,
        "active": 314,
        "end": 338,
        "target": 5,
        "side": "both",
        "watch_msg": "Both arms extended, join fingers, rotate both hands clockwise together 5 times",
        "check_landmarks": [11, 12, 13, 14, 15, 16],
    },
    {
        "id": "p8_both_ccw",
        "name": "Both Hands Counter-Clockwise",
        "start": 348,
        "active": 349,
        "end": 363,
        "target": 5,
        "side": "both",
        "watch_msg": "Both arms extended, rotate both hands counter-clockwise together",
        "check_landmarks": [11, 12, 13, 14, 15, 16],
    },
    {
        "id": "p9_arm_swings",
        "name": "Arm Swings",
        "start": 363,
        "active": 370,
        "end": 385,
        "target": 10,
        "watch_msg": "Step right leg forward, swing both arms in big circles — 5 clockwise then 5 counter-clockwise",
        "check_landmarks": [11, 12, 15, 16, 27, 28],
    },
    {
        "id": "p10_torso",
        "name": "Torso Rotation",
        "start": 522,
        "active": 532,
        "end": 602,
        "target": 3,
        "watch_msg": "Thumbs touching at shoulder level, rotate torso right then left — that is 1 rep",
        "check_landmarks": [11, 12, 15, 16, 23, 24],
    },
    {
        "id": "p11_knee",
        "name": "Knee Rotation",
        "start": 602,
        "active": 612,
        "end": 660,
        "target": 3,
        "watch_msg": "Place hands on knees, rotate knees clockwise 3 times then counter-clockwise 3 times",
        "check_landmarks": [23, 24, 25, 26, 27, 28, 15, 16],
    },
]


class WorkoutController(BaseController):

    def __init__(self):
        super().__init__()

        # Motion trackers
        self._tw_l = MotionTracker(1.5, 12)
        self._tw_r = MotionTracker(1.5, 12)
        self._tk_l = MotionTracker(2.0, 10)
        self._tk_r = MotionTracker(2.0, 10)
        self._ts_l = MotionTracker(2.0, 15)
        self._ts_r = MotionTracker(2.0, 15)

        # ── Exercise 1 state machine ──────────────────────────────────────
        # States: REST → UP → DOWN → (count) → REST
        self._p1_state      = "REST"
        self._p1_hold_start = None   # when arms went UP
        self._p1_down_start = None   # when arms came DOWN
        self._p1_short_hold = False  # flag: hold was < 3s

        # Exercise 2
        self._p2_state        = "T_POS"
        self._p2_forward_once = False

        # Rotation tracking
        self._last_cyc_l = 0
        self._last_cyc_r = 0
        self._last_cyc_k = 0

        # Torso
        self._torso_rotated      = False
        self._torso_baseline_gap = None

        # Arm swings
        self._arms_down = False

    # ─────────────────────────────────────────────────────────────────────

    def phases(self) -> list:
        return _PHASES

    def on_phase_change(self, phase: dict):
        for t in [self._tw_l, self._tw_r,
                  self._tk_l, self._tk_r,
                  self._ts_l, self._ts_r]:
            t.reset()

        # Reset exercise 1
        self._p1_state      = "REST"
        self._p1_hold_start = None
        self._p1_down_start = None
        self._p1_short_hold = False

        # Reset exercise 2
        self._p2_state        = "T_POS"
        self._p2_forward_once = False

        self._last_cyc_l = 0
        self._last_cyc_r = 0
        self._last_cyc_k = 0

        self._torso_rotated      = False
        self._torso_baseline_gap = None
        self._arms_down          = False

    @property
    def current_phase_name(self) -> str:
        p = self._get_phase(self._video_pos)
        return p["name"] if p else "Hand Exercises"

    # ─────────────────────────────────────────────────────────────────────
    # MOTION TRACKING
    # ─────────────────────────────────────────────────────────────────────

    def _track(self, lm, w: int, h: int):
        self._tw_l.update(lm[15].x * w, lm[15].y * h)
        self._tw_r.update(lm[16].x * w, lm[16].y * h)
        self._tk_l.update(lm[25].x * w, lm[25].y * h)
        self._tk_r.update(lm[26].x * w, lm[26].y * h)
        self._ts_l.update(lm[11].x * w, lm[11].y * h)
        self._ts_r.update(lm[12].x * w, lm[12].y * h)

    # ─────────────────────────────────────────────────────────────────────
    # DISPATCHER
    # ─────────────────────────────────────────────────────────────────────

    def check_pose(self, user_lm, w: int, h: int, phase: dict) -> tuple:
        self._track(user_lm, w, h)
        pid = phase["id"]

        if   pid == "p1_raise_hold":
            return self._check_p1(user_lm, w, h)
        elif pid == "p2_t_pose":
            return self._check_p2(user_lm, w, h)
        elif pid in ("p3_right_cw", "p4_right_ccw",
                     "p5_left_cw",  "p6_left_ccw",
                     "p7_both_cw",  "p8_both_ccw"):
            return self._check_rotation(user_lm, w, h, phase)
        elif pid == "p9_arm_swings":
            return self._check_swings(user_lm, w, h)
        elif pid == "p10_torso":
            return self._check_torso(user_lm, w, h)
        elif pid == "p11_knee":
            return self._check_knee(user_lm, w, h)

        return (False, None)

    def detect_rep(self, user_lm, w: int, h: int):
        # Use _active_phase (set by base update()) so reps count even
        # when video_pos is in a gap or HOLD (where _get_phase returns None)
        p = self._active_phase
        if not p:
            return
        pid = p["id"]

        if   pid == "p1_raise_hold":
            self._rep_p1(user_lm, w, h)
        elif pid == "p2_t_pose":
            self._rep_p2(user_lm, w, h)
        elif pid in ("p3_right_cw", "p4_right_ccw",
                     "p5_left_cw",  "p6_left_ccw",
                     "p7_both_cw",  "p8_both_ccw"):
            self._rep_rotation(p)
        elif pid == "p9_arm_swings":
            self._rep_swings(user_lm, w, h)
        elif pid == "p10_torso":
            self._rep_torso(user_lm, w, h)
        elif pid == "p11_knee":
            self._rep_knee()

    # ─────────────────────────────────────────────────────────────────────
    # EXERCISE 1 HELPERS
    # ─────────────────────────────────────────────────────────────────────

    def _is_up(self, lm, w, h) -> bool:
        """Both wrists ABOVE nose AND palms joined (gap < 20% shoulder width)."""
        if not visible(lm, 0, 15, 16):
            return False
        # wrists must be above nose (lower y value = higher on screen)
        if lm[15].y >= lm[0].y or lm[16].y >= lm[0].y:
            return False
        sw       = shoulder_width(lm, w, h)
        palm_gap = dist(px(lm, 15, w, h), px(lm, 16, w, h)) / sw
        return palm_gap < 0.25   # palms joined

    def _is_rest(self, lm) -> bool:
        """Both wrists below hips."""
        if not visible(lm, 15, 16, 23, 24):
            return False
        hip_y = (lm[23].y + lm[24].y) / 2
        return lm[15].y > hip_y and lm[16].y > hip_y

    # ─────────────────────────────────────────────────────────────────────
    # EXERCISE 1: CHECK POSE  — feedback text shown on screen
    # ─────────────────────────────────────────────────────────────────────

    def _check_p1(self, lm, w: int, h: int) -> tuple:
        if not visible(lm, 11, 12, 15, 16, 23, 24):
            return (False, None)

        # Leg width check
        if visible(lm, 27, 28):
            gap = dist(px(lm, 27, w, h), px(lm, 28, w, h))
            if gap < w * 0.08 or gap > w * 0.30:
                return (True, "Keep legs at normal shoulder width")

        now = time.time()
        st  = self._p1_state

        # ── REST: waiting for user to raise arms ─────────────────────────
        if st == "REST":
            return (False, "Raise both arms overhead and join your palms")

        # ── UP: arms raised — show hold timer ────────────────────────────
        if st == "UP":
            held      = (now - self._p1_hold_start) if self._p1_hold_start else 0.0
            remaining = max(0.0, P1_HOLD_TARGET_SEC - held)

            if not self._is_up(lm, w, h):
                # Arms dropped
                if held < P1_HOLD_SHORT_SEC:
                    return (False, "Arms lowering - next time hold longer!")
                return (False, f"Good hold ({held:.0f}s)! Lower arms fully to rest")

            if remaining > 0:
                return (False, f"Hold - {remaining:.0f}s remaining")
            return (False, "Great hold! Now lower arms slowly to your sides")

        # ── DOWN: arms down, resting before counting rep ─────────────────
        if st == "DOWN":
            rested    = (now - self._p1_down_start) if self._p1_down_start else 0.0
            remaining = max(0.0, P1_REST_TARGET_SEC - rested)
            suffix    = "  Hold longer next time!" if self._p1_short_hold else ""
            if remaining > 0:
                return (False, f"Rest - {remaining:.0f}s more{suffix}")
            return (False, f"Rep counted!{suffix} Ready for next rep")

        return (False, None)

    # ─────────────────────────────────────────────────────────────────────
    # EXERCISE 1: REP COUNTING  — state transitions
    # ─────────────────────────────────────────────────────────────────────

    def _rep_p1(self, lm, w: int, h: int):
        """
        State machine:
          REST  → arms go UP (wrists above nose + palms joined)
          UP    → arms come DOWN (wrists below hips)  [hold timer noted]
          DOWN  → after 4s rest → rep_count += 1 → back to REST
        """
        now = time.time()
        st  = self._p1_state

        # ── REST → UP ────────────────────────────────────────────────────
        if st == "REST":
            if self._is_up(lm, w, h):
                self._p1_state      = "UP"
                self._p1_hold_start = now
                self._p1_short_hold = False

        # ── UP → DOWN ────────────────────────────────────────────────────
        elif st == "UP":
            if self._p1_hold_start is None:
                self._p1_hold_start = now

            held = now - self._p1_hold_start

            # Auto-transition after full hold target, even if arms still up
            if held >= P1_HOLD_TARGET_SEC:
                self._p1_state      = "DOWN"
                self._p1_down_start = now
                self._p1_short_hold = False
                return

            # Arms came down early
            if self._is_rest(lm):
                self._p1_short_hold = held < P1_HOLD_SHORT_SEC
                self._p1_state      = "DOWN"
                self._p1_down_start = now

        # ── DOWN → REST (rep counted here) ───────────────────────────────
        elif st == "DOWN":
            if self._p1_down_start is None:
                self._p1_down_start = now
                return

            rested = now - self._p1_down_start
            if rested >= P1_REST_TARGET_SEC:
                self.rep_count     += 1
                self._p1_state      = "REST"
                self._p1_hold_start = None
                self._p1_down_start = None
                self._p1_short_hold = False

    # ─────────────────────────────────────────────────────────────────────
    # EXERCISE 2: T-POSE BREATHE
    # ─────────────────────────────────────────────────────────────────────

    def _is_t_pose(self, lm, w, h) -> bool:
        """
        T-pose: both arms extended out to sides at shoulder height.
        Check: wrists are far apart (> 1.6x shoulder_width) AND
               wrists are roughly at shoulder height (y within 0.18).
        Image 2 shows this position.
        """
        if not visible(lm, 11, 12, 15, 16):
            return False
        sw  = shoulder_width(lm, w, h)
        lwr = px(lm, 15, w, h)
        rwr = px(lm, 16, w, h)
        gap = dist(lwr, rwr) / sw
        # wrists spread wide
        if gap < 1.5:
            return False
        # wrists near shoulder height (y close to shoulder y)
        if abs(lm[15].y - lm[11].y) > 0.20:
            return False
        if abs(lm[16].y - lm[12].y) > 0.20:
            return False
        return True

    def _is_forward_together(self, lm, w, h) -> bool:
        """
        Forward/together: both hands brought in front of chest, palms
        close together. Wrists near each other (< 0.35x shoulder_width)
        AND wrists are in front (z is less negative / more positive than
        shoulders — approximate with y near shoulder height since MediaPipe
        z is unreliable; use small wrist-gap as primary signal).
        Image 1 shows this position.
        """
        if not visible(lm, 11, 12, 15, 16):
            return False
        sw  = shoulder_width(lm, w, h)
        lwr = px(lm, 15, w, h)
        rwr = px(lm, 16, w, h)
        gap = dist(lwr, rwr) / sw
        # hands must be close together
        if gap > 0.45:
            return False
        # hands should be roughly at chest/shoulder height, not below hips
        mid_wrist_y = (lm[15].y + lm[16].y) / 2
        shoulder_y  = (lm[11].y + lm[12].y) / 2
        if mid_wrist_y > shoulder_y + 0.25:
            return False
        return True

    def _check_p2(self, lm, w: int, h: int) -> tuple:
        """
        T-Pose Breathe check + feedback.
        State: T_POS → FORWARD → (back to T_POS = 1 rep)

        T_POS  : arms out to sides at shoulder height (Image 2)
        FORWARD: hands brought forward and together at chest (Image 1)
        """
        if not visible(lm, 11, 12, 15, 16):
            return (False, None)

        # Arm straightness check only in T_POS state
        if self._p2_state == "T_POS":
            ls  = px(lm, 11, w, h)
            rs  = px(lm, 12, w, h)
            le  = px(lm, 13, w, h)
            re  = px(lm, 14, w, h)
            lwr = px(lm, 15, w, h)
            rwr = px(lm, 16, w, h)
            if visible(lm, 13, 15) and angle(ls, le, lwr) < 140:
                return (True, "Keep left arm straight")
            if visible(lm, 14, 16) and angle(rs, re, rwr) < 140:
                return (True, "Keep right arm straight")

            if self._is_t_pose(lm, w, h):
                return (False, f"Good T-pose — now bring hands forward together  {self.rep_count} / 5")
            # Guide user into T-pose
            sw  = shoulder_width(lm, w, h)
            lwr = px(lm, 15, w, h)
            rwr = px(lm, 16, w, h)
            gap = dist(lwr, rwr) / sw
            if gap < 1.5:
                return (False, "Spread arms wide to shoulder height — T-position")
            return (False, "Raise arms to shoulder height")

        else:  # FORWARD state
            if self._is_forward_together(lm, w, h):
                return (False, f"Hands together — now return arms to T-position  {self.rep_count} / 5")
            return (False, "Bring both hands forward and together at chest")

    def _rep_p2(self, lm, w: int, h: int):
        """
        Rep state machine:
          T_POS   → hands come FORWARD (wrists close together at chest)
          FORWARD → hands go back OUT to T-pose → rep_count += 1
        """
        if self._p2_state == "T_POS":
            if self._is_forward_together(lm, w, h):
                self._p2_state = "FORWARD"

        elif self._p2_state == "FORWARD":
            if self._is_t_pose(lm, w, h):
                self._p2_state        = "T_POS"
                self._p2_forward_once = False
                self.rep_count       += 1

    # ─────────────────────────────────────────────────────────────────────
    # EXERCISES 3-8: WRIST ROTATIONS
    # ─────────────────────────────────────────────────────────────────────

    def _check_rotation(self, lm, w: int, h: int, phase: dict) -> tuple:
        side = phase.get("side", "right")
        done = self.rep_count

        if side in ("right", "both"):
            if visible(lm, 12, 14, 16, 24):
                rs  = px(lm, 12, w, h)
                re  = px(lm, 14, w, h)
                rwr = px(lm, 16, w, h)
                rh  = px(lm, 24, w, h)
                sw  = shoulder_width(lm, w, h)
                if dist(rwr, rh) / sw < 0.20:
                    return (True, "Extend right arm further out")
                if angle(rs, re, rwr) < 90:
                    return (True, "Straighten your right arm")
                if not self._tw_r.is_moving():
                    return (False, f"Rotate right hand  {done} / 5")

        if side in ("left", "both"):
            if visible(lm, 11, 13, 15, 23):
                ls  = px(lm, 11, w, h)
                le  = px(lm, 13, w, h)
                lwr = px(lm, 15, w, h)
                lh  = px(lm, 23, w, h)
                sw  = shoulder_width(lm, w, h)
                if dist(lwr, lh) / sw < 0.20:
                    return (True, "Extend left arm further out")
                if angle(ls, le, lwr) < 90:
                    return (True, "Straighten your left arm")
                if not self._tw_l.is_moving():
                    return (False, f"Rotate left hand  {done} / 5")

        return (False, f"Good — keep rotating  {done} / 5")

    def _rep_rotation(self, phase: dict):
        side   = phase.get("side", "right")
        target = phase.get("target", 5)

        if side == "right":
            c = self._tw_r.cycle_count()
            n = c - self._last_cyc_r
            if n > 0:
                self.rep_count   = min(self.rep_count + n, target)
                self._last_cyc_r = c

        elif side == "left":
            c = self._tw_l.cycle_count()
            n = c - self._last_cyc_l
            if n > 0:
                self.rep_count   = min(self.rep_count + n, target)
                self._last_cyc_l = c

        elif side == "both":
            cr = self._tw_r.cycle_count()
            cl = self._tw_l.cycle_count()
            n  = max(cr - self._last_cyc_r, cl - self._last_cyc_l)
            if n > 0:
                self.rep_count   = min(self.rep_count + n, target)
                self._last_cyc_r = cr
                self._last_cyc_l = cl

    # ─────────────────────────────────────────────────────────────────────
    # EXERCISE 9: ARM SWINGS
    # ─────────────────────────────────────────────────────────────────────

    def _check_swings(self, lm, w: int, h: int) -> tuple:
        if not visible(lm, 11, 12, 15, 16, 27, 28):
            return (False, None)
        if abs(lm[27].y - lm[28].y) < 0.03:
            return (False, "Step right leg forward first")
        done = self.rep_count
        if not self._tw_l.is_moving() and not self._tw_r.is_moving():
            return (False, f"Swing arms in big circles  {done} / 10")
        return (False, f"Keep swinging  {done} / 10")

    def _rep_swings(self, lm, w: int, h: int):
        ls_y    = lm[11].y
        is_down = lm[15].y > ls_y + 0.20 or lm[16].y > ls_y + 0.20
        if is_down and not self._arms_down:
            self._arms_down = True
            self.rep_count  = min(self.rep_count + 1, 10)
        elif not is_down:
            self._arms_down = False

    # ─────────────────────────────────────────────────────────────────────
    # EXERCISE 10: TORSO ROTATION
    # ─────────────────────────────────────────────────────────────────────

    def _check_torso(self, lm, w: int, h: int) -> tuple:
        if not visible(lm, 11, 12, 15, 16):
            return (False, None)
        lwr = px(lm, 15, w, h)
        rwr = px(lm, 16, w, h)
        if dist(lwr, rwr) > 40:
            return (False, "Bring thumbs together at chest")
        if abs(lm[15].y - lm[11].y) > 0.15:
            return (True, "Raise arms to shoulder height")
        if not self._ts_l.is_moving():
            return (False, f"Rotate torso right then left  {self.rep_count} / 3")
        return (False, f"Rotating  {self.rep_count} / 3")

    def _rep_torso(self, lm, w: int, h: int):
        gap = abs(lm[11].x - lm[12].x)
        if self._torso_baseline_gap is None:
            self._torso_baseline_gap = gap
        is_rotated = gap < self._torso_baseline_gap * 0.85
        if is_rotated and not self._torso_rotated:
            self._torso_rotated = True
        elif not is_rotated and self._torso_rotated:
            self._torso_rotated = False
            self.rep_count = min(self.rep_count + 1, 3)

    # ─────────────────────────────────────────────────────────────────────
    # EXERCISE 11: KNEE ROTATION
    # ─────────────────────────────────────────────────────────────────────

    def _check_knee(self, lm, w: int, h: int) -> tuple:
        if not visible(lm, 23, 24, 25, 26, 27, 28, 15, 16):
            return (False, None)
        lk  = px(lm, 25, w, h)
        rk  = px(lm, 26, w, h)
        lwr = px(lm, 15, w, h)
        rwr = px(lm, 16, w, h)
        if dist(lwr, lk) > 100 or dist(rwr, rk) > 100:
            return (False, "Place both hands on your knees")
        done = self.rep_count
        if not self._tk_l.is_moving() and not self._tk_r.is_moving():
            return (False, f"Rotate knees in circles  {done} / 3")
        return (False, f"Rotating  {done} / 3")

    def _rep_knee(self):
        c = self._tk_l.cycle_count()
        n = c - self._last_cyc_k
        if n > 0:
            self.rep_count   = min(self.rep_count + n, 3)
            self._last_cyc_k = c