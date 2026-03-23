"""
exercises/hand_exercise.py — SKY Yoga Complete Hand Exercise Controller

SEQUENCE:
  p1  Hand Raise & Hold          — raise overhead, join palms, hold, lower
  p2  T-Pose Breathe             — arms forward joined -> spread T -> return
  p3  Right Arm CW Rotation      — right arm full clockwise circles
  p4  Left Arm CW Rotation       — left arm full clockwise circles
  p5  Right Arm CCW Rotation     — right arm counter-clockwise circles
  p6  Left Arm CCW Rotation      — left arm counter-clockwise circles
  p7  Both Arms CW Rotation      — both arms clockwise together
  p8  Both Arms CCW Rotation     — both arms counter-clockwise together
  p9  Upper Body Rotation        — thumbs at shoulder, torso sweeps R then L
  p10 Knee Rotation CW           — hands on knees, rotate forward->center
  p11 Knee Rotation CCW          — hands on knees, rotate backward->center

Detection logic sourced from uploaded prototype scripts:
  arm_rotation*.py, both_arm*.py  -> single/both arm rotation detection
  sideways.py                     -> upper body sweep detection
  knee_rotation.py                -> knee forward/backward/center detection
  join_hands_front.py             -> arms joined at shoulder height
"""

import math
import time
from core.base_controller import BaseController
from core.utils import angle, dist, px, visible, shoulder_width
from core.motion_tracker import MotionTracker

EXERCISE_KEY = "hand"

# p1 timing constants
P1_HOLD_TARGET_SEC = 10.0
P1_HOLD_SHORT_SEC  = 3.0
P1_REST_TARGET_SEC = 4.0

