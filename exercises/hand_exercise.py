"""
exercises/hand_exercise.py — SKY Yoga Complete Hand Exercise Controller

SEQUENCE:
  p1  Hand Raise & Hold          — raise overhead, join palms, hold, lower
  p2  T-Pose Breathe             — arms wide T -> joined front -> back
  p3  Right Arm CW Rotation      — right arm full clockwise circles
  p4  Left Arm CW Rotation       — left arm full clockwise circles
  p5  Right Arm CCW Rotation     — right arm counter-clockwise circles
  p6  Left Arm CCW Rotation      — left arm counter-clockwise circles
  p7  Both Arms CW Rotation      — both arms clockwise together
  p8  Both Arms CCW Rotation     — both arms counter-clockwise together
  p9  Forward Position CW        — staggered stance windmill CW
  p10 Forward Position CCW       — staggered stance windmill CCW
  p11 Upper Body Rotation        — thumbs at shoulder, torso sweeps R then L
  p12 Knee Rotation CW           — hands on knees, rotate forward -> center
  p13 Knee Rotation CCW          — hands on knees, rotate backward -> center

PHILOSOPHY:
  - Red skeleton / wrong-pose fires ONLY for clearly bad form
  - Near-correct = "Good form" (green)
  - Rep counting uses relaxed thresholds so users get credit
  - Angle tolerances are generous (not lab-precision)
"""

import math
import time
from collections import deque
from core.base_controller import BaseController
from core.utils import angle, dist, px, visible, shoulder_width
from core.motion_tracker import MotionTracker

EXERCISE_KEY = "hand"

# ─────────────────────────────────────────────────────────────────────────────
# PHASE DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────

