"""
exercises/leg_exercise.py — Leg Exercises
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Combined Leg Exercises 1 to 4
"""

from core.base_controller import BaseController
from core.utils import angle, dist, px

EXERCISE_KEY = "leg"

# Combined Constants
HOLD_FRAMES = 3
HOLD_FRAMES_WIPERS = 3
HOLD_FRAMES_ROTATION = 3
HOLD_FRAMES_MASSAGE = 4

_PHASES = [
    # ── POSE 1: Toe Rotation ──
    {
        "id":        "leg_p1_setup",
        "name":      "Get Into Position",
        "start":     660,
        "active":    683,
        "end":       683,
        "target":    0,
        "watch_msg": "Sit on the floor, extend both legs forward, spread them 18 inches apart, place hands behind you on the floor",
        "check_landmarks": [23, 24, 25, 26, 27, 28],
    },
    {
        "id":        "leg_p1_toe_rotation",
        "name":      "Toe Rotation  —  5 Reps",
        "start":     683,
        "active":    686,
        "end":       715,
        "target":    5,
        "watch_msg": "Watch carefully — rotate both feet inward so big toes touch down, then outward so little toes touch down",
        "check_landmarks": [23, 24, 25, 26, 27, 28],
    },

    # ── POSE 4: Windshield Wipers (Setup removed) ──
    {
        "id":        "leg_p4_wipers",
        "name":      "Windshield Wipers — 5 Reps",
        "start":     715, # 11.55 -> 715
        "active":    738, # 12.18 -> 738
        "end":       766, # 12.46 -> 766
        "target":    5,
        "watch_msg": "Rotate both feet to the left, then both feet to the right.",
        "check_landmarks": [23, 24, 25, 26, 27, 28, 31, 32],
    },

    # ── POSE 5: Ankle Rotations (Clockwise setup changed) ──
    {
        "id":        "leg_p5_ankle_rotation_cw",
        "name":      "Ankle Rotations Clockwise — 5 Reps",
        "start":     766, # 12.46 -> 766
        "active":    776, # 12.56 -> 776
        "end":       797, # 13.17 -> 797
        "target":    5,
        "watch_msg": "Draw big circles with your toes. Rotate both ankles clockwise.",
        "check_landmarks": [15, 16, 23, 24, 25, 26, 27, 28, 31, 32],
    },
    {
        "id":        "leg_p5_ankle_rotation_ccw",
        "name":      "Ankle Rotations Counter Clockwise — 5 Reps",
        "start":     797, # 13.17 -> 797
        "active":    797, # 13.17 -> 797
        "end":       822, # 13.42 -> 822
        "target":    5,
        "watch_msg": "Draw big circles with your toes. Rotate both ankles counter clockwise.",
        "check_landmarks": [23, 24, 25, 26, 27, 28, 31, 32],
    },

    # ── POSE 6: Foot Massage ──
    {
        "id":        "leg_p6_setup",
        "name":      "Get Into Position",
        "start":     825, # 13.45 -> 825
        "active":    841, # 14.01 -> 841
        "end":       841, # 14.01 -> 841
        "target":    0,
        "watch_msg": "Sit down. Keep one leg straight, bend the other, and bring that foot to your opposite knee. Grab your foot with both hands.",
        "check_landmarks": [15, 16, 23, 24, 25, 26, 27, 28, 31, 32],
    },
    {
        "id":        "leg_p6_massage",
        "name":      "Foot Massage — 10 Strokes",
        "start":     841, # 14.01 -> 841
        "active":    841, # 14.01 -> 841
        "end":       1269, # 21.09 -> 1269
        "target":    10,
        "watch_msg": "Massage your foot, sliding your hands from your toes down to your ankle, and back.",
        "check_landmarks": [15, 16, 25, 26, 27, 28, 29, 30, 31, 32],
    },
]