_PHASES = [
    # ── 1. Hand Raise & Hold ──────────────────────────────────────────────
    {
        "id":     "p1_raise_hold",
        "name":   "Raise Arms & Hold",
        "start":  16 ,  "active": 55,  "end": 185,
        "target": 3,
        "watch_msg": "",
        "check_landmarks": [11, 12, 13, 14, 15, 16, 23, 24, 27, 28],
    },
    # ── 2. T-Pose Breathe ─────────────────────────────────────────────────
    {
        "id":     "p2_t_pose",
        "name":   "T-Pose Breathe",
        "start":  185, "active": 227, "end": 273,
        "target": 5,
        "watch_msg": "spread wide to T -> Arms forward joined ",
        "check_landmarks": [11, 12, 13, 14, 15, 16],
    },
    # ── 3. Right Arm CW ───────────────────────────────────────────────────
    {
        "id":     "p3_right_cw",
        "name":   "Right Arm Clockwise",
        "start":  273, "active": 283, "end": 305,
        "target": 5,
        "side":   "right",
        "watch_msg": "Right arm down at side, rotate full clockwise circles - 5 reps",
        "check_landmarks": [12, 14, 16, 24],
    },
    # ── 4. Left Arm CW ────────────────────────────────────────────────────
    {
        "id":     "p4_left_cw",
        "name":   "Left Arm Clockwise",
        "start":  305, "active": 310, "end": 330,
        "target": 5,
        "side":   "left",
        "watch_msg": "Left arm down at side, rotate full clockwise circles - 5 reps",
        "check_landmarks": [11, 13, 15, 23],
    },
    # ── 5. Right Arm CCW ──────────────────────────────────────────────────
    {
        "id":     "p5_right_ccw",
        "name":   "Right Arm Counter-Clockwise",
        "start":  330, "active": 338, "end": 358,
        "target": 5,
        "side":   "right",
        "watch_msg": "Right arm down at side, rotate full counter-clockwise circles - 5 reps",
        "check_landmarks": [12, 14, 16, 24],
    },
    # ── 6. Left Arm CCW ───────────────────────────────────────────────────
    {
        "id":     "p6_left_ccw",
        "name":   "Left Arm Counter-Clockwise",
        "start":  358, "active": 362, "end": 382,
        "target": 5,
        "side":   "left",
        "watch_msg": "Left arm down at side, rotate full counter-clockwise circles - 5 reps",
        "check_landmarks": [11, 13, 15, 23],
    },
    # ── 7. Both Arms CW ───────────────────────────────────────────────────
    {
        "id":     "p7_both_cw",
        "name":   "Both Arms Clockwise",
        "start":  382, "active": 391, "end":414,
        "target": 5,
        "side":   "both",
        "watch_msg": "Both arms down, rotate full clockwise circles together - 5 reps",
        "check_landmarks": [11, 12, 13, 14, 15, 16, 23, 24],
    },
    # ── 8. Both Arms CCW ──────────────────────────────────────────────────
    {
        "id":     "p8_both_ccw",
        "name":   "Both Arms Counter-Clockwise",
        "start":  414, "active": 419, "end": 440,
        "target": 5,
        "side":   "both",
        "watch_msg": "Both arms down, rotate full counter-clockwise circles together - 5 reps",
        "check_landmarks": [11, 12, 13, 14, 15, 16, 23, 24],
    },
    # ── 9. Forward Position CW ────────────────────────────────────────────
    {
        "id":     "p9_forward_both_cw",
        "name":   "Forward Position Both Arms CW",
        "start":  440, "active": 460, "end": 482,
        "target": 5,
        "side":   "both",
        "watch_msg": "Right foot forward, right hand forward & left hand backward, rotate both hands clockwise - 5 reps",
        "check_landmarks": [11, 12, 13, 14, 15, 16, 23, 24],
    },
    # ── 10. Forward Position CCW ──────────────────────────────────────────
    {
        "id":     "p10_forward_both_ccw",
        "name":   "Forward Position Both Arms CCW",
        "start":  482, "active": 489, "end": 510,
        "target": 5,
        "side":   "both",
        "watch_msg": "Right foot forward, right hand forward & left hand backward, rotate both hands counter-clockwise - 5 reps",
        "check_landmarks": [11, 12, 13, 14, 15, 16, 23, 24],
    },
    # ── 11. Upper Body Rotation ────────────────────────────────────────────
    {
        "id":     "p11_upper_body",
        "name":   "Upper Body Rotation",
        "start":  511, "active": 563, "end": 603,
        "target": 5,
        "watch_msg": "Arms joined forward at shoulder height, sweep right then left - 1 rep",
        "check_landmarks": [11, 12, 15, 16, 23, 24],
    },
    # ── 10. Knee Rotation CW ──────────────────────────────────────────────
    {
        "id":     "p10_knee_cw",
        "name":   "Knee Rotation Clockwise",
        "start":  603, "active": 628, "end": 637,
        "target": 3,
        "watch_msg": "Hands on knees, push knees forward then return to center - 1 rep",
        "check_landmarks": [23, 24, 25, 26, 15, 16],
    },
    # ── 11. Knee Rotation CCW ─────────────────────────────────────────────
    {
        "id":     "p11_knee_ccw",
        "name":   "Knee Rotation Counter-Clockwise",
        "start":  637, "active": 640, "end": 660,
        "target": 5,
        "watch_msg": "Hands on knees, push knees backward then return to center - 1 rep",
        "check_landmarks": [23, 24, 25, 26, 15, 16],
    },
]