_PHASES = [
    # ── 1. Hand Raise & Hold ──────────────────────────────────────────────────
    {
        "id":     "p1_raise_hold",
        "name":   "Raise Arms & Hold",
        "start":  16,  "active": 55,  "end": 185,
        "target": 3,
        "watch_msg": "Stand tall with feet slightly apart. Inhale, raise arms and bring palms together above your head.",
        "check_landmarks": [11, 12, 13, 14, 15, 16, 23, 24, 27, 28],
    },
    # ── 2. T-Pose Breathe ─────────────────────────────────────────────────────
    {
        "id":     "p2_t_pose",
        "name":   "T-Pose Breathe",
        "start":  185, "active": 227, "end": 273,
        "target": 5,
        "watch_msg": "Spread arms wide to a T-pose, then bring them together in front of chest and back.",
        "check_landmarks": [11, 12, 13, 14, 15, 16],
    },
    # ── 3. Right Arm CW ───────────────────────────────────────────────────────
    {
        "id":     "p3_right_cw",
        "name":   "Right Arm Clockwise",
        "start":  273, "active": 283, "end": 305,
        "target": 5,
        "side":   "right",
        "watch_msg": "Keep your right arm straight, rotate it in full clockwise circles for five reps.",
        "check_landmarks": [12, 14, 16, 24],
    },
    # ── 4. Left Arm CW ────────────────────────────────────────────────────────
    {
        "id":     "p4_left_cw",
        "name":   "Left Arm Clockwise",
        "start":  305, "active": 310, "end": 330,
        "target": 5,
        "side":   "left",
        "watch_msg": "Keep your left arm straight, rotate it in full clockwise circles for five reps.",
        "check_landmarks": [11, 13, 15, 23],
    },
    # ── 5. Right Arm CCW ──────────────────────────────────────────────────────
    {
        "id":     "p5_right_ccw",
        "name":   "Right Arm Counter-Clockwise",
        "start":  330, "active": 338, "end": 358,
        "target": 5,
        "side":   "right",
        "watch_msg": "Keep your right arm straight, rotate in full counter-clockwise circles.",
        "check_landmarks": [12, 14, 16, 24],
    },
    # ── 6. Left Arm CCW ───────────────────────────────────────────────────────
    {
        "id":     "p6_left_ccw",
        "name":   "Left Arm Counter-Clockwise",
        "start":  358, "active": 362, "end": 382,
        "target": 5,
        "side":   "left",
        "watch_msg": "Left arm down at side, rotate full counter-clockwise circles — 5 reps.",
        "check_landmarks": [11, 13, 15, 23],
    },
    # ── 7. Both Arms CW ───────────────────────────────────────────────────────
    {
        "id":     "p7_both_cw",
        "name":   "Both Arms Clockwise",
        "start":  382, "active": 391, "end": 414,
        "target": 3,
        "side":   "both",
        "watch_msg": "Both arms down, rotate full clockwise circles together — 3 reps.",
        "check_landmarks": [11, 12, 13, 14, 15, 16, 23, 24],
    },
    # ── 8. Both Arms CCW ──────────────────────────────────────────────────────
    {
        "id":     "p8_both_ccw",
        "name":   "Both Arms Counter-Clockwise",
        "start":  414, "active": 419, "end": 440,
        "target": 3,
        "side":   "both",
        "watch_msg": "Both arms down, rotate full counter-clockwise circles together — 3 reps.",
        "check_landmarks": [11, 12, 13, 14, 15, 16, 23, 24],
    },
    # ── 9. Forward Position CW ────────────────────────────────────────────────
    {
        "id":     "p9_forward_both_cw",
        "name":   "Forward Position Both Arms CW",
        "start":  440, "active": 460, "end": 482,
        "target": 5,
        "side":   "both",
        "watch_msg": "Step right foot forward. Right arm forward, left arm back. Rotate both clockwise like a windmill.",
        "check_landmarks": [11, 12, 13, 14, 15, 16, 23, 24],
    },
    # ── 10. Forward Position CCW ──────────────────────────────────────────────
    {
        "id":     "p10_forward_both_ccw",
        "name":   "Forward Position Both Arms CCW",
        "start":  482, "active": 489, "end": 510,
        "target": 5,
        "side":   "both",
        "watch_msg": "Keep stance. Right arm forward, left arm back. Rotate counter-clockwise — 5 reps.",
        "check_landmarks": [11, 12, 13, 14, 15, 16, 23, 24],
    },
    # ── 11. Upper Body Rotation ───────────────────────────────────────────────
    {
        "id":     "p11_upper_body",
        "name":   "Upper Body Rotation",
        "start":  511, "active": 563, "end": 603,
        "target": 5,
        "watch_msg": "Arms joined forward at shoulder height. Sweep right then left — 1 rep.",
        "check_landmarks": [11, 12, 15, 16, 23, 24],
    },
    # ── 12. Knee Rotation CW ──────────────────────────────────────────────────
    {
        "id":     "p10_knee_cw",
        "name":   "Knee Rotation Clockwise",
        "start":  603, "active": 628, "end": 637,
        "target": 3,
        "watch_msg": "Hands on knees, push knees forward in a circle then return to center — 1 rep.",
        "check_landmarks": [23, 24, 25, 26, 15, 16],
    },
    # ── 13. Knee Rotation CCW ─────────────────────────────────────────────────
    {
        "id":     "p11_knee_ccw",
        "name":   "Knee Rotation Counter-Clockwise",
        "start":  637, "active": 640, "end": 660,
        "target": 5,
        "watch_msg": "Hands on knees, push knees backward in a circle then return to center — 1 rep.",
        "check_landmarks": [23, 24, 25, 26, 15, 16],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: smoothed angle buffer (per landmark triplet)
# ─────────────────────────────────────────────────────────────────────────────

def _smooth_angle(buf: deque, val: float) -> float:
    buf.append(val)
    return sum(buf) / len(buf)


class WorkoutController(BaseController):

    def __init__(self):
        super().__init__()

        # Motion trackers — wrists for arm rotation
        self._tw_l = MotionTracker(2.0, 10)   # left wrist
        self._tw_r = MotionTracker(2.0, 10)   # right wrist

        # Smoothing buffers for noisy angles
        self._buf_l_elbow = deque(maxlen=6)
        self._buf_r_elbow = deque(maxlen=6)

        self._lm = None
        self._reset_all()

    # ─────────────────────────────────────────────────────────────────────────

    def _reset_all(self):
        """Reset every per-exercise state variable."""

        # p1 — raise & hold
        self._p1_state = "REST"   # REST | UP | DOWN

        # p2 — T-pose breathe
        self._p2_state = "JOINED"  # JOINED | SPREAD

        # p3–p6 — single arm rotation state machines
        self._arm_state_r = "DOWN"
        self._arm_state_l = "DOWN"
        self._last_cyc_r  = 0
        self._last_cyc_l  = 0

        # p7–p8 — both arm rotation: each arm tracked independently
        # A rep counts only when BOTH arms complete their rotation cycle
        self._both_r_state = "DOWN"   # right arm zone for both-arm phases
        self._both_l_state = "DOWN"   # left arm zone for both-arm phases
        self._both_r_done  = False    # right completed current cycle
        self._both_l_done  = False    # left completed current cycle

        # p9–p10 — forward windmill: track right arm only
        self._fwd_arm_state = "DOWN"

        # p11 — upper body rotation
        self._ub_state = "CENTER"  # CENTER | LEFT | RIGHT

        # p12 — knee CW
        self._knee_cw_state    = "CENTER"   # CENTER | RIGHT | LEFT
        self._knee_cw_saw_left = False       # saw LEFT side during current cycle

        # p13 — knee CCW
        self._knee_ccw_state     = "CENTER"  # CENTER | LEFT | RIGHT
        self._knee_ccw_saw_right = False     # saw RIGHT side during current cycle

        # smoothing buffers
        self._buf_l_elbow.clear()
        self._buf_r_elbow.clear()

    # ─────────────────────────────────────────────────────────────────────────

    def phases(self) -> list:
        return _PHASES

    def on_phase_change(self, phase: dict):
        self._tw_l.reset()
        self._tw_r.reset()
        self._reset_all()

    @property
    def current_phase_name(self) -> str:
        p = self._get_phase(self._video_pos)
        return p["name"] if p else "Hand Exercises"

    # ─────────────────────────────────────────────────────────────────────────
    # MOTION TRACKER UPDATE — every ACTIVE frame
    # ─────────────────────────────────────────────────────────────────────────

    def _track(self, lm, w, h):
        self._tw_l.update(lm[15].x * w, lm[15].y * h)
        self._tw_r.update(lm[16].x * w, lm[16].y * h)

    # ─────────────────────────────────────────────────────────────────────────
    # DISPATCHERS (called every ACTIVE frame by BaseController)
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
            return self._check_single_arm(lm, w, h, "right")
        elif pid in ("p4_left_cw", "p6_left_ccw"):
            return self._check_single_arm(lm, w, h, "left")
        elif pid in ("p7_both_cw", "p8_both_ccw"):
            return self._check_both_arms(lm, w, h)
        elif pid in ("p9_forward_both_cw", "p10_forward_both_ccw"):
            return self._check_forward_position(lm, w, h)
        elif pid == "p11_upper_body":
            return self._check_upper_body(lm, w, h)
        elif pid == "p10_knee_cw":
            return self._check_knee(lm, w, h)
        elif pid == "p11_knee_ccw":
            return self._check_knee(lm, w, h)

        return (False, "Good form - keep going")

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
            is_cw = "cw" in pid
            self._rep_single_arm(lm, "right", is_cw, self._arm_state_r,
                                 lambda s: setattr(self, "_arm_state_r", s))
        elif pid in ("p4_left_cw", "p6_left_ccw"):
            is_cw = "cw" in pid
            self._rep_single_arm(lm, "left", is_cw, self._arm_state_l,
                                 lambda s: setattr(self, "_arm_state_l", s))
        elif pid in ("p7_both_cw", "p8_both_ccw"):
            self._rep_both_arms()
        elif pid in ("p9_forward_both_cw", "p10_forward_both_ccw"):
            is_cw = "cw" in pid
            self._rep_forward(lm, is_cw)
        elif pid == "p11_upper_body":
            self._rep_upper_body(lm, w, h)
        elif pid == "p10_knee_cw":
            self._rep_knee_cw(lm)
        elif pid == "p11_knee_ccw":
            self._rep_knee_ccw(lm)

    # =========================================================================
    # p1 — RAISE ARMS & HOLD
    # REST -> UP -> DOWN -> REST = 1 rep
    #
    # LENIENT: wrists above nose level = "overhead", elbow >= 130° (not 160°)
    #          wrist gap < 0.5 shoulder widths (very relaxed)
    # =========================================================================

    def _is_overhead(self, lm, w, h) -> bool:
        """Wrists clearly above shoulders (above nose is ideal but not required)."""
        if not visible(lm, 11, 12, 15, 16):
            return False
        # Wrists must be above shoulder line (lower y = higher on screen)
        left_ok  = lm[15].y < lm[11].y - 0.05
        right_ok = lm[16].y < lm[12].y - 0.05
        return left_ok and right_ok

    def _is_palms_joined(self, lm, w, h) -> bool:
        """Hands are close enough to be considered 'joined'."""
        if not visible(lm, 15, 16):
            return False
        sw = shoulder_width(lm, w, h)
        gap = dist(px(lm, 15, w, h), px(lm, 16, w, h))
        return gap < (sw * 0.5)  # very lenient: half shoulder width

    def _is_arms_at_sides(self, lm, w, h) -> bool:
        """Wrists below hip level (arms lowered)."""
        if not visible(lm, 11, 12, 15, 16):
            return False
        left_ok  = lm[15].y > lm[11].y + 0.05
        right_ok = lm[16].y > lm[12].y + 0.05
        return left_ok and right_ok

    def _check_p1(self, lm, w, h):
        if not visible(lm, 11, 12, 15, 16):
            return (False, "Good form - keep going")

        if self._p1_state == "UP":
            # Only check arm form during the raised phase
            l_ang = angle(px(lm, 11, w, h), px(lm, 13, w, h), px(lm, 15, w, h))
            r_ang = angle(px(lm, 12, w, h), px(lm, 14, w, h), px(lm, 16, w, h))
            # Only flag if VERY bent (< 120°) — otherwise accept
            if l_ang < 120 or r_ang < 120:
                return (True, "Straighten your arms above your head.")

            # Check if palms are trying to be together
            sw  = shoulder_width(lm, w, h)
            gap = dist(px(lm, 15, w, h), px(lm, 16, w, h))
            if gap > sw * 0.7:
                return (True, "Bring your palms closer together.")

            return (False, "Good - arms raised! Hold the stretch.")

        return (False, "Good form - keep going")

    def _rep_p1(self, lm, w, h):
        st = self._p1_state

        if st == "REST":
            # Transition to UP when arms are clearly overhead
            if self._is_overhead(lm, w, h):
                self._p1_state = "UP"

        elif st == "UP":
            # Transition back down when arms drop below shoulder level
            if self._is_arms_at_sides(lm, w, h):
                # Count the rep as soon as arms lower — completes raise→lower cycle
                self.rep_count += 1
                self._p1_state = "REST"

    # =========================================================================
    # p2 — T-POSE BREATHE
    # JOINED (arms forward together) -> SPREAD (T-pose wide) -> JOINED = 1 rep
    #
    # LENIENT: shoulder-height tolerance 0.18 (vs old 0.10)
    #          wrist gap for "joined" < 0.45 SW, for "spread" > 1.6 SW
    # =========================================================================

    def _is_arms_joined_forward(self, lm, w, h) -> bool:
        if not visible(lm, 11, 12, 15, 16):
            return False
        sw  = shoulder_width(lm, w, h)
        gap = dist(px(lm, 15, w, h), px(lm, 16, w, h))
        return gap < (sw * 0.45)

    def _is_arms_spread_t(self, lm, w, h) -> bool:
        if not visible(lm, 11, 12, 15, 16):
            return False
        sw  = shoulder_width(lm, w, h)
        gap = dist(px(lm, 15, w, h), px(lm, 16, w, h))
        return gap > (sw * 1.6)

    def _check_p2(self, lm, w, h):
        if not visible(lm, 11, 12, 15, 16):
            return (False, "Good form - keep going")

        # Only flag if arms drop VERY far below shoulder (>0.20 normalized)
        l_drop = lm[15].y - lm[11].y
        r_drop = lm[16].y - lm[12].y
        if l_drop > 0.22 and r_drop > 0.22:
            return (True, "Raise your arms to shoulder height.")

        if self._p2_state == "SPREAD":
            return (False, "Good - arms wide! Now bring them together.")
        return (False, "Good form - keep going")

    def _rep_p2(self, lm, w, h):
        if self._p2_state == "JOINED":
            if self._is_arms_spread_t(lm, w, h):
                self._p2_state = "SPREAD"
        else:
            if self._is_arms_joined_forward(lm, w, h):
                self._p2_state = "JOINED"
                self.rep_count += 1

    # =========================================================================
    # p3–p8 — SINGLE & BOTH ARM ROTATION
    #
    # LENIENT elbow: warn only if < 130° (was 150°)
    # Rep: full cycle detection via arm angle quadrants (DOWN->FRONT->BACK->DOWN)
    # =========================================================================

    @staticmethod
    def _arm_angle_deg(lm, shoulder_idx, wrist_idx) -> float:
        """atan2 angle of wrist relative to shoulder, in degrees."""
        dx = lm[wrist_idx].x - lm[shoulder_idx].x
        dy = lm[wrist_idx].y - lm[shoulder_idx].y
        return math.degrees(math.atan2(dy, dx))

    def _check_single_arm(self, lm, w, h, side: str):
        s_idx = 11 if side == "left" else 12
        e_idx = 13 if side == "left" else 14
        w_idx = 15 if side == "left" else 16

        if not visible(lm, s_idx, e_idx, w_idx):
            return (False, "Good form — keep going")

        elbow_ang = angle(px(lm, s_idx, w, h), px(lm, e_idx, w, h), px(lm, w_idx, w, h))
        # Only flag very bent elbows
        if elbow_ang < 120:
            return (True, f"Keep your {side} arm straighter as you rotate.")

        return (False, "Good form - arm straight, keep rotating!")

    def _rep_single_arm(self, lm, side: str, is_cw: bool, state: str, set_state):
        """
        Count a rep for one arm using angle-quadrant state machine.
        Zone detection:
          DOWN  — wrist clearly below shoulder (deg 50..130)
          UP    — wrist clearly above shoulder (deg -130..-50)
        Rep fires on transition: UP → DOWN (completed a full rotation).
        Direction (is_cw) uses the same zones — direction doesn't change
        which quadrants the arm passes through, only the order.
        """
        s_idx = 11 if side == "left" else 12
        w_idx = 15 if side == "left" else 16

        if not visible(lm, s_idx, w_idx):
            return

        deg = self._arm_angle_deg(lm, s_idx, w_idx)

        if 50 <= deg <= 130:
            new_state = "DOWN"
        elif -130 <= deg <= -50:
            new_state = "UP"
        else:
            new_state = state   # keep current zone while in transition

        if state == "UP" and new_state == "DOWN":
            self.rep_count += 1

        set_state(new_state)

    def _check_both_arms(self, lm, w, h):
        """
        Strictly require BOTH arms to be actively rotating.
        Checks each wrist is moving (via MotionTracker) AND elbows are straight.
        If only one arm is moving, show a specific error.
        """
        if not visible(lm, 11, 12, 13, 14, 15, 16):
            return (False, "Good form - keep going")

        l_ang = angle(px(lm, 11, w, h), px(lm, 13, w, h), px(lm, 15, w, h))
        r_ang = angle(px(lm, 12, w, h), px(lm, 14, w, h), px(lm, 16, w, h))

        # Elbow check first
        if l_ang < 120 and r_ang < 120:
            return (True, "Straighten both arms while rotating.")
        if l_ang < 120:
            return (True, "Straighten your left arm.")
        if r_ang < 120:
            return (True, "Straighten your right arm.")

        # Check both wrists are actually moving
        r_moving = self._tw_r.is_moving()
        l_moving = self._tw_l.is_moving()

        if not r_moving and not l_moving:
            return (True, "Rotate both hands in full circles.")
        if not r_moving:
            return (True, "Rotate your right hand too — both arms must move!")
        if not l_moving:
            return (True, "Rotate your left hand too — both arms must move!")

        return (False, "Good — both arms rotating!")

    def _rep_both_arms(self):
        """
        Both-arm CW/CCW rep counter.
        A rep is counted only when BOTH arms have individually completed
        a full rotation cycle (UP → DOWN transition on each side).
        """
        r_state = self._both_r_state
        l_state = self._both_l_state
        lm = self._lm
        if lm is None:
            return

        # --- Right arm cycle detection ---
        if visible(lm, 12, 16):
            deg_r = self._arm_angle_deg(lm, 12, 16)
            if 50 <= deg_r <= 130:
                new_r = "DOWN"
            elif -130 <= deg_r <= -50:
                new_r = "UP"
            else:
                new_r = r_state

            if r_state == "UP" and new_r == "DOWN":
                self._both_r_done = True
            self._both_r_state = new_r

        # --- Left arm cycle detection ---
        if visible(lm, 11, 15):
            deg_l = self._arm_angle_deg(lm, 11, 15)
            if 50 <= deg_l <= 130:
                new_l = "DOWN"
            elif -130 <= deg_l <= -50:
                new_l = "UP"
            else:
                new_l = l_state

            if l_state == "UP" and new_l == "DOWN":
                self._both_l_done = True
            self._both_l_state = new_l

        # Count rep only when BOTH arms finished their cycle
        if self._both_r_done and self._both_l_done:
            self.rep_count += 1
            self._both_r_done = False
            self._both_l_done = False

    # =========================================================================
    # p9–p10 — FORWARD POSITION (WINDMILL) CW / CCW
    # Staggered stance + arms in opposite phase.
    # Rep = right wrist completes full rotation (same state machine as single arm).
    #
    # LENIENT: stance check skipped (MediaPipe Z is unreliable).
    #          arm-opposite check relaxed to 60° tolerance.
    # =========================================================================

    def _check_forward_position(self, lm, w, h):
        """
        p9/p10 — Staggered stance (right foot forward) is MANDATORY.
        Also checks arms are straight.
        MediaPipe: camera is typically mirrored, so right foot (28) appears
        on the LEFT side of the image (smaller x). We check the Z depth
        difference if available, but fall back to a hip-offset heuristic
        using the hip landmarks which shift forward with the stepping foot.
        """
        if not visible(lm, 11, 12, 13, 14, 15, 16):
            return (False, "Good form - keep going")

        # ── Staggered stance check ─────────────────────────────────────────
        # When the right leg steps forward the right hip (24) shifts slightly
        # forward and the right ankle (28) z-coordinate decreases (closer to cam).
        # Since z is available in MediaPipe world landmarks but NOT in normalized
        # landmarks, we use the vertical hip offset as a proxy:
        #   - stepping foot causes a slight drop in that hip landmark Y
        # More reliably: check that ankles are NOT side-by-side (x diff > threshold)
        if visible(lm, 27, 28):
            ankle_x_diff = abs(lm[27].x - lm[28].x)
            # If ankles are nearly at the same X, feet are side-by-side → wrong
            if ankle_x_diff < 0.06:
                return (True, "Step your RIGHT foot one step forward.")
        else:
            # Ankles not visible — skip stance check, check arms only
            pass

        # ── Elbow check ────────────────────────────────────────────────────
        l_ang = angle(px(lm, 11, w, h), px(lm, 13, w, h), px(lm, 15, w, h))
        r_ang = angle(px(lm, 12, w, h), px(lm, 14, w, h), px(lm, 16, w, h))

        if l_ang < 120 or r_ang < 120:
            return (True, "Keep both arms straight - rotate like a windmill.")

        return (False, "Good - windmill arms rotating!")

    def _rep_forward(self, lm, is_cw: bool):
        """Count reps by tracking right wrist full rotation."""
        if not visible(lm, 12, 16):
            return
        deg = self._arm_angle_deg(lm, 12, 16)

        if 50 <= deg <= 130:
            new_state = "DOWN"
        elif -130 <= deg <= -50:
            new_state = "UP"
        else:
            new_state = self._fwd_arm_state

        if self._fwd_arm_state == "UP" and new_state == "DOWN":
            self.rep_count += 1
        self._fwd_arm_state = new_state

    # =========================================================================
    # p11 — UPPER BODY ROTATION
    # Arms joined forward at shoulder height.
    # 1 rep = sweep from CENTER to one side AND back to CENTER.
    # Going RIGHT then back = 1 rep. Going LEFT then back = 1 rep.
    # So a full right+left sweep = 2 reps.
    # =========================================================================

    def _check_upper_body(self, lm, w, h):
        if not visible(lm, 11, 12, 15, 16):
            return (False, "Good form - keep going")

        sw  = shoulder_width(lm, w, h)
        gap = dist(px(lm, 15, w, h), px(lm, 16, w, h))

        if gap > sw * 0.7:
            return (True, "Keep your arms joined together in front.")

        return (False, "Good - keep sweeping side to side!")

    def _rep_upper_body(self, lm, w, h):
        """
        State machine: CENTER → LEFT or RIGHT → back to CENTER = 1 rep.
        Each full side-sweep (out and back) counts as 1 rep independently.
        """
        if not visible(lm, 11, 12, 15, 16):
            return

        wrist_mid_x = (lm[15].x + lm[16].x) / 2
        # Shoulder bounds — use min/max to handle mirrored camera
        sh_left  = max(lm[11].x, lm[12].x)   # left edge of shoulders on screen
        sh_right = min(lm[11].x, lm[12].x)   # right edge of shoulders on screen

        SWEEP_OUT  = 0.03   # wrist must go this far past shoulder to register a sweep
        RETURN_IN  = 0.02   # wrist must return this close to shoulder center to register return

        sh_center = (sh_left + sh_right) / 2

        st = self._ub_state

        if st == "CENTER":
            if wrist_mid_x > sh_left + SWEEP_OUT:
                self._ub_state    = "LEFT"    # swept to user's left (screen right)
            elif wrist_mid_x < sh_right - SWEEP_OUT:
                self._ub_state    = "RIGHT"   # swept to user's right (screen left)

        elif st == "LEFT":
            # Returned close enough to center
            if abs(wrist_mid_x - sh_center) < (sh_left - sh_right) * 0.4 + RETURN_IN:
                self._ub_state = "CENTER"
                self.rep_count += 1   # completed 1 sweep

        elif st == "RIGHT":
            if abs(wrist_mid_x - sh_center) < (sh_left - sh_right) * 0.4 + RETURN_IN:
                self._ub_state = "CENTER"
                self.rep_count += 1   # completed 1 sweep

    # =========================================================================
    # p12–p13 — KNEE ROTATION CW / CCW
    # Hands on knees, slight bend, rotate knees in small circles.
    #
    # Rep detection: track knee midpoint X oscillation (left→right→left = 1 rep).
    # The knee circle causes the knee midpoint to sweep left and right relative
    # to the hip midpoint. One full sweep through LEFT → RIGHT → LEFT (or vice
    # versa) = 1 rotation = 1 rep.
    #
    # LENIENT: hand-on-knee check uses generous threshold (0.20 normalized).
    # =========================================================================

    def _check_knee(self, lm, w, h):
        if not visible(lm, 25, 26, 15, 16):
            return (False, "Good form - keep going")

        lh = (lm[15].x, lm[15].y)
        rh = (lm[16].x, lm[16].y)
        lk = (lm[25].x, lm[25].y)
        rk = (lm[26].x, lm[26].y)

        l_dist = math.hypot(lh[0] - lk[0], lh[1] - lk[1])
        r_dist = math.hypot(rh[0] - rk[0], rh[1] - rk[1])

        if l_dist > 0.20 or r_dist > 0.20:
            return (True, "Place your hands firmly on your knees.")

        return (False, "Good - hands on knees, keep circling!")

    def _rep_knee_cw(self, lm):
        """
        CW knee rotation rep counter.
        Track knee-midpoint X relative to hip-midpoint X.
        A rep is counted when the knees complete a full side-to-side cycle:
        they must reach one side (RIGHT or LEFT) and then the opposite side
        before returning to CENTER.  This ensures a genuine circle is traced.

        Sequence: CENTER → RIGHT → LEFT → CENTER = 1 rep
                  (or CENTER → LEFT → RIGHT → CENTER = 1 rep)
        """
        if not visible(lm, 23, 24, 25, 26):
            return

        hip_mid_x  = (lm[23].x + lm[24].x) / 2
        knee_mid_x = (lm[25].x + lm[26].x) / 2
        offset     = knee_mid_x - hip_mid_x   # + = knees shifted right on screen

        THRESH = 0.012  # ~2.5% frame width — sensitive enough for small circles

        st = self._knee_cw_state
        if st == "CENTER":
            if offset > THRESH:
                self._knee_cw_state    = "RIGHT"
                self._knee_cw_saw_left = False
            elif offset < -THRESH:
                self._knee_cw_state    = "LEFT"
                self._knee_cw_saw_left = True   # started left — flag already set
        elif st == "RIGHT":
            if offset < -THRESH:
                # Reached the opposite side — mark it
                self._knee_cw_state    = "LEFT"
                self._knee_cw_saw_left = True
        elif st == "LEFT":
            if offset > THRESH:
                self._knee_cw_state = "RIGHT"
            elif abs(offset) <= THRESH:
                # Returned to center after visiting both sides
                if self._knee_cw_saw_left:
                    self.rep_count        += 1
                self._knee_cw_state    = "CENTER"
                self._knee_cw_saw_left = False

    def _rep_knee_ccw(self, lm):
        """
        CCW knee rotation rep counter.
        Sequence: CENTER → LEFT → RIGHT → CENTER = 1 rep
        (mirror of CW — knees go left first for CCW when viewed from front)
        """
        if not visible(lm, 23, 24, 25, 26):
            return

        hip_mid_x  = (lm[23].x + lm[24].x) / 2
        knee_mid_x = (lm[25].x + lm[26].x) / 2
        offset     = knee_mid_x - hip_mid_x

        THRESH = 0.012

        st = self._knee_ccw_state
        if st == "CENTER":
            if offset < -THRESH:
                self._knee_ccw_state     = "LEFT"
                self._knee_ccw_saw_right = False
            elif offset > THRESH:
                self._knee_ccw_state     = "RIGHT"
                self._knee_ccw_saw_right = True   # started right — flag already set
        elif st == "LEFT":
            if offset > THRESH:
                # Reached the opposite side
                self._knee_ccw_state     = "RIGHT"
                self._knee_ccw_saw_right = True
        elif st == "RIGHT":
            if offset < -THRESH:
                self._knee_ccw_state = "LEFT"
            elif abs(offset) <= THRESH:
                # Returned to center after visiting both sides
                if self._knee_ccw_saw_right:
                    self.rep_count           += 1
                self._knee_ccw_state     = "CENTER"
                self._knee_ccw_saw_right = False