class WorkoutController(BaseController):

    def __init__(self):
        super().__init__()
        # State tracking POSE 1 (Toe Rotation)
        self._toe_step       = "NEUTRAL"
        self._inward_count   = 0
        self._outward_count  = 0
        self._neutral_count  = 0
        
        # State tracking POSE 4 (Wipers)
        self._wiper_state    = "NEUTRAL"
        self._w_left_count   = 0
        self._w_right_count  = 0
        self._w_center_count = 0

        # State tracking POSE 5 (Feet Rotation — left/right sweep)
        self._rot_state      = "NEUTRAL"   # NEUTRAL / LEFT / RIGHT
        self._rot_left_count  = 0
        self._rot_right_count = 0
        self._rot_center_count = 0

        # State tracking POSE 6 (Massage)
        self._massage_state  = "TOES"
        self._active_leg     = None
        self._m_toes_count   = 0
        self._m_ankle_count  = 0

    def phases(self) -> list:
        return _PHASES

    def on_phase_change(self, phase: dict):
        # Reset POSE 1
        self._toe_step       = "NEUTRAL"
        self._inward_count   = 0
        self._outward_count  = 0
        self._neutral_count  = 0
        
        # Reset POSE 4
        self._wiper_state    = "NEUTRAL"
        self._w_left_count   = 0
        self._w_right_count  = 0
        self._w_center_count = 0

        # Reset POSE 5
        self._rot_state       = "NEUTRAL"
        self._rot_left_count  = 0
        self._rot_right_count = 0
        self._rot_center_count = 0

        # Reset POSE 6
        self._massage_state  = "TOES"
        self._m_toes_count   = 0
        self._m_ankle_count  = 0
        # self._active_leg intentionally NOT reset so it carries from setup to massage

    @property
    def current_phase_name(self) -> str:
        p = self._get_phase(self._video_pos)
        return p["name"] if p else "Leg Exercises"

    @property
    def coach_state(self) -> str:
        return self._coach_state

    # ── dispatcher ───────────────────────────────────────────────────
    def check_pose(self, user_lm, w, h, phase) -> tuple:
        pid = phase["id"]
        if pid == "leg_p1_setup":
            return self._check_setup_p1(user_lm, w, h)
        elif pid == "leg_p1_toe_rotation":
            return self._check_toe_rotation(user_lm, w, h)
        elif pid == "leg_p4_wipers":
            return self._check_wipers(user_lm, w, h)
        elif pid in ["leg_p5_ankle_rotation_cw", "leg_p5_ankle_rotation_ccw"]:
            return self._check_feet_rotation(user_lm, w, h)
        elif pid == "leg_p6_setup":
            return self._check_setup_p6(user_lm, w, h)
        elif pid == "leg_p6_massage":
            return self._check_massage(user_lm, w, h)
        return False, None

    def detect_rep(self, user_lm, w, h):
        p = self._active_phase
        if not p: return
        pid = p["id"]
        
        if pid == "leg_p1_toe_rotation":
            self._rep_toe_rotation(user_lm, w, h)
        elif pid == "leg_p4_wipers":
            self._rep_wipers(user_lm, w, h)
        elif pid == "leg_p5_ankle_rotation_cw":
            self._rep_feet_rotation_cw(user_lm, w, h)
        elif pid == "leg_p5_ankle_rotation_ccw":
            self._rep_feet_rotation_ccw(user_lm, w, h)
        elif pid == "leg_p6_massage":
            self._rep_massage(user_lm, w, h)

    # ══════════════════════════════════════════════════════════════════
    # POSE 1: TOE ROTATION
    # ══════════════════════════════════════════════════════════════════
    def _check_setup_p1(self, lm, w, h) -> tuple:
        lh = px(lm, 23, w, h); rh = px(lm, 24, w, h)
        lk = px(lm, 25, w, h); rk = px(lm, 26, w, h)
        la = px(lm, 27, w, h); ra = px(lm, 28, w, h)
        lw = px(lm, 15, w, h); rw = px(lm, 16, w, h)

        if angle(lh, lk, la) < 155:
            return True, "Straighten your left leg all the way out in front of you"
        if angle(rh, rk, ra) < 155:
            return True, "Straighten your right leg all the way out in front of you"

        ankle_dist = dist(la, ra)
        hip_w      = dist(lh, rh) or 1
        ratio      = ankle_dist / hip_w
        if ratio < 1.0:
            return True, "Spread your legs a bit further — about 18 inches apart"
        if ratio > 3.5:
            return True, "Bring your legs a little closer together"

        hip_mid_x = (lh[0] + rh[0]) / 2
        if lw[0] > hip_mid_x + w * 0.15 or rw[0] < hip_mid_x - w * 0.15:
            return True, "Place both hands flat on the floor behind your hips"

        return False, "Good position — stay still and we will begin"

    def _get_foot_rotation(self, lm) -> str:
        l_ankle_vis  = lm[27].visibility
        r_ankle_vis  = lm[28].visibility
        l_foot_vis   = lm[31].visibility
        r_foot_vis   = lm[32].visibility

        if min(l_ankle_vis, r_ankle_vis, l_foot_vis, r_foot_vis) < 0.2:
            return "UNKNOWN"

        l_ankle_x = lm[27].x; r_ankle_x = lm[28].x
        l_foot_x  = lm[31].x; r_foot_x  = lm[32].x

        thr = 0.012
        l_inward  = l_foot_x < l_ankle_x - thr
        l_outward = l_foot_x > l_ankle_x + thr
        r_inward  = r_foot_x > r_ankle_x + thr
        r_outward = r_foot_x < r_ankle_x - thr

        if l_inward or r_inward: return "INWARD"
        if l_outward or r_outward: return "OUTWARD"
        return "NEUTRAL"

    def _check_toe_rotation(self, lm, w, h) -> tuple:
        lh = px(lm, 23, w, h); rh = px(lm, 24, w, h)
        lk = px(lm, 25, w, h); rk = px(lm, 26, w, h)
        la = px(lm, 27, w, h); ra = px(lm, 28, w, h)
        done = self.rep_count

        if angle(lh, lk, la) < 145: return True, "Keep your left leg straight — do not bend the knee"
        if angle(rh, rk, ra) < 145: return True, "Keep your right leg straight — do not bend the knee"

        if dist(la, ra) / (dist(lh, rh) or 1) < 0.7: return True, "Keep your legs spread apart while rotating"
        if done >= 5: return False, "Well done — you have completed all 5 repetitions"

        step = self._toe_step
        if step == "NEUTRAL": return False, f"Rotate both feet inward now — press your big toes toward the floor  {done}/5"
        elif step == "INWARD": return False, f"Good — now rotate outward, press the outer edge of your feet down  {done}/5"
        elif step == "OUTWARD": return False, f"Rep {done} complete! Rotate inward again  {done}/5"
        return False, None

    def _rep_toe_rotation(self, lm, w, h):
        rotation = self._get_foot_rotation(lm)
        if rotation == "UNKNOWN": return

        if rotation == "INWARD":
            self._inward_count  += 1
            self._outward_count  = 0
            self._neutral_count  = 0
        elif rotation == "OUTWARD":
            self._outward_count += 1
            self._inward_count   = 0
            self._neutral_count  = 0
        else:
            self._neutral_count += 1
            self._inward_count   = 0
            self._outward_count  = 0

        inward_held  = self._inward_count  >= HOLD_FRAMES
        outward_held = self._outward_count >= HOLD_FRAMES

        if self._toe_step == "NEUTRAL" and inward_held:
            self._toe_step = "INWARD"
            self._inward_count = 0
        elif self._toe_step == "INWARD" and outward_held:
            self._toe_step = "OUTWARD"
            self._outward_count = 0
            self.rep_count += 1
        elif self._toe_step == "OUTWARD" and inward_held:
            self._toe_step = "INWARD"
            self._inward_count = 0

    # ══════════════════════════════════════════════════════════════════
    # POSE 4: WIPERS
    # ══════════════════════════════════════════════════════════════════
    def _get_wiper_position(self, lm) -> str:
        if min(lm[27].visibility, lm[28].visibility, lm[31].visibility, lm[32].visibility) < 0.2: return "UNKNOWN"
        l_ankle_x = lm[27].x; r_ankle_x = lm[28].x
        l_foot_x  = lm[31].x; r_foot_x  = lm[32].x

        thr = 0.012
        l_points_left  = l_foot_x < l_ankle_x - thr
        r_points_left  = r_foot_x < r_ankle_x - thr
        l_points_right = l_foot_x > l_ankle_x + thr
        r_points_right = r_foot_x > r_ankle_x + thr

        if l_points_left or r_points_left: return "LEFT"
        if l_points_right or r_points_right: return "RIGHT"
        return "CENTER"

    def _check_wipers(self, lm, w, h) -> tuple:
        lh = px(lm, 23, w, h); rh = px(lm, 24, w, h)
        lk = px(lm, 25, w, h); rk = px(lm, 26, w, h)
        la = px(lm, 27, w, h); ra = px(lm, 28, w, h)
        done = self.rep_count

        if angle(lh, lk, la) < 145 or angle(rh, rk, ra) < 145:
            return True, "Keep your knees flat on the floor — rotate from the hips and ankles."
        if done >= 5: return False, "Great job! You have completed all 5 repetitions."

        state = self._wiper_state
        if state == "NEUTRAL": return False, f"Move both feet to point to the left  {done}/5"
        elif state == "LEFT": return False, f"Good — now move both feet to point to the right  {done}/5"
        elif state == "RIGHT": return False, f"Rep {done} complete! Move both feet to the left again  {done}/5"
        return False, None

    def _rep_wipers(self, lm, w, h):
        pos = self._get_wiper_position(lm)
        if pos == "UNKNOWN": return

        if pos == "LEFT":
            self._w_left_count   += 1
            self._w_right_count   = 0
            self._w_center_count  = 0
        elif pos == "RIGHT":
            self._w_right_count  += 1
            self._w_left_count    = 0
            self._w_center_count  = 0
        elif pos == "CENTER":
            self._w_center_count += 1
            self._w_left_count    = 0
            self._w_right_count   = 0

        left_held   = self._w_left_count >= HOLD_FRAMES_WIPERS
        right_held  = self._w_right_count >= HOLD_FRAMES_WIPERS

        if self._wiper_state == "NEUTRAL" and left_held:
            self._wiper_state = "LEFT"
            self._w_left_count = 0
        elif self._wiper_state == "LEFT" and right_held:
            self._wiper_state = "RIGHT"
            self._w_right_count = 0
            self.rep_count += 1
        elif self._wiper_state == "RIGHT" and left_held:
            self._wiper_state = "LEFT"
            self._w_left_count = 0

    # ══════════════════════════════════════════════════════════════════
    # POSE 5: FEET ROTATION  (left/right sweep)
    # ══════════════════════════════════════════════════════════════════
    #
    # Detection: toe-tip (foot index, landmarks 31/32) x-position
    # relative to the ankle (landmarks 27/28).
    #
    #   LEFT ------+------ RIGHT
    #
    # Clockwise:         LEFT → RIGHT = 1 rep
    # Counter-clockwise: RIGHT → LEFT = 1 rep
    #

    def _get_foot_sweep_position(self, lm) -> str:
        """Return LEFT / RIGHT / CENTER based on foot-index vs ankle x-offset."""
        if min(lm[27].visibility, lm[28].visibility,
               lm[31].visibility, lm[32].visibility) < 0.2:
            return "UNKNOWN"

        # Average both feet for robustness
        ankle_x = (lm[27].x + lm[28].x) / 2
        foot_x  = (lm[31].x + lm[32].x) / 2

        dx  = foot_x - ankle_x
        thr = 0.006  # lowered threshold for better sensitivity

        if dx < -thr: return "LEFT"
        if dx >  thr: return "RIGHT"
        return "CENTER"

    def _check_feet_rotation(self, lm, w, h) -> tuple:
        lh = px(lm, 23, w, h); rh = px(lm, 24, w, h)
        lk = px(lm, 25, w, h); rk = px(lm, 26, w, h)
        la = px(lm, 27, w, h); ra = px(lm, 28, w, h)
        done = self.rep_count

        if angle(lh, lk, la) < 145 or angle(rh, rk, ra) < 145:
            return True, "Keep your legs straight — rotate using only your feet."
        if done >= 5:
            return False, "Excellent work! You have completed all 5 rotations."

        state = self._rot_state
        pid = self._active_phase["id"] if self._active_phase else ""

        if pid == "leg_p5_ankle_rotation_cw":
            # Clockwise: LEFT → RIGHT
            if state == "NEUTRAL":
                return False, f"Move both feet to the left  {done}/5"
            elif state == "LEFT":
                return False, f"Good — now sweep to the right  {done}/5"
            elif state == "RIGHT":
                return False, f"Rep {done} done! Move feet to the left again  {done}/5"
        else:
            # Counter-clockwise: RIGHT → LEFT
            if state == "NEUTRAL":
                return False, f"Move both feet to the right  {done}/5"
            elif state == "RIGHT":
                return False, f"Good — now sweep to the left  {done}/5"
            elif state == "LEFT":
                return False, f"Rep {done} done! Move feet to the right again  {done}/5"

        return False, None

    def _rep_feet_rotation_cw(self, lm, w, h):
        """Clockwise: LEFT → RIGHT = 1 rep."""
        pos = self._get_foot_sweep_position(lm)
        if pos == "UNKNOWN": return

        if pos == "LEFT":
            self._rot_left_count   += 1
            self._rot_right_count   = 0
            self._rot_center_count  = 0
        elif pos == "RIGHT":
            self._rot_right_count  += 1
            self._rot_left_count    = 0
            self._rot_center_count  = 0
        else:
            self._rot_center_count += 1
            self._rot_left_count    = 0
            self._rot_right_count   = 0

        left_held  = self._rot_left_count  >= HOLD_FRAMES_ROTATION
        right_held = self._rot_right_count >= HOLD_FRAMES_ROTATION

        if self._rot_state == "NEUTRAL" and left_held:
            self._rot_state = "LEFT"
            self._rot_left_count = 0
        elif self._rot_state == "LEFT" and right_held:
            self._rot_state = "RIGHT"
            self._rot_right_count = 0
            self.rep_count += 1
        elif self._rot_state == "RIGHT" and left_held:
            self._rot_state = "LEFT"
            self._rot_left_count = 0

    def _rep_feet_rotation_ccw(self, lm, w, h):
        """Counter-clockwise: RIGHT → LEFT = 1 rep."""
        pos = self._get_foot_sweep_position(lm)
        if pos == "UNKNOWN": return

        if pos == "LEFT":
            self._rot_left_count   += 1
            self._rot_right_count   = 0
            self._rot_center_count  = 0
        elif pos == "RIGHT":
            self._rot_right_count  += 1
            self._rot_left_count    = 0
            self._rot_center_count  = 0
        else:
            self._rot_center_count += 1
            self._rot_left_count    = 0
            self._rot_right_count   = 0

        left_held  = self._rot_left_count  >= HOLD_FRAMES_ROTATION
        right_held = self._rot_right_count >= HOLD_FRAMES_ROTATION

        if self._rot_state == "NEUTRAL" and right_held:
            self._rot_state = "RIGHT"
            self._rot_right_count = 0
        elif self._rot_state == "RIGHT" and left_held:
            self._rot_state = "LEFT"
            self._rot_left_count = 0
            self.rep_count += 1
        elif self._rot_state == "LEFT" and right_held:
            self._rot_state = "RIGHT"
            self._rot_right_count = 0

    # ══════════════════════════════════════════════════════════════════
    # POSE 6: FOOT MASSAGE
    # ══════════════════════════════════════════════════════════════════
    def _check_setup_p6(self, lm, w, h) -> tuple:
        lh = px(lm, 23, w, h); rh = px(lm, 24, w, h)
        lk = px(lm, 25, w, h); rk = px(lm, 26, w, h)
        la = px(lm, 27, w, h); ra = px(lm, 28, w, h)
        lw = px(lm, 15, w, h); rw = px(lm, 16, w, h)

        l_angle = angle(lh, lk, la)
        r_angle = angle(rh, rk, ra)

        # Detect which leg is bent (over the other straight leg)
        if l_angle < 130 and r_angle > 130:
            self._active_leg = "LEFT"
        elif r_angle < 130 and l_angle > 130:
            self._active_leg = "RIGHT"
        else:
            return True, "Keep one leg straight, bend the other and place it over the straight leg"

        if self._active_leg == "LEFT":
            if dist(la, rk) > w * 0.35: return True, "Rest your left foot on or near your right leg"
            active_ankle = la
        else:
            if dist(ra, lk) > w * 0.35: return True, "Rest your right foot on or near your left leg"
            active_ankle = ra

        hands_mid = ((lw[0] + rw[0]) / 2, (lw[1] + rw[1]) / 2)
        if dist(hands_mid, active_ankle) > w * 0.30:
            return True, "Bring both hands to hold your bent foot"

        return False, "Great position. Hold your foot to begin."

    def _get_massage_position(self, lm, w, h) -> str:
        if not self._active_leg: return "UNKNOWN"
        lw = px(lm, 15, w, h); rw = px(lm, 16, w, h)
        hands_mid = ((lw[0] + rw[0]) / 2, (lw[1] + rw[1]) / 2)

        if self._active_leg == "LEFT":
            ankle = px(lm, 27, w, h)
            toes  = px(lm, 31, w, h)
        else:
            ankle = px(lm, 28, w, h)
            toes  = px(lm, 32, w, h)

        dist_to_toes  = dist(hands_mid, toes)
        dist_to_ankle = dist(hands_mid, ankle)

        if dist_to_toes < dist_to_ankle * 0.65: return "TOES"
        elif dist_to_ankle < dist_to_toes * 0.65: return "ANKLE"
        return "MIDDLE"

    def _check_massage(self, lm, w, h) -> tuple:
        lw = px(lm, 15, w, h); rw = px(lm, 16, w, h)
        done = self.rep_count

        # Auto-detect active leg if setup didn't set it
        if not self._active_leg:
            lh = px(lm, 23, w, h); rh = px(lm, 24, w, h)
            lk = px(lm, 25, w, h); rk = px(lm, 26, w, h)
            la = px(lm, 27, w, h); ra = px(lm, 28, w, h)
            l_angle = angle(lh, lk, la)
            r_angle = angle(rh, rk, ra)
            if l_angle < r_angle:
                self._active_leg = "LEFT"
            else:
                self._active_leg = "RIGHT"

        if self._active_leg == "LEFT": active_ankle = px(lm, 27, w, h)
        else: active_ankle = px(lm, 28, w, h)

        hands_mid = ((lw[0] + rw[0]) / 2, (lw[1] + rw[1]) / 2)
        if dist(hands_mid, active_ankle) > w * 0.45:
            return True, "Keep your hands on your foot to massage it"

        if done >= 10: return False, "Great job! You have finished massaging this foot."

        state = self._massage_state
        if state == "TOES": return False, f"Rub down towards your ankle/heel  {done}/10"
        elif state == "ANKLE": return False, f"Rub back up towards your toes  {done}/10"
        return False, None

    def _rep_massage(self, lm, w, h):
        pos = self._get_massage_position(lm, w, h)
        if pos == "UNKNOWN" or pos == "MIDDLE": return

        if pos == "TOES":
            self._m_toes_count  += 1
            self._m_ankle_count  = 0
        elif pos == "ANKLE":
            self._m_ankle_count += 1
            self._m_toes_count   = 0

        toes_held  = self._m_toes_count >= HOLD_FRAMES_MASSAGE
        ankle_held = self._m_ankle_count >= HOLD_FRAMES_MASSAGE

        if self._massage_state == "TOES" and ankle_held:
            self._massage_state = "ANKLE"
        elif self._massage_state == "ANKLE" and toes_held:
            self._massage_state = "TOES"
            self.rep_count += 1