class WorkoutController(BaseController):

    def __init__(self):
        super().__init__()

        # Motion trackers — wrists for arm rotation, shoulders for body sweep
        self._tw_l = MotionTracker(1.5, 12)   # left wrist
        self._tw_r = MotionTracker(1.5, 12)   # right wrist
        self._ts_l = MotionTracker(2.0, 15)   # left shoulder (body rotation)
        self._ts_r = MotionTracker(2.0, 15)   # right shoulder (body rotation)

        self._lm = None   # current landmark list stored each frame
        self._reset_all()

    # ─────────────────────────────────────────────────────────────────────────
    def _reset_all(self):
        """Reset every per-exercise state variable."""

        # p1 — raise & hold
        self._p1_state      = "REST"    # REST | UP | DOWN
        self._p1_hold_start = None
        self._p1_down_start = None
        self._p1_short_hold = False

        # p2 — T-pose breathe
        self._p2_state = "JOINED"       # JOINED | SPREAD

        # p3-p8 — arm rotation rep tracking via MotionTracker cycles
        self._last_cyc_r  = 0
        self._last_cyc_l  = 0
        # arm lengths (captured on first frame) used to verify full extension
        self._arm_len_r   = 0.0
        self._arm_len_l   = 0.0

        # p9 — upper body rotation (from sideways.py)
        self._ub_state    = "CENTER"    # CENTER | LEFT | RIGHT
        self._ub_saw_left = False       # must see LEFT then return to count rep

        # p10 — knee CW (from knee_rotation.py)
        self._knee_cw_state   = "CENTER"    # CENTER | FORWARD
        self._knee_width_base = None

        # p11 — knee CCW
        self._knee_ccw_state  = "CENTER"    # CENTER | BACKWARD

    # ─────────────────────────────────────────────────────────────────────────

    def phases(self) -> list:
        return _PHASES

    def on_phase_change(self, phase: dict):
        for t in [self._tw_l, self._tw_r, self._ts_l, self._ts_r]:
            t.reset()
        self._reset_all()

    @property
    def current_phase_name(self) -> str:
        p = self._get_phase(self._video_pos)
        return p["name"] if p else "Hand Exercises"

    # ─────────────────────────────────────────────────────────────────────────
    # MOTION TRACKERS — updated every ACTIVE frame
    # ─────────────────────────────────────────────────────────────────────────

    def _track(self, lm, w, h):
        self._tw_l.update(lm[15].x * w, lm[15].y * h)
        self._tw_r.update(lm[16].x * w, lm[16].y * h)
        self._ts_l.update(lm[11].x * w, lm[11].y * h)
        self._ts_r.update(lm[12].x * w, lm[12].y * h)

    # ─────────────────────────────────────────────────────────────────────────
    # DISPATCHERS (BaseController calls these every ACTIVE frame)
    # ─────────────────────────────────────────────────────────────────────────

    def check_pose(self, lm, w, h, phase):
        self._lm = lm
        self._track(lm, w, h)
        pid = phase["id"]

        if   pid == "p1_raise_hold":
            return self._check_p1(lm, w, h)
        elif pid == "p2_t_pose":
            return self._check_p2(lm, w, h)
        elif pid in ("p3_right_cw", "p5_right_ccw"):
            return self._check_arm_rotation(lm, w, h, "right")
        elif pid in ("p4_left_cw", "p6_left_ccw"):
            return self._check_arm_rotation(lm, w, h, "left")
        elif pid in ("p7_both_cw", "p8_both_ccw", "p9_forward_both_cw", "p10_forward_both_ccw"):
            return self._check_arm_rotation(lm, w, h, "both")
        elif pid == "p11_upper_body":
            return self._check_upper_body(lm, w, h)
        elif pid == "p10_knee_cw":
            return self._check_knee(lm, "cw")
        elif pid == "p11_knee_ccw":
            return self._check_knee(lm, "ccw")

        return (False, None)

    def detect_rep(self, lm, w, h):
        self._lm = lm
        p = self._active_phase
        if not p:
            return
        pid = p["id"]

        if   pid == "p1_raise_hold":
            self._rep_p1(lm, w, h)
        elif pid == "p2_t_pose":
            self._rep_p2(lm, w, h)
        elif pid in ("p3_right_cw", "p5_right_ccw"):
            self._rep_arm_rotation("right", p)
        elif pid in ("p4_left_cw", "p6_left_ccw"):
            self._rep_arm_rotation("left", p)
        elif pid in ("p7_both_cw", "p8_both_ccw", "p9_forward_both_cw", "p10_forward_both_ccw"):
            self._rep_arm_rotation("both", p)
        elif pid == "p11_upper_body":
            self._rep_upper_body(lm, w, h)
        elif pid == "p10_knee_cw":
            self._rep_knee_cw(lm)
        elif pid == "p11_knee_ccw":
            self._rep_knee_ccw(lm)

    # =========================================================================
    # p1 — RAISE ARMS & HOLD
    # State: REST -> UP (hold timer) -> DOWN (rest timer) -> rep counted
    # =========================================================================

    def _is_overhead_joined(self, lm, w, h) -> bool:
        """Both wrists above nose AND palms joined (< 25% shoulder width apart)."""
        if not visible(lm, 0, 15, 16):
            return False
        if lm[15].y >= lm[0].y or lm[16].y >= lm[0].y:
            return False
        sw  = shoulder_width(lm, w, h)
        gap = dist(px(lm, 15, w, h), px(lm, 16, w, h)) / (sw or 1)
        return gap < 0.25

    def _is_arms_at_sides(self, lm) -> bool:
        """Both wrists near hip level."""
        if not visible(lm, 15, 16, 23, 24):
            return False
        hip_y = (lm[23].y + lm[24].y) / 2
        return lm[15].y > hip_y and lm[16].y > hip_y

    def _check_p1(self, lm, w, h):
        if not visible(lm, 11, 12, 15, 16, 23, 24):
            return (False, None)
        if visible(lm, 27, 28):
            gap = dist(px(lm, 27, w, h), px(lm, 28, w, h))
            if gap < w * 0.08 or gap > w * 0.30:
                return (True, "Keep legs at shoulder width")

        now = time.time()
        st  = self._p1_state

        if st == "REST":
            return (False, "Raise both arms overhead and join your palms")
        if st == "UP":
            held = (now - self._p1_hold_start) if self._p1_hold_start else 0.0
            rem  = max(0.0, P1_HOLD_TARGET_SEC - held)
            if not self._is_overhead_joined(lm, w, h):
                if held < P1_HOLD_SHORT_SEC:
                    return (False, "Arms lowering — try to hold longer next time!")
                return (False, f"Good {held:.0f}s hold! Lower arms to your sides")
            return (False, f"Hold — {rem:.0f}s remaining" if rem > 0 else "Great! Now lower arms slowly")
        if st == "DOWN":
            rested = (now - self._p1_down_start) if self._p1_down_start else 0.0
            rem    = max(0.0, P1_REST_TARGET_SEC - rested)
            sfx    = "  Hold longer next time!" if self._p1_short_hold else ""
            return (False, f"Rest — {rem:.0f}s more{sfx}" if rem > 0 else f"Rep counted!{sfx} Raise again")
        return (False, None)

    def _rep_p1(self, lm, w, h):
        now = time.time()
        st  = self._p1_state

        if st == "REST":
            if self._is_overhead_joined(lm, w, h):
                self._p1_state      = "UP"
                self._p1_hold_start = now

        elif st == "UP":
            if self._p1_hold_start is None:
                self._p1_hold_start = now
            held = now - self._p1_hold_start
            if held >= P1_HOLD_TARGET_SEC:
                self._p1_state = "DOWN"; self._p1_down_start = now
                self._p1_short_hold = False; return
            if self._is_arms_at_sides(lm):
                self._p1_short_hold = held < P1_HOLD_SHORT_SEC
                self._p1_state      = "DOWN"
                self._p1_down_start = now

        elif st == "DOWN":
            if self._p1_down_start is None:
                self._p1_down_start = now; return
            if (now - self._p1_down_start) >= P1_REST_TARGET_SEC:
                self.rep_count     += 1
                self._p1_state      = "REST"
                self._p1_hold_start = None
                self._p1_down_start = None
                self._p1_short_hold = False

    # =========================================================================
    # p2 — T-POSE BREATHE
    # Source: join_hands_front.py + sideways.py
    #
    # JOINED state: arms extended straight FORWARD, palms together at
    #               shoulder height (join_hands_front detection)
    # SPREAD state: arms spread wide to T-pose (sideways left/right check)
    # Cycle: JOINED -> SPREAD -> JOINED = 1 rep
    # =========================================================================

    def _is_arms_joined_forward(self, lm, w, h) -> bool:
        """
        Both arms extended forward at shoulder height, pinkies near shoulders.
        From join_hands_front.py: pinky(17/18) within 0.18 of shoulder(11/12)
        AND elbows(13/14) also close (arms straight forward not bent).
        """
        if not visible(lm, 11, 12, 13, 14, 15, 16):
            return False
        left_reach  = math.hypot(lm[11].y - lm[17].y, lm[11].x - lm[17].x) < 0.18
        right_reach = math.hypot(lm[12].y - lm[18].y, lm[12].x - lm[18].x) < 0.18
        left_elbow  = math.hypot(lm[11].y - lm[13].y, lm[11].x - lm[17].x) < 0.18
        right_elbow = math.hypot(lm[12].y - lm[14].y, lm[12].x - lm[18].x) < 0.18
        # Also check wrists close together (palms joined)
        wrist_gap   = math.hypot(lm[15].x - lm[16].x, lm[15].y - lm[16].y)
        sw          = math.hypot(lm[11].x - lm[12].x, lm[11].y - lm[12].y) or 1
        palms_close = wrist_gap / sw < 0.40
        return left_reach and right_reach and left_elbow and right_elbow and palms_close

    def _is_arms_spread_t(self, lm) -> bool:
        """
        Arms spread to T-pose. From sideways.py:
        - Shoulders level (y diff < 0.07)
        - Left wrist clearly past left shoulder in x (> 0.1 offset)
          OR right wrist clearly past right shoulder
        - Wrists at shoulder height (from sideways correction_engine wrist_shoulder check)
        """
        if not visible(lm, 11, 12, 15, 16):
            return False
        sh_level    = math.fabs(lm[11].y - lm[12].y) < 0.07
        wrist_ht    = math.fabs(lm[15].y - lm[11].y) < 0.18
        # wrists far apart — spread > 1.5x shoulder width
        sw          = math.hypot(lm[11].x - lm[12].x, lm[11].y - lm[12].y) or 1
        wrist_gap   = math.hypot(lm[15].x - lm[16].x, lm[15].y - lm[16].y)
        spread_wide = wrist_gap / sw > 1.4
        return sh_level and wrist_ht and spread_wide

    def _check_p2(self, lm, w, h):
        if not visible(lm, 11, 12, 15, 16):
            return (False, None)
        done = self.rep_count

        if self._p2_state == "JOINED":
            if self._is_arms_joined_forward(lm, w, h):
                return (False, f"Good! Now spread arms wide to T-position  {done}/5")
            return (False, "Bring both arms straight forward, join palms at shoulder height")
        else:   # SPREAD
            if self._is_arms_spread_t(lm):
                return (False, f"Arms wide! Now return forward and join palms  {done}/5")
            return (False, "Spread arms wide out to T-position")

    def _rep_p2(self, lm, w, h):
        if self._p2_state == "JOINED":
            if self._is_arms_spread_t(lm):
                self._p2_state = "SPREAD"
        else:
            if self._is_arms_joined_forward(lm, w, h):
                self._p2_state  = "JOINED"
                self.rep_count += 1

    # =========================================================================
    # p3-p8 — ARM ROTATION (single arm and both arms)
    # Source: arm_rotation*.py, both_arm*.py
    #
    # Rep detection: arm starts DOWN at side, swings FORWARD through a full
    # arc back to DOWN = 1 rep. Tracked via:
    #   - arm_down: wrist y near hip y (arm_rotation.py: is_arms_down)
    #   - arm_up:   wrist near ear + arm fully extended (arm_rotation.py: is_arms_up)
    # A rep is counted each time the wrist completes DOWN->UP->DOWN arc.
    # MotionTracker cycle count used as fallback counter.
    # =========================================================================

    def _arm_down_right(self, lm) -> bool:
        """Right wrist at hip level. From arm_rotation_right_forward.py."""
        return math.fabs(lm[16].y - lm[24].y) < 0.07

    def _arm_down_left(self, lm) -> bool:
        """Left wrist at hip level."""
        return math.fabs(lm[15].y - lm[23].y) < 0.07

    def _arm_up_right(self, lm) -> bool:
        """
        Right arm raised overhead — wrist near right ear, arm extended.
        From arm_rotation_right_forward.py: is_arms_up()
        """
        if self._arm_len_r == 0.0:
            return False
        near_ear = math.hypot(lm[12].y - lm[8].y,
                               lm[12].x - lm[8].x) < 0.15
        extended = math.fabs(math.fabs(lm[12].y - lm[16].y)
                             - self._arm_len_r) < 0.12
        return near_ear and extended

    def _arm_up_left(self, lm) -> bool:
        """Left arm raised overhead. From arm_rotation_left_foward.py."""
        if self._arm_len_l == 0.0:
            return False
        near_ear = math.hypot(lm[11].y - lm[7].y,
                               lm[11].x - lm[7].x) < 0.15
        extended = math.fabs(math.fabs(lm[11].y - lm[15].y)
                             - self._arm_len_l) < 0.12
        return near_ear and extended

    def _check_arm_rotation(self, lm, w, h, side):
        done = self.rep_count

        # Capture arm length baseline on first frame
        if self._arm_len_r == 0.0:
            self._arm_len_r = math.fabs(lm[12].y - lm[16].y)
        if self._arm_len_l == 0.0:
            self._arm_len_l = math.fabs(lm[11].y - lm[15].y)

        if side in ("right", "both"):
            if not visible(lm, 12, 14, 16, 24):
                return (False, None)
            # Check elbow straightness during the swing
            ang = angle(px(lm, 12, w, h), px(lm, 14, w, h), px(lm, 16, w, h))
            if ang < 130:
                return (True, "Keep right arm straight during rotation")

        if side in ("left", "both"):
            if not visible(lm, 11, 13, 15, 23):
                return (False, None)
            ang = angle(px(lm, 11, w, h), px(lm, 13, w, h), px(lm, 15, w, h))
            if ang < 130:
                return (True, "Keep left arm straight during rotation")

        # Feedback based on where in the arc the arm currently is
        if side == "right":
            if self._arm_down_right(lm):
                return (False, f"Swing right arm forward and up in a full circle  {done}/5")
            if self._arm_up_right(lm):
                return (False, f"Right arm up — continue the circle back down  {done}/5")
            return (False, f"Keep rotating right arm  {done}/5")

        elif side == "left":
            if self._arm_down_left(lm):
                return (False, f"Swing left arm forward and up in a full circle  {done}/5")
            if self._arm_up_left(lm):
                return (False, f"Left arm up — continue the circle back down  {done}/5")
            return (False, f"Keep rotating left arm  {done}/5")

        else:  # both
            both_down = self._arm_down_right(lm) and self._arm_down_left(lm)
            both_up   = self._arm_up_right(lm)   and self._arm_up_left(lm)
            if both_down:
                return (False, f"Swing both arms forward and up in full circles  {done}/5")
            if both_up:
                return (False, f"Both arms up — continue circle back down  {done}/5")
            return (False, f"Keep rotating both arms  {done}/5")

    def _rep_arm_rotation(self, side, phase):
        """
        Count reps via MotionTracker cycle detection.
        Each full 360-degree wrist arc = 1 cycle = 1 rep.
        """
        if side == "right":
            c = self._tw_r.cycle_count()
            n = c - self._last_cyc_r
            if n > 0:
                self.rep_count += n
                self._last_cyc_r = c

        elif side == "left":
            c = self._tw_l.cycle_count()
            n = c - self._last_cyc_l
            if n > 0:
                self.rep_count += n
                self._last_cyc_l = c

        elif side == "both":
            # For both arms rotation we count one rep only when both wrists complete
            # a cycle together (synchronized motion, not doubled by each arm).
            c_r = self._tw_r.cycle_count()
            c_l = self._tw_l.cycle_count()
            delta_r = c_r - self._last_cyc_r
            delta_l = c_l - self._last_cyc_l

            # Count only completed cycles that both arms have done
            common = min(delta_r, delta_l)
            if common > 0:
                self.rep_count += common

            # Keep last counts synced to newest values
            self._last_cyc_r = c_r
            self._last_cyc_l = c_l


    # =========================================================================
    # p9 — UPPER BODY ROTATION
    # Source: sideways.py
    #
    # Arms joined forward at shoulder height (p2 JOINED position).
    # User sweeps torso LEFT then RIGHT (or R then L) = 1 rep.
    # Detected via wrist x-position relative to shoulders (sideways.py logic).
    #
    # left_check():  shoulders level + left wrist clearly RIGHT of left shoulder
    # right_check(): shoulders level + left wrist clearly LEFT of left shoulder
    # State: CENTER -> LEFT -> CENTER (or CENTER->RIGHT->CENTER) = 1 rep
    # =========================================================================

    def _ub_swept_left(self, lm) -> bool:
        """Torso rotated left — from sideways.py left_check()."""
        sh_level = math.fabs(lm[11].y - lm[12].y) < 0.07
        wrist_at_sh_ht = math.fabs(lm[15].y - lm[11].y) < 0.15
        wrists_joined  = math.hypot(lm[15].x - lm[16].x,
                                     lm[15].y - lm[16].y) < 0.20
        swept = (lm[15].x - lm[11].x) > 0.08   # left wrist past left shoulder
        return sh_level and wrist_at_sh_ht and wrists_joined and swept

    def _ub_swept_right(self, lm) -> bool:
        """Torso rotated right — from sideways.py right_check()."""
        sh_level = math.fabs(lm[11].y - lm[12].y) < 0.07
        wrist_at_sh_ht = math.fabs(lm[15].y - lm[11].y) < 0.15
        wrists_joined  = math.hypot(lm[15].x - lm[16].x,
                                     lm[15].y - lm[16].y) < 0.20
        swept = (lm[15].x - lm[11].x) < -0.08  # left wrist past right shoulder
        return sh_level and wrist_at_sh_ht and wrists_joined and swept

    def _ub_centered(self, lm) -> bool:
        """Arms joined forward, torso facing camera."""
        if not visible(lm, 11, 12, 15, 16):
            return False
        wrists_joined = math.hypot(lm[15].x - lm[16].x,
                                    lm[15].y - lm[16].y) < 0.20
        at_sh_ht      = math.fabs(lm[15].y - lm[11].y) < 0.15
        return wrists_joined and at_sh_ht

    def _check_upper_body(self, lm, w, h):
        if not visible(lm, 11, 12, 15, 16):
            return (False, None)

        done = self.rep_count
        st   = self._ub_state

        # Wrists must be joined at shoulder height throughout
        if not self._ub_centered(lm) and not self._ub_swept_left(lm) and not self._ub_swept_right(lm):
            return (False, "Join both wrists forward at shoulder height to start")

        if st == "CENTER":
            return (False, f"Sweep arms+torso left then right — that is 1 rep  {done}/5")
        elif st == "LEFT":
            return (False, f"Good left! Now sweep right  {done}/5")
        elif st == "RIGHT":
            return (False, f"Good right! Return to center to complete rep  {done}/5")

        return (False, f"Rotating  {done}/5")

    def _rep_upper_body(self, lm, w, h):
        """
        Rep state: CENTER -> LEFT -> RIGHT -> CENTER = 1 rep
        (or CENTER -> RIGHT -> LEFT -> CENTER = 1 rep)
        Uses sideways.py left_check / right_check logic.
        """
        st = self._ub_state

        if st == "CENTER":
            if self._ub_swept_left(lm):
                self._ub_state    = "LEFT"
                self._ub_saw_left = True
            elif self._ub_swept_right(lm):
                self._ub_state    = "RIGHT"
                self._ub_saw_left = False

        elif st == "LEFT":
            if self._ub_swept_right(lm):
                self._ub_state = "RIGHT"
            elif self._ub_centered(lm):
                # returned to center without going right — don't count
                self._ub_state = "CENTER"

        elif st == "RIGHT":
            if self._ub_centered(lm):
                # Only count rep if we saw BOTH left and right
                if self._ub_saw_left:
                    self.rep_count += 1
                self._ub_state    = "CENTER"
                self._ub_saw_left = False
            elif self._ub_swept_left(lm) and not self._ub_saw_left:
                self._ub_saw_left = True
                self._ub_state    = "LEFT"

    # =========================================================================
    # p10 — KNEE ROTATION CLOCKWISE
    # Source: knee_rotation.py
    #
    # Hands on knees -> push knees FORWARD (z increases) -> return CENTER = 1 rep
    # Uses knee_rotation.py: is_hands_on_knees, is_knees_forward, is_knees_center
    # =========================================================================

    def _hands_on_knees(self, lm) -> bool:
        """From knee_rotation.py: is_hands_on_knees()"""
        right_ok = math.hypot(lm[16].x - lm[26].x, lm[16].y - lm[26].y) < 0.08
        left_ok  = math.hypot(lm[15].x - lm[25].x, lm[15].y - lm[25].y) < 0.08
        return right_ok and left_ok

    def _knees_forward(self, lm) -> bool:
        """From knee_rotation.py: is_knees_forward()"""
        return lm[26].z > lm[24].z and lm[25].z > lm[23].z

    def _knees_backward(self, lm) -> bool:
        """From knee_rotation.py: is_knees_backward()"""
        return lm[26].z < lm[24].z and lm[25].z < lm[23].z

    def _knees_centered(self, lm) -> bool:
        """From knee_rotation.py: is_knees_center()"""
        if self._knee_width_base is None:
            return False
        cur = math.fabs(lm[25].x - lm[26].x)
        return math.fabs(cur - self._knee_width_base) < 0.05

    def _check_knee(self, lm, direction):
        if not visible(lm, 23, 24, 25, 26, 15, 16):
            return (False, None)

        if not self._hands_on_knees(lm):
            return (False, "Place both hands on your knees")

        done = self.rep_count

        if direction == "cw":
            st = self._knee_cw_state
            if st == "CENTER":
                return (False, f"Push knees forward to start rotation  {done}/3")
            elif st == "FORWARD":
                return (False, f"Knees forward — now return to center  {done}/3")
        else:
            st = self._knee_ccw_state
            if st == "CENTER":
                return (False, f"Push knees backward to start rotation  {done}/3")
            elif st == "BACKWARD":
                return (False, f"Knees backward — now return to center  {done}/3")

        return (False, f"Rotating knees  {done}/3")

    def _rep_knee_cw(self, lm):
        """CW: CENTER -> FORWARD -> CENTER = 1 rep"""
        # Capture baseline knee width once
        if self._knee_width_base is None:
            self._knee_width_base = math.fabs(lm[25].x - lm[26].x)

        st = self._knee_cw_state
        if st == "CENTER":
            if self._hands_on_knees(lm) and self._knees_forward(lm):
                self._knee_cw_state = "FORWARD"
        elif st == "FORWARD":
            if self._knees_centered(lm):
                self._knee_cw_state = "CENTER"
                self.rep_count      = min(self.rep_count + 1, 3)

    # =========================================================================
    # p11 — KNEE ROTATION COUNTER-CLOCKWISE
    # Source: knee_rotation.py
    #
    # Hands on knees -> push knees BACKWARD (z decreases) -> return CENTER = 1 rep
    # =========================================================================

    def _rep_knee_ccw(self, lm):
        """CCW: CENTER -> BACKWARD -> CENTER = 1 rep"""
        if self._knee_width_base is None:
            self._knee_width_base = math.fabs(lm[25].x - lm[26].x)

        st = self._knee_ccw_state
        if st == "CENTER":
            if self._hands_on_knees(lm) and self._knees_backward(lm):
                self._knee_ccw_state = "BACKWARD"
        elif st == "BACKWARD":
            if self._knees_centered(lm):
                self._knee_ccw_state = "CENTER"
                self.rep_count       = min(self.rep_count + 1, 3)