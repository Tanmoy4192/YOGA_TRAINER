"""
exercises/hand_exercise.py — Complete SKY Yoga Hand Exercises

11 EXERCISES with proper state machines and geometry-based evaluation:

1. RAISE ARMS + HOLD (3 reps)
   - Legs normal width (not too wide/narrow)
   - Raise both arms, join palms (10 sec watch)
   - Hold 4 breaths
   - Lower arms 2 breaths
   - Up→Down cycle = 1 rep

2. T-POSE BREATHE (5 reps)
   - T-position (arms shoulder level, wide apart)
   - Breathe in
   - Forward + together (arms straight)
   - Back to T
   - T→Forward→T = 1 rep

3-6. WRIST ROTATIONS (5 reps each)
   - Right hand clockwise (5 reps)
   - Right hand counter-clockwise (5 reps)
   - Left hand clockwise (5 reps)
   - Left hand counter-clockwise (5 reps)

7-8. BOTH HANDS ROTATION (5 reps each)
   - Both hands together clockwise (5 reps)
   - Both hands together counter-clockwise (5 reps)

9. ARM SWINGS (5 reps CW + 5 reps CCW = 10 total)
   - Right leg forward, rotate arms clockwise
   - Down position = 1 rep
   - Then counter-clockwise 5 reps

10. TORSO ROTATION (3 reps)
    - Thumbs touching, shoulder level
    - Rotate right → front → left = 1 rep

11. KNEE ROTATION (3 reps)
    - Hands on knees
    - 3x clockwise + 3x counter-clockwise = 1 rep
"""

from core.base_controller import BaseController
from core.utils import angle, dist, px, visible, shoulder_width
from core.motion_tracker import MotionTracker
from core.breath_detector import BreathDetector

EXERCISE_KEY = "hand"

_PHASES = [
    # EXERCISE 1: RAISE ARMS + HOLD
    {
        "id": "p1_raise_hold",
        "name": "Raise Arms & Hold",
        "start": 0,
        "active": 10,
        "end": 185,
        "target": 3,
        "watch_msg": "Raise arms, join palms, hold for 4 breaths, then lower for 2 breaths",
        "check_landmarks": [11, 12, 13, 14, 15, 16, 23, 24, 27, 28],
    },
    
    # EXERCISE 2: T-POSE BREATHE
    {
        "id": "p2_t_pose",
        "name": "T-Pose Breathe",
        "start": 185,
        "active": 230,
        "end": 270,
        "target": 5,
        "watch_msg": "Raise arms upto shoulder level",
        "check_landmarks": [11, 12, 13, 14, 15, 16],
    },
    
    # EXERCISE 3: RIGHT WRIST CLOCKWISE
    {
        "id": "p3_right_cw",
        "name": "Right Hand Clockwise",
        "start": 270,
        "active": 285,
        "end": 285,
        "target": 5,
        "watch_msg": "Join right fingers, rotate your hand clockwise",
        "check_landmarks": [12, 14, 16],
    },
    # EXERCISE 5: LEFT WRIST CLOCKWISE
    {
        "id": "p5_left_cw",
        "name": "Left Hand Clockwise",
        "start": 305,
        "active": 310,
        "end": 331,
        "target": 5,
        "watch_msg": "Join left fingers, rotate clockwise",
        "check_landmarks": [11, 13, 15],
    },
    # EXERCISE 4: RIGHT WRIST COUNTER-CLOCKWISE
    {
        "id": "p4_right_ccw",
        "name": "Right Hand Counter-Clockwise",
        "start": 332,
        "active": 337,
        "end": 358,
        "target": 5,
        "watch_msg": "Right hand rotate counter-clockwise",
        "check_landmarks": [12, 14, 16],
    },
    

    
    # EXERCISE 6: LEFT WRIST COUNTER-CLOCKWISE
    {
        "id": "p6_left_ccw",
        "name": "Left Hand Counter-Clockwise",
        "start": 359,
        "active": 363,
        "end": 382,
        "target": 5,
        "watch_msg": "Left hand rotate counter-clockwise",
        "check_landmarks": [11, 13, 15],
    },
    
    # EXERCISE 7: BOTH HANDS CLOCKWISE
    {
        "id": "p7_both_cw",
        "name": "Both Hands Clockwise",
        "start": 391,
        "active": 525,
        "end": 585,
        "target": 5,
        "watch_msg": "Join both hands, rotate together clockwise",
        "check_landmarks": [11, 12, 13, 14, 15, 16],
    },
    
    # EXERCISE 8: BOTH HANDS COUNTER-CLOCKWISE
    {
        "id": "p8_both_ccw",
        "name": "Both Hands Counter-Clockwise",
        "start": 585,
        "active": 600,
        "end": 660,
        "target": 5,
        "watch_msg": "Both hands rotate together counter-clockwise",
        "check_landmarks": [11, 12, 13, 14, 15, 16],
    },
    
    # EXERCISE 9: ARM SWINGS
    {
        "id": "p9_arm_swings",
        "name": "Arm Swings (Right leg forward)",
        "start": 660,
        "active": 675,
        "end": 750,
        "target": 10,
        "watch_msg": "Step right leg forward, swing both arms in circles clockwise then counter-clockwise",
        "check_landmarks": [11, 12, 15, 16, 27, 28],
    },
    
    # EXERCISE 10: TORSO ROTATION
    {
        "id": "p10_torso",
        "name": "Torso Rotation",
        "start": 750,
        "active": 765,
        "end": 825,
        "target": 3,
        "watch_msg": "Thumbs touching at shoulder level, rotate right → front → left",
        "check_landmarks": [11, 12, 15, 16, 23, 24],
    },
    
    # EXERCISE 11: KNEE ROTATION
    {
        "id": "p11_knee",
        "name": "Knee Rotation",
        "start": 825,
        "active": 840,
        "end": 900,
        "target": 3,
        "watch_msg": "Hands on knees, rotate clockwise 3 times then counter-clockwise 3 times",
        "check_landmarks": [23, 24, 25, 26, 27, 28, 15, 16],
    },
]


class WorkoutController(BaseController):
    """Hand exercises controller with 11 complete exercises."""

    def __init__(self):
        """Initialize all state machines."""
        super().__init__()
        
        # Motion trackers for rotations
        self._tw_l = MotionTracker(1.5, 12)
        self._tw_r = MotionTracker(1.5, 12)
        self._tk_l = MotionTracker(2.0, 10)
        self._tk_r = MotionTracker(2.0, 10)
        self._ts_l = MotionTracker(2.0, 15)
        self._ts_r = MotionTracker(2.0, 15)
        
        # Breath detector
        self._breath = BreathDetector(min_breath_sec=2.0)
        
        # ─── EXERCISE 1: RAISE ARMS ─────────────────────────────────────
        self._p1_state = "RAISE"  # RAISE → HOLD → LOWER
        self._p1_hold_b = 0
        self._p1_lower_b = 0
        self._arms_raised = False
        
        # ─── EXERCISE 2: T-POSE ─────────────────────────────────────────
        self._p2_state = "T_POS"
        self._p2_forward_once = False
        
        # ─── ROTATION CYCLES ────────────────────────────────────────────
        self._last_cyc_l = 0
        self._last_cyc_r = 0
        self._last_cyc_k = 0
        
        # ─── TORSO ROTATION ─────────────────────────────────────────────
        self._torso_rotated = False
        self._torso_baseline_gap = None
        
        # ─── KNEE ROTATION ──────────────────────────────────────────────
        self._knee_cw_count = 0
        self._knee_ccw_count = 0
        
        # ─── ARM SWINGS ─────────────────────────────────────────────────
        self._swing_phase = "CW"  # CW or CCW
        self._arms_down = False
        
        # Message tracking (debounce)
        self._last_message = {}

    def phases(self) -> list:
        return _PHASES

    def on_phase_change(self, phase: dict):
        """Reset all state machines."""
        for t in [self._tw_l, self._tw_r, self._tk_l, self._tk_r, self._ts_l, self._ts_r]:
            t.reset()
        self._breath.reset()
        
        self._p1_state = "RAISE"
        self._p1_hold_b = 0
        self._p1_lower_b = 0
        self._arms_raised = False
        
        self._p2_state = "T_POS"
        self._p2_forward_once = False
        
        self._last_cyc_l = 0
        self._last_cyc_r = 0
        self._last_cyc_k = 0
        
        self._torso_rotated = False
        self._torso_baseline_gap = None
        
        self._knee_cw_count = 0
        self._knee_ccw_count = 0
        
        self._swing_phase = "CW"
        self._arms_down = False
        
        self._last_message = {}

    @property
    def current_phase_name(self) -> str:
        p = self._get_phase(self._video_pos)
        return p["name"] if p else "Hand Exercises"

    # ─────────────────────────────────────────────────────────────────────
    # TRACKERS
    # ─────────────────────────────────────────────────────────────────────

    def _track(self, lm, w: int, h: int):
        """Update all motion and breath trackers."""
        self._tw_l.update(lm[15].x * w, lm[15].y * h)
        self._tw_r.update(lm[16].x * w, lm[16].y * h)
        self._tk_l.update(lm[25].x * w, lm[25].y * h)
        self._tk_r.update(lm[26].x * w, lm[26].y * h)
        self._ts_l.update(lm[11].x * w, lm[11].y * h)
        self._ts_r.update(lm[12].x * w, lm[12].y * h)
        self._breath.update((lm[11].y + lm[12].y) / 2)

    # ─────────────────────────────────────────────────────────────────────
    # MAIN DISPATCHER
    # ─────────────────────────────────────────────────────────────────────

    def check_pose(self, user_lm, w: int, h: int, phase: dict) -> tuple:
        """Route to exercise-specific check."""
        self._track(user_lm, w, h)
        
        pid = phase["id"]
        
        if pid == "p1_raise_hold":
            return self._check_p1(user_lm, w, h)
        elif pid == "p2_t_pose":
            return self._check_p2(user_lm, w, h)
        elif pid in ["p3_right_cw", "p4_right_ccw", "p5_left_cw", "p6_left_ccw", 
                     "p7_both_cw", "p8_both_ccw"]:
            return self._check_rotation(user_lm, w, h, phase)
        elif pid == "p9_arm_swings":
            return self._check_swings(user_lm, w, h)
        elif pid == "p10_torso":
            return self._check_torso(user_lm, w, h)
        elif pid == "p11_knee":
            return self._check_knee(user_lm, w, h)
        
        return (False, None)

    def detect_rep(self, user_lm, w: int, h: int):
        """Count reps by phase."""
        p = self._get_phase(self._video_pos)
        if not p:
            return
        
        pid = p["id"]
        
        if pid == "p1_raise_hold":
            self._rep_p1(user_lm, w, h)
        elif pid == "p2_t_pose":
            self._rep_p2(user_lm, w, h)
        elif pid in ["p3_right_cw", "p4_right_ccw", "p5_left_cw", "p6_left_ccw",
                     "p7_both_cw", "p8_both_ccw"]:
            self._rep_rotation(p)
        elif pid == "p9_arm_swings":
            self._rep_swings(user_lm, w, h)
        elif pid == "p10_torso":
            self._rep_torso(user_lm, w, h)
        elif pid == "p11_knee":
            self._rep_knee()

    # ─────────────────────────────────────────────────────────────────────
    # EXERCISE 1: RAISE ARMS + HOLD (3 reps)
    # ─────────────────────────────────────────────────────────────────────

    def _check_p1(self, lm, w: int, h: int) -> tuple:
        """Raise arms, hold 4 breaths, lower 2 breaths."""
        if not visible(lm, 11, 12, 15, 16, 23, 24, 27, 28):
            return (False, None)
        
        # Check leg width: not too wide, not too narrow
        la = px(lm, 27, w, h)
        ra = px(lm, 28, w, h)
        leg_gap = dist(la, ra)
        if leg_gap < w * 0.08 or leg_gap > w * 0.30:
            return (True, "Keep legs normal width")
        
        st = self._p1_state
        
        if st == "RAISE":
            # Arms down?
            if lm[15].y > lm[23].y and lm[16].y > lm[23].y:
                return (False, "Raise both hands overhead and join palms")
            
            # Arms raised and joined?
            if lm[15].y < lm[0].y and lm[16].y < lm[0].y:
                sw = shoulder_width(lm, w, h)
                if dist(px(lm, 15, w, h), px(lm, 16, w, h)) / sw < 0.15:
                    self._arms_raised = True
                    return (False, None)
            
            if self._arms_raised:
                return (False, "Bring palms together")
            
            return (False, "Raise arms and join palms")
        
        elif st == "HOLD":
            # Check if arms still up and joined
            if lm[15].y > lm[0].y or lm[16].y > lm[0].y:
                return (True, "Keep arms above head")
            
            sw = shoulder_width(lm, w, h)
            if dist(px(lm, 15, w, h), px(lm, 16, w, h)) / sw > 0.20:
                return (True, "Keep palms joined")
            
            rem = 4 - self._p1_hold_b
            return (False, f"Hold {self._p1_hold_b}/4 breaths ({rem} more)")
        
        elif st == "LOWER":
            # Arms lowered?
            if lm[15].y < lm[23].y or lm[16].y < lm[23].y:
                return (False, "Lower arms to rest")
            
            rem = 2 - self._p1_lower_b
            return (False, f"Rest {self._p1_lower_b}/2 breaths ({rem} more)")
        
        return (False, None)

    def _rep_p1(self, lm, w: int, h: int):
        """Count breaths and state transitions."""
        st = self._p1_state
        
        if st == "RAISE":
            if lm[15].y < lm[0].y and lm[16].y < lm[0].y:
                sw = shoulder_width(lm, w, h)
                if dist(px(lm, 15, w, h), px(lm, 16, w, h)) / sw < 0.15:
                    self._p1_state = "HOLD"
                    self._breath.reset()
        
        elif st == "HOLD":
            self._p1_hold_b += self._breath.new_breaths()
            if self._p1_hold_b >= 4:
                self._p1_state = "LOWER"
                self._breath.reset()
        
        elif st == "LOWER":
            if lm[15].y > lm[23].y and lm[16].y > lm[23].y:
                self._p1_lower_b += self._breath.new_breaths()
                if self._p1_lower_b >= 2:
                    self._p1_state = "RAISE"
                    self._arms_raised = False
                    self.rep_count += 1

    # ─────────────────────────────────────────────────────────────────────
    # EXERCISE 2: T-POSE BREATHE (5 reps)
    # ─────────────────────────────────────────────────────────────────────

    def _check_p2(self, lm, w: int, h: int) -> tuple:
        """T→Forward→T = 1 rep."""
        if not visible(lm, 11, 12, 13, 14, 15, 16):
            return (False, None)
        
        lwr = px(lm, 15, w, h)
        rwr = px(lm, 16, w, h)
        ls = px(lm, 11, w, h)
        rs = px(lm, 12, w, h)
        le = px(lm, 13, w, h)
        re = px(lm, 14, w, h)
        
        # Arm angles
        l_angle = angle(ls, le, lwr)
        r_angle = angle(rs, re, rwr)
        
        if l_angle < 150:
            return (True, "Keep left arm straight")
        if r_angle < 150:
            return (True, "Keep right arm straight")
        
        # Shoulder height
        if abs(lm[15].y - lm[11].y) > 0.15:
            return (True, "Bring left arm to shoulder height")
        if abs(lm[16].y - lm[12].y) > 0.15:
            return (True, "Bring right arm to shoulder height")
        
        sw = shoulder_width(lm, w, h)
        gap = dist(lwr, rwr) / sw
        
        st = self._p2_state
        
        if st == "T_POS":
            if gap > 1.8:
                return (False, "Breathe in - keep arms wide (T)")
            return (False, "Move arms wider to T-position")
        else:  # FORWARD
            if gap < 0.30:
                return (False, "Breathe out - bring hands together forward")
            return (False, "Bring hands closer together")

    def _rep_p2(self, lm, w: int, h: int):
        """T→Forward transitions."""
        lwr = px(lm, 15, w, h)
        rwr = px(lm, 16, w, h)
        sw = shoulder_width(lm, w, h)
        gap = dist(lwr, rwr) / sw
        
        st = self._p2_state
        
        if st == "T_POS":
            if gap > 1.8:
                self._p2_state = "FORWARD"
        elif st == "FORWARD":
            if gap < 0.30:
                self._p2_forward_once = True
            if self._p2_forward_once and gap > 1.8:
                self._p2_state = "T_POS"
                self.rep_count += 1

    # ─────────────────────────────────────────────────────────────────────
    # EXERCISES 3-8: WRIST ROTATIONS (5 reps each)
    # ─────────────────────────────────────────────────────────────────────

    def _check_rotation(self, lm, w: int, h: int, phase: dict) -> tuple:
        """Wrist rotations - clockwise and counter-clockwise."""
        side = phase.get("side", "right")
        done = self.rep_count
        
        if side in ("right", "both"):
            if visible(lm, 12, 14, 16):
                rs = px(lm, 12, w, h)
                re = px(lm, 14, w, h)
                rwr = px(lm, 16, w, h)
                rh = px(lm, 24, w, h)
                
                sw = shoulder_width(lm, w, h)
                if dist(rwr, rh) / sw < 0.20:
                    return (True, "Extend right arm more")
                
                if angle(rs, re, rwr) < 90:
                    return (True, "Straighten right arm")
                
                if not self._tw_r.is_moving():
                    return (False, f"Rotate right hand {done}/5")
        
        if side in ("left", "both"):
            if visible(lm, 11, 13, 15):
                ls = px(lm, 11, w, h)
                le = px(lm, 13, w, h)
                lwr = px(lm, 15, w, h)
                lh = px(lm, 23, w, h)
                
                sw = shoulder_width(lm, w, h)
                if dist(lwr, lh) / sw < 0.20:
                    return (True, "Extend left arm more")
                
                if angle(ls, le, lwr) < 90:
                    return (True, "Straighten left arm")
                
                if not self._tw_l.is_moving():
                    return (False, f"Rotate left hand {done}/5")
        
        return (False, f"Good form {done}/5")

    def _rep_rotation(self, phase):
        """Count rotation cycles."""
        side = phase.get("side", "right")
        
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
            cr = self._tw_r.cycle_count()
            cl = self._tw_l.cycle_count()
            nr = cr - self._last_cyc_r
            nl = cl - self._last_cyc_l
            reps = max(nr, nl)
            if reps > 0:
                self.rep_count += reps
                self._last_cyc_r = cr
                self._last_cyc_l = cl

    # ─────────────────────────────────────────────────────────────────────
    # EXERCISE 9: ARM SWINGS (10 total: 5 CW + 5 CCW)
    # ─────────────────────────────────────────────────────────────────────

    def _check_swings(self, lm, w: int, h: int) -> tuple:
        """Right leg forward, swing arms."""
        if not visible(lm, 11, 12, 15, 16, 27, 28):
            return (False, None)
        
        # Right leg forward?
        if abs(lm[27].y - lm[28].y) < 0.03:
            return (False, "Step right leg forward")
        
        done = self.rep_count
        
        if not self._tw_l.is_moving() and not self._tw_r.is_moving():
            return (False, f"Swing arms {done}/10")
        
        return (False, f"Swinging {done}/10")

    def _rep_swings(self, lm, w: int, h: int):
        """Count swings (down position = 1 rep)."""
        lw_y = lm[15].y
        rw_y = lm[16].y
        ls_y = lm[11].y
        
        # Down when hands below shoulders
        is_down = lw_y > ls_y + 0.20 or rw_y > ls_y + 0.20
        
        if is_down and not self._arms_down:
            self._arms_down = True
            self.rep_count += 1
        elif not is_down:
            self._arms_down = False

    # ─────────────────────────────────────────────────────────────────────
    # EXERCISE 10: TORSO ROTATION (3 reps)
    # ─────────────────────────────────────────────────────────────────────

    def _check_torso(self, lm, w: int, h: int) -> tuple:
        """Thumbs touching, shoulder level, rotate."""
        if not visible(lm, 11, 12, 15, 16):
            return (False, None)
        
        lwr = px(lm, 15, w, h)
        rwr = px(lm, 16, w, h)
        
        # Thumbs distance
        thumb_dist = dist(lwr, rwr)
        if thumb_dist > 40:
            return (False, "Bring thumbs closer")
        
        # Shoulder height
        if abs(lm[15].y - lm[11].y) > 0.15:
            return (True, "Raise arms to shoulder height")
        
        if not self._ts_l.is_moving():
            return (False, f"Rotate torso {self.rep_count}/3")
        
        return (False, f"Rotating {self.rep_count}/3")

    def _rep_torso(self, lm, w: int, h: int):
        """Count torso rotations (shoulder gap change)."""
        ls_x = lm[11].x
        rs_x = lm[12].x
        gap = abs(ls_x - rs_x)
        
        if self._torso_baseline_gap is None:
            self._torso_baseline_gap = gap
        
        # Rotated when gap < 85% of baseline
        is_rotated = gap < self._torso_baseline_gap * 0.85
        
        if is_rotated and not self._torso_rotated:
            self._torso_rotated = True
        elif not is_rotated and self._torso_rotated:
            self._torso_rotated = False
            self.rep_count += 1

    # ─────────────────────────────────────────────────────────────────────
    # EXERCISE 11: KNEE ROTATION (3 reps)
    # ─────────────────────────────────────────────────────────────────────

    def _check_knee(self, lm, w: int, h: int) -> tuple:
        """Hands on knees, rotate."""
        if not visible(lm, 23, 24, 25, 26, 27, 28, 15, 16):
            return (False, None)
        
        lk = px(lm, 25, w, h)
        rk = px(lm, 26, w, h)
        lwr = px(lm, 15, w, h)
        rwr = px(lm, 16, w, h)
        
        # Hands on knees?
        if dist(lwr, lk) > 100 or dist(rwr, rk) > 100:
            return (False, "Place hands on knees")
        
        done = self.rep_count
        
        if not self._tk_l.is_moving() and not self._tk_r.is_moving():
            return (False, f"Rotate knees {done}/3")
        
        return (False, f"Rotating {done}/3")

    def _rep_knee(self):
        """Count knee rotations."""
        c = self._tk_l.cycle_count()
        n = c - self._last_cyc_k
        if n > 0:
            self.rep_count += n
            self._last_cyc_k = c