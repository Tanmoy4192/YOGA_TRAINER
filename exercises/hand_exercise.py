"""
exercises/hand_exercise.py — Hand Exercises
FIXES:
  1. _check_p1 RAISE: arms mid-raise = guidance not error (is_error=False)
  2. _at_rest uses normalized coords not pixel offset
  3. _check_rotation: remove wrong height guard, check arm is extended instead
  4. All check methods return (is_error, message) correctly
"""

import math
from core.base_controller import BaseController
from core.utils import calculate_angle, dist, lm_px
from core.motion_tracker import MotionTracker
from core.breath_detector import BreathDetector

EXERCISE_KEY = "hand"

_PHASES = [
    {
        "id": "p1_arms_up",
        "name": "Raise Arms Overhead",
        "start": 0,   "active": 22,  "end": 185,
        "target": 3,
        "watch_msg": "Watch — arms up, palms joined overhead",
        "check_landmarks": [11,12,13,14,15,16],
    },
    {
        "id": "p2_t_pose",
        "name": "T-Pose Breathe",
        "start": 185, "active": 205, "end": 270,
        "target": 5,
        "watch_msg": "Watch — arms wide on inhale, palms front on exhale",
        "check_landmarks": [11,12,13,14,15,16],
    },
    {
        "id": "p3a_rot_right",
        "name": "Right Hand CW Rotation",
        "start": 270, "active": 300, "end": 335,
        "target": 5,
        "watch_msg": "Watch — right hand rotating clockwise",
        "check_landmarks": [12,14,16],
        "side": "right",
    },
    {
        "id": "p3b_rot_left",
        "name": "Left Hand CW Rotation",
        "start": 335, "active": 338, "end": 372,
        "target": 5,
        "watch_msg": "Watch — left hand rotating clockwise",
        "check_landmarks": [11,13,15],
        "side": "left",
    },
    {
        "id": "p3c_rot_right_ccw",
        "name": "Right Hand CCW Rotation",
        "start": 372, "active": 375, "end": 393,
        "target": 5,
        "watch_msg": "Watch — right hand anti-clockwise",
        "check_landmarks": [12,14,16],
        "side": "right",
    },
    {
        "id": "p3d_rot_left_ccw",
        "name": "Left Hand CCW Rotation",
        "start": 393, "active": 396, "end": 414,
        "target": 5,
        "watch_msg": "Watch — left hand anti-clockwise",
        "check_landmarks": [11,13,15],
        "side": "left",
    },
    {
        "id": "p3e_both_cw",
        "name": "Both Hands CW Rotation",
        "start": 414, "active": 417, "end": 435,
        "target": 5,
        "watch_msg": "Watch — both hands clockwise together",
        "check_landmarks": [11,12,13,14,15,16],
        "side": "both",
    },
    {
        "id": "p3f_both_ccw",
        "name": "Both Hands CCW Rotation",
        "start": 435, "active": 438, "end": 450,
        "target": 5,
        "watch_msg": "Watch — both hands anti-clockwise",
        "check_landmarks": [11,12,13,14,15,16],
        "side": "both",
    },
    {
        "id": "p4_arm_swing",
        "name": "Arm Swing (Foot Forward)",
        "start": 450, "active": 455, "end": 515,
        "target": 10,
        "watch_msg": "Watch — one foot forward, swing arms in circles",
        "check_landmarks": [11,12,15,16,27,28],
    },
    {
        "id": "p5_zoom",
        "name": "Finger Exercise",
        "start": 515, "active": 515, "end": 540,
        "target": 0,
        "zoom": True,
        "watch_msg": "Watch the finger exercise closely",
    },
    {
        "id": "p5_torso",
        "name": "Upper Body Rotation",
        "start": 540, "active": 543, "end": 603,
        "target": 5,
        "watch_msg": "Watch — feet 8 inches apart, thumbs touch, rotate body",
        "check_landmarks": [11,12,23,24,27,28],
    },
    {
        "id": "p6_knee",
        "name": "Knee Rotation",
        "start": 603, "active": 606, "end": 651,
        "target": 9,
        "watch_msg": "Watch — feet 3 inches, hands on knees, rotate",
        "check_landmarks": [25,26,27,28],
        "side": "knees",
    },
]


class WorkoutController(BaseController):

    def __init__(self):
        super().__init__()
        self._tw_l = MotionTracker(1.5, 12)
        self._tw_r = MotionTracker(1.5, 12)
        self._tk_l = MotionTracker(2.0, 10)
        self._tk_r = MotionTracker(2.0, 10)
        self._ts_l = MotionTracker(2.0, 15)
        self._ts_r = MotionTracker(2.0, 15)
        self._breath       = BreathDetector(min_breath_sec=2.0)
        self._p1_state     = "RAISE"
        self._p1_hold_b    = 0
        self._p1_rest_b    = 0
        self._last_cyc_l   = 0
        self._last_cyc_r   = 0
        self._last_cyc_k   = 0
        self._sw_baseline  = None
        self._p2_sub       = "CLOSE"
        self._arm_swing_ph = "DOWN"
        self._torso_ph     = "CENTER"

    def phases(self) -> list:
        return _PHASES

    def on_phase_change(self, phase: dict):
        for t in [self._tw_l, self._tw_r, self._tk_l,
                  self._tk_r, self._ts_l, self._ts_r]:
            t.reset()
        self._breath.reset()
        self._p1_state     = "RAISE"
        self._p1_hold_b    = 0
        self._p1_rest_b    = 0
        self._last_cyc_l   = 0
        self._last_cyc_r   = 0
        self._last_cyc_k   = 0
        self._sw_baseline  = None
        self._p2_sub       = "CLOSE"
        self._arm_swing_ph = "DOWN"
        self._torso_ph     = "CENTER"

    @property
    def current_phase_name(self) -> str:
        p = self._get_phase(self._video_pos)
        return p["name"] if p else "Hand Exercises"

    @property
    def coach_state(self) -> str:
        return self._coach_state

    def _track(self, lm, w, h):
        """Update all trackers. Called first inside check_pose."""
        self._tw_l.update(lm[15].x*w, lm[15].y*h)
        self._tw_r.update(lm[16].x*w, lm[16].y*h)
        self._tk_l.update(lm[25].x*w, lm[25].y*h)
        self._tk_r.update(lm[26].x*w, lm[26].y*h)
        self._ts_l.update(lm[11].x*w, lm[11].y*h)
        self._ts_r.update(lm[12].x*w, lm[12].y*h)
        self._breath.update((lm[11].y + lm[12].y) / 2)

    # ── check_pose dispatcher ─────────────────────────────────────────
    def check_pose(self, user_lm, ref_lm, w, h, phase) -> tuple:
        self._track(user_lm, w, h)   # always update trackers first
        pid = phase["id"]
        if pid == "p1_arms_up":               return self._check_p1(user_lm, w, h)
        elif pid == "p2_t_pose":              return self._check_p2(user_lm, w, h)
        elif pid.startswith("p3"):            return self._check_rotation(user_lm, w, h, phase)
        elif pid == "p4_arm_swing":           return self._check_arm_swing(user_lm, w, h)
        elif pid == "p5_torso":               return self._check_torso(user_lm, w, h)
        elif pid == "p6_knee":                return self._check_knee(user_lm, w, h)
        return False, None

    # ── detect_rep dispatcher ─────────────────────────────────────────
    def detect_rep(self, user_lm, w, h):
        p = self._get_phase(self._video_pos)
        if not p: return
        pid = p["id"]
        if pid == "p1_arms_up":               self._rep_p1(user_lm, w, h)
        elif pid == "p2_t_pose":              self._rep_p2(user_lm, w, h)
        elif pid.startswith("p3"):            self._rep_rotation(p)
        elif pid == "p4_arm_swing":           self._rep_arm_swing(user_lm, w, h)
        elif pid == "p5_torso":               self._rep_torso(user_lm, w, h)
        elif pid == "p6_knee":                self._rep_knee()

    # ══════════════════════════════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════════════════════════════
    def _arms_up_ok(self, lm, w, h):
        """Returns (ok, error_msg). Uses normalized coords for stability."""
        ls  = lm_px(lm,11,w,h); rs  = lm_px(lm,12,w,h)
        le  = lm_px(lm,13,w,h); re  = lm_px(lm,14,w,h)
        lwr = lm_px(lm,15,w,h); rwr = lm_px(lm,16,w,h)
        nose_y = lm[0].y * h
        if calculate_angle(ls,le,lwr) < 155: return False,"Straighten your left arm"
        if calculate_angle(rs,re,rwr) < 155: return False,"Straighten your right arm"
        if lwr[1] > nose_y:                  return False,"Raise left arm above your head"
        if rwr[1] > nose_y:                  return False,"Raise right arm above your head"
        if dist(lwr,rwr) > w*0.09:           return False,"Join both palms together"
        return True, None

    def _at_rest(self, lm) -> bool:
        """
        FIX: use normalized y coords (0-1 range) not pixel offset.
        Arms at rest = wrists below hips in normalized coords.
        """
        return lm[15].y > lm[23].y and lm[16].y > lm[23].y

    def _arms_mid_raise(self, lm) -> bool:
        """Arms between rest and fully raised — user is in the process of raising."""
        lw_y = lm[15].y; rw_y = lm[16].y
        lh_y = lm[23].y; nose_y = lm[0].y
        # wrists above hips but below nose = mid-raise
        l_mid = nose_y < lw_y < lh_y
        r_mid = nose_y < rw_y < lh_y
        return l_mid or r_mid

    # ══════════════════════════════════════════════════════════════════
    # PHASE 1 — Arms Overhead + breath hold
    # FIX: mid-raise = guidance (is_error=False), not an error
    # ══════════════════════════════════════════════════════════════════
    def _check_p1(self, lm, w, h) -> tuple:
        st = self._p1_state

        if st == "RAISE":
            if self._at_rest(lm):
                # arms resting — give guidance, NOT an error (don't pause video)
                return False, "Raise both arms overhead and join palms"
            if self._arms_mid_raise(lm):
                # arms on the way up — silent, let them finish
                return False, "Keep raising..."
            # arms are up somewhere — check form
            ok, err = self._arms_up_ok(lm, w, h)
            if not ok:
                return True, err    # specific form error — is_error
            return False, None      # perfect form, waiting for HOLD

        elif st == "HOLD":
            ok, err = self._arms_up_ok(lm, w, h)
            if not ok:
                # arms dropped = real error
                return True, f"Keep arms up! {err}  ({self._p1_hold_b}/4 breaths)"
            rem = 4 - self._p1_hold_b
            return False, f"Hold...  {self._p1_hold_b}/4 breaths  ({rem} more)"

        elif st == "REST":
            if not self._at_rest(lm):
                return True, f"Lower arms to rest  ({self._p1_rest_b}/2 breaths)"
            rem = 2 - self._p1_rest_b
            return False, f"Rest...  {self._p1_rest_b}/2 breaths  ({rem} more)"

        return False, None

    def _rep_p1(self, lm, w, h):
        st = self._p1_state
        if st == "RAISE":
            ok, _ = self._arms_up_ok(lm, w, h)
            if ok:
                self._p1_state  = "HOLD"
                self._p1_hold_b = 0
                self._breath.reset()
        elif st == "HOLD":
            self._p1_hold_b += self._breath.new_breaths()
            if self._p1_hold_b >= 4:
                self._p1_state  = "REST"
                self._p1_rest_b = 0
                self._breath.reset()
        elif st == "REST":
            if self._at_rest(lm):
                self._p1_rest_b += self._breath.new_breaths()
                if self._p1_rest_b >= 2:
                    self._p1_state = "RAISE"
                    self.rep_count += 1

    # ══════════════════════════════════════════════════════════════════
    # PHASE 2 — T-Pose Breathe
    # ══════════════════════════════════════════════════════════════════
    def _check_p2(self, lm, w, h) -> tuple:
        ls  = lm_px(lm,11,w,h); rs  = lm_px(lm,12,w,h)
        le  = lm_px(lm,13,w,h); re  = lm_px(lm,14,w,h)
        lwr = lm_px(lm,15,w,h); rwr = lm_px(lm,16,w,h)

        # arms below hips — need to raise
        if lm[15].y > lm[23].y and lm[16].y > lm[23].y:
            return False, "Raise arms to shoulder level to begin"

        if calculate_angle(ls,le,lwr) < 150: return True,"Keep left arm straight"
        if calculate_angle(rs,re,rwr) < 150: return True,"Keep right arm straight"

        tol = 0.10  # 10% of frame height in normalized
        if lm[15].y < lm[11].y - tol: return True,"Lower left arm to shoulder level"
        if lm[15].y > lm[11].y + tol: return True,"Raise left arm to shoulder level"
        if lm[16].y < lm[12].y - tol: return True,"Lower right arm to shoulder level"
        if lm[16].y > lm[12].y + tol: return True,"Raise right arm to shoulder level"

        wd = dist(lwr, rwr)
        if self._p2_sub == "CLOSE":
            return False, "Inhale — spread arms wide to the sides"
        else:
            if wd > w*0.45:
                return False, "Exhale — bring palms together in front"
            return False, None

    def _rep_p2(self, lm, w, h):
        if lm[15].y > lm[23].y: return
        lwr = lm_px(lm,15,w,h); rwr = lm_px(lm,16,w,h)
        wd  = dist(lwr, rwr)
        if wd > w*0.45 and self._p2_sub == "CLOSE": self._p2_sub = "WIDE"
        if wd < w*0.15 and self._p2_sub == "WIDE":
            self._p2_sub = "CLOSE"
            self.rep_count += 1

    # ══════════════════════════════════════════════════════════════════
    # PHASE 3 — Wrist Rotations
    # FIX: removed wrong height guard. Check arm is extended (elbow angle)
    # and wrist is not resting at hip.
    # ══════════════════════════════════════════════════════════════════
    def _check_rotation(self, lm, w, h, phase) -> tuple:
        side = phase.get("side","right")
        done = self.rep_count
        tgt  = phase.get("target",5)

        if side in ("right","both"):
            rs  = lm_px(lm,12,w,h); re  = lm_px(lm,14,w,h); rwr = lm_px(lm,16,w,h)
            rh  = lm_px(lm,24,w,h)
            # arm resting = wrist near hip level, skip
            arm_active = dist(rwr, rh) > w * 0.15
            if arm_active:
                ang = calculate_angle(rs,re,rwr)
                if ang < 90:
                    return True, "Extend your right arm more"
                if not self._tw_r.is_moving():
                    return True, f"Rotate right hand in circles  {done}/{tgt}"

        if side in ("left","both"):
            ls  = lm_px(lm,11,w,h); le  = lm_px(lm,13,w,h); lwr = lm_px(lm,15,w,h)
            lh  = lm_px(lm,23,w,h)
            arm_active = dist(lwr, lh) > w * 0.15
            if arm_active:
                ang = calculate_angle(ls,le,lwr)
                if ang < 90:
                    return True, "Extend your left arm more"
                if not self._tw_l.is_moving():
                    return True, f"Rotate left hand in circles  {done}/{tgt}"

        if side == "knees":
            if not self._tk_l.is_moving() and not self._tk_r.is_moving():
                return True, f"Rotate knees in circles  {done}/{tgt}"

        return False, f"Rotating...  {done}/{tgt}"

    def _rep_rotation(self, phase):
        side = phase.get("side","right")
        if side in ("right","both"):
            c = self._tw_r.cycle_count(); n = c - self._last_cyc_r
            if n > 0: self.rep_count += n; self._last_cyc_r = c
        if side == "left":
            c = self._tw_l.cycle_count(); n = c - self._last_cyc_l
            if n > 0: self.rep_count += n; self._last_cyc_l = c
        if side == "knees":
            c = self._tk_l.cycle_count(); n = c - self._last_cyc_k
            if n > 0: self.rep_count += n; self._last_cyc_k = c

    # ══════════════════════════════════════════════════════════════════
    # PHASE 4 — Arm Swing
    # ══════════════════════════════════════════════════════════════════
    def _check_arm_swing(self, lm, w, h) -> tuple:
        if abs(lm[27].y - lm[28].y) < 0.04:
            return True, "Step one foot forward first"
        if not self._tw_l.is_moving() and not self._tw_r.is_moving():
            return True, f"Swing arms in big circles  {self.rep_count}/10"
        return False, f"Swinging...  {self.rep_count}/10"

    def _rep_arm_swing(self, lm, w, h):
        lw_y = lm[15].y; ls_y = lm[11].y
        up   = lw_y < ls_y - 0.05
        if up and self._arm_swing_ph == "DOWN":   self._arm_swing_ph = "UP"
        if not up and self._arm_swing_ph == "UP":
            self._arm_swing_ph = "DOWN"; self.rep_count += 1

    # ══════════════════════════════════════════════════════════════════
    # PHASE 5 — Torso Rotation
    # ══════════════════════════════════════════════════════════════════
    def _check_torso(self, lm, w, h) -> tuple:
        ls  = lm_px(lm,11,w,h); rs  = lm_px(lm,12,w,h)
        la  = lm_px(lm,27,w,h); ra  = lm_px(lm,28,w,h)
        lwr = lm_px(lm,15,w,h); rwr = lm_px(lm,16,w,h)
        sw  = dist(ls,rs) or 1
        ratio = dist(la,ra)/sw
        if ratio < 0.10: return True,"Place feet 8 inches apart"
        if ratio > 0.65: return True,"Feet too wide — 8 inches only"
        if lm[15].y > lm[11].y + 0.10 and lm[16].y > lm[12].y + 0.10:
            return True,"Raise arms to shoulder level and touch thumbs"
        if not self._ts_l.is_moving():
            return True, f"Rotate upper body left and right  {self.rep_count}/5"
        return False, f"Rotating...  {self.rep_count}/5"

    def _rep_torso(self, lm, w, h):
        ls_x = lm[11].x*w; rs_x = lm[12].x*w; sw = abs(ls_x-rs_x)
        if self._sw_baseline is None: self._sw_baseline = sw; return
        rotated = sw < self._sw_baseline * 0.82
        if rotated and self._torso_ph == "CENTER":   self._torso_ph = "ROTATED"
        if not rotated and self._torso_ph == "ROTATED":
            self._torso_ph = "CENTER"; self.rep_count += 1

    # ══════════════════════════════════════════════════════════════════
    # PHASE 6 — Knee Rotation
    # ══════════════════════════════════════════════════════════════════
    def _check_knee(self, lm, w, h) -> tuple:
        lk  = lm_px(lm,25,w,h); rk  = lm_px(lm,26,w,h)
        lwr = lm_px(lm,15,w,h); rwr = lm_px(lm,16,w,h)
        lh  = lm_px(lm,23,w,h)
        la  = lm_px(lm,27,w,h); ra  = lm_px(lm,28,w,h)
        done = self.rep_count

        if dist(lk,rk) > w*0.13:             return True,"Bring knees together"
        if dist(la,ra) > w*0.15:             return True,"Place feet only 3 inches apart"
        km_y = (lk[1]+rk[1])/2
        wm_y = (lwr[1]+rwr[1])/2
        if abs(wm_y-km_y) > h*0.15:         return True,"Place both hands on your knees"
        if calculate_angle(lh,lk,la) > 168: return True,"Bend your knees slightly"

        if not self._tk_l.is_moving() and not self._tk_r.is_moving():
            if done < 3:   return True, f"Rotate knees clockwise  {done}/3"
            elif done < 6: return True, f"Anti-clockwise now  {done-3}/3"
            else:          return True, f"Clockwise again  {done-6}/3"

        if done < 3:   return False, f"Clockwise  {done}/3"
        elif done < 6: return False, f"Anti-clockwise  {done-3}/3"
        else:          return False, f"Clockwise  {done-6}/3"

    def _rep_knee(self):
        c = self._tk_l.cycle_count(); n = c - self._last_cyc_k
        if n > 0: self.rep_count += n; self._last_cyc_k = c