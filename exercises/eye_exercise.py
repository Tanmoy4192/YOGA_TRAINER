"""
exercises/eye_exercise.py — SKY Yoga Eye Exercises

7 EXERCISES with proper state machines and geometry-based evaluation:
1. Horizontal Movement (+ Sign Part 1)
2. Vertical Movement (+ Sign Part 2)
3. Diagonal (Left Lower to Right Upper)
4. Diagonal (Right Lower to Left Upper)
5. Circular Rotation (Clockwise)
6. Circular Rotation (Counter-Clockwise)
7. Near and Far (Depth Focus)
8. Palming (Relaxation)
"""
from core.base_controller import BaseController
from core.utils import angle, dist, px, visible, shoulder_width
from core.motion_tracker import MotionTracker

EXERCISE_KEY = "eye"

# Video Timestamps converted to seconds
# 24:15 = 1455s | 25:22 = 1522s | 25:59 = 1559s | 26:49 = 1609s
# 27:31 = 1651s | 28:27 = 1707s | 29:08 = 1748s | 29:30 = 1770s

_PHASES = [
    # 1. HORIZONTAL MOVEMENT
    {
        "id": "p1_horizontal",
        "name": "Horizontal Eye Movement",
        "start": 1835,        # 30:35
        "active": 1840,
        "end": 1980,          
        "target": 5,
        "watch_msg": "Clasp hands, thumbs up. Swing hands horizontally left to right.",
        "check_landmarks": [0, 11, 12, 15, 16],
    },
    # 2. VERTICAL MOVEMENT
    {
        "id": "p2_vertical",
        "name": "Vertical Eye Movement",
        "start": 1980,        # 32:03
        "active": 1982,
        "end": 1992,          
        "target": 5,
        "watch_msg": "Lift clasped hands vertically up and down. Eyes move in unison.",
        "check_landmarks": [0, 11, 12, 15, 16],
    },
    # 3. DIAGONAL (LL to RU)
    {
        "id": "p3_diag_1",
        "name": "Diagonal (Left-Low to Right-Up)",
        "start": 1992,        # 33:05
        "active": 1990,
        "end": 2037,          
        "target": 5,
        "watch_msg": "Move hands from left thigh to right shoulder diagonally.",
        "check_landmarks": [0, 11, 12, 15, 16, 23, 24], 
    },
    # 4. DIAGONAL (RL to LU)
    {
        "id": "p4_diag_2",
        "name": "Diagonal (Right-Low to Left-Up)",
        "start": 2037,        # 33:57
        "active": 2042,
        "end": 2090,          
        "target": 5,
        "watch_msg": "Move hands from right thigh to left shoulder diagonally.",
        "check_landmarks": [0, 11, 12, 15, 16, 23, 24],
    },
    # 5. CIRCULAR CLOCKWISE
    {
        "id": "p5_circle_cw",
        "name": "Circular Clockwise",
        "start": 2090,        # 34:50
        "active": 2095,
        "end": 2130,          
        "target": 5,
        "watch_msg": "Move clasped hands in a large clockwise circle.",
        "check_landmarks": [0, 11, 12, 15, 16],
    },
    # 6. CIRCULAR COUNTER-CLOCKWISE
    {
        "id": "p6_circle_ccw",
        "name": "Circular Counter-Clockwise",
        "start": 2130,        # 35:30
        "active": 2135,
        "end": 2158,          
        "target": 5,
        "watch_msg": "Move clasped hands in a large counter-clockwise circle.",
        "check_landmarks": [0, 11, 12, 15, 16],
    },
    # 7. NEAR AND FAR
    {
        "id": "p7_near_far",
        "name": "Near and Far Focus",
        "start": 2158,        # 35:58
        "active": 2163,
        "end": 2210,          
        "target": 5,
        "watch_msg": "Bring thumbs close to nose, then extend arms fully.",
        "check_landmarks": [0, 11, 12, 13, 14, 15, 16],
    },
    # 8. PALMING
    {
        "id": "p8_palming",
        "name": "Palming Relaxation",
        "start": 2210,        # 36:50
        "active": 2215,
        "end": 2260,          # Final end at 37:40
        "target": 1,
        "watch_msg": "Close eyes. Cover eyes with palms and relax.",
        "check_landmarks": [0, 1, 4, 15, 16], 
    }
]


class WorkoutController(BaseController):
    """Eye exercises controller with 8 complete phases."""

    def __init__(self):
        super().__init__()
        
        # Motion trackers for circular eye movements
        # Adjusted sensitivity: larger threshold since hands move in a big circle
        self._tw_hands = MotionTracker(2.0, 15)
        
        # State machines
        self._mov_state = "CENTER"
        self._palming_frames = 0
        self._last_cyc = 0

    def phases(self) -> list:
        return _PHASES

    def on_phase_change(self, phase: dict):
        """Reset state machines on phase transition."""
        self._tw_hands.reset()
        self._mov_state = "CENTER"
        self._palming_frames = 0
        self._last_cyc = 0

    @property
    def current_phase_name(self) -> str:
        p = self._get_phase(self._video_pos)
        return p["name"] if p else "Eye Exercises"

    def _mid_wrist(self, lm, w, h):
        """Helper to get the center point between both hands."""
        lw = px(lm, 15, w, h)
        rw = px(lm, 16, w, h)
        return ((lw[0] + rw[0]) // 2, (lw[1] + rw[1]) // 2)

    def _check_clasped(self, lm, w, h) -> tuple:
        """Helper to ensure hands stay clasped for phases 1-6."""
        lw = px(lm, 15, w, h)
        rw = px(lm, 16, w, h)
        sw = shoulder_width(lm, w, h)
        
        # If wrists are further apart than 40% of shoulder width, they aren't clasped
        if dist(lw, rw) / sw > 0.40:
            return (True, "Clasp hands together and point thumbs up")
        return (False, None)

    # ─────────────────────────────────────────────────────────────────────
    # MAIN DISPATCHER
    # ─────────────────────────────────────────────────────────────────────

    def check_pose(self, user_lm, w: int, h: int, phase: dict) -> tuple:
        pid = phase["id"]
        
        # Verify visibility for standard required landmarks
        req_lms = phase.get("check_landmarks", [])
        if not visible(user_lm, *req_lms):
            return (False, "Stand in frame. Make sure upper body is visible.")

        # Ensure hands are clasped for all movement phases (except palming)
        if pid != "p8_palming":
            err, msg = self._check_clasped(user_lm, w, h)
            if err: return (err, msg)

            # Update motion tracker for circular movements
            mid = self._mid_wrist(user_lm, w, h)
            self._tw_hands.update(mid[0], mid[1])

        # Routing to specific phase checks
        if pid == "p1_horizontal":
            return (False, f"Swing hands left to right. Reps: {self.rep_count}/5")
        elif pid == "p2_vertical":
            return (False, f"Move hands up and down. Reps: {self.rep_count}/5")
        elif pid in ["p3_diag_1", "p4_diag_2"]:
            return (False, f"Move hands diagonally. Reps: {self.rep_count}/5")
        elif pid in ["p5_circle_cw", "p6_circle_ccw"]:
            return (False, f"Rotate hands in big circle. Reps: {self.rep_count}/5")
        elif pid == "p7_near_far":
            return (False, f"Bring thumbs to nose, then extend. Reps: {self.rep_count}/5")
        elif pid == "p8_palming":
            return self._check_palming(user_lm, w, h)
            
        return (False, None)

    def detect_rep(self, user_lm, w: int, h: int):
        p = self._active_phase
        if not p:
            return
        
        pid = p["id"]
        mid = self._mid_wrist(user_lm, w, h)
        nose = px(user_lm, 0, w, h)
        sw = shoulder_width(user_lm, w, h)

        if pid == "p1_horizontal":
            self._rep_horizontal(mid, nose, sw)
        elif pid == "p2_vertical":
            ls = px(user_lm, 11, w, h)
            self._rep_vertical(mid, nose, ls[1])
        elif pid == "p3_diag_1":
            self._rep_diag_1(user_lm, mid, w, h)
        elif pid == "p4_diag_2":
            self._rep_diag_2(user_lm, mid, w, h)
        elif pid in ["p5_circle_cw", "p6_circle_ccw"]:
            self._rep_circular()
        elif pid == "p7_near_far":
            self._rep_near_far(user_lm, mid, nose, sw, w, h)

    # ─────────────────────────────────────────────────────────────────────
    # REP DETECTION LOGIC
    # ─────────────────────────────────────────────────────────────────────

    def _rep_horizontal(self, mid, nose, sw):
        """Cross right of nose, then left of nose = 1 rep"""
        margin = sw * 0.4  # Must move at least 40% of shoulder width past nose
        
        if self._mov_state != "RIGHT" and mid[0] < nose[0] - margin: # Screen coordinates: smaller X is Right side of body
            self._mov_state = "RIGHT"
        elif self._mov_state == "RIGHT" and mid[0] > nose[0] + margin: # Larger X is Left side of body
            self._mov_state = "LEFT"
            self.rep_count += 1

    def _rep_vertical(self, mid, nose, shoulder_y):
        """Above eyes, then down to lap = 1 rep"""
        if self._mov_state != "UP" and mid[1] < nose[1]:
            self._mov_state = "UP"
        elif self._mov_state == "UP" and mid[1] > shoulder_y + 50: # Hands drop below shoulders
            self._mov_state = "DOWN"
            self.rep_count += 1

    def _rep_diag_1(self, lm, mid, w, h):
        """Left Thigh (Low/Left) to Right Shoulder (High/Right)"""
        ls = px(lm, 11, w, h)
        rs = px(lm, 12, w, h)
        
        # High and Right (Screen X is flipped, so rs[0] is smaller)
        if self._mov_state != "HIGH" and mid[1] < rs[1] and mid[0] < rs[0]:
            self._mov_state = "HIGH"
        # Low and Left
        elif self._mov_state == "HIGH" and mid[1] > ls[1] + 100 and mid[0] > ls[0]:
            self._mov_state = "LOW"
            self.rep_count += 1

    def _rep_diag_2(self, lm, mid, w, h):
        """Right Thigh (Low/Right) to Left Shoulder (High/Left)"""
        ls = px(lm, 11, w, h)
        rs = px(lm, 12, w, h)
        
        # High and Left
        if self._mov_state != "HIGH" and mid[1] < ls[1] and mid[0] > ls[0]:
            self._mov_state = "HIGH"
        # Low and Right
        elif self._mov_state == "HIGH" and mid[1] > rs[1] + 100 and mid[0] < rs[0]:
            self._mov_state = "LOW"
            self.rep_count += 1

    def _rep_circular(self):
        """Uses MotionTracker to count completed cycles"""
        c = self._tw_hands.cycle_count()
        n = c - self._last_cyc
        if n > 0:
            self.rep_count += n
            self._last_cyc = c

    def _rep_near_far(self, lm, mid, nose, sw, w, h):
        """Thumbs near nose, then arms fully extended"""
        ls = px(lm, 11, w, h); le = px(lm, 13, w, h); lw = px(lm, 15, w, h)
        arm_angle = angle(ls, le, lw)
        
        # Near: Hands very close to face
        if self._mov_state != "NEAR" and dist(mid, nose) < sw * 0.4:
            self._mov_state = "NEAR"
        # Far: Arms straightened out
        elif self._mov_state == "NEAR" and arm_angle > 140:
            self._mov_state = "FAR"
            self.rep_count += 1

    # ─────────────────────────────────────────────────────────────────────
    # EXERCISE 8: PALMING
    # ─────────────────────────────────────────────────────────────────────

    def _check_palming(self, lm, w, h) -> tuple:
        """Ensure hands are covering the eyes for relaxation."""
        l_eye = px(lm, 1, w, h)
        r_eye = px(lm, 4, w, h)
        lw = px(lm, 15, w, h)
        rw = px(lm, 16, w, h)
        sw = shoulder_width(lm, w, h)
        
        # Wrists/Palms should be very close to the eyes
        if dist(lw, l_eye) > sw * 0.6 or dist(rw, r_eye) > sw * 0.6:
            self._palming_frames = 0 # Reset timer if hands drop
            return (True, "Cover your eyes completely with your palms")
            
        # Hold state (Simulating 1 minute hold using frames, assuming ~30fps)
        self._palming_frames += 1
        sec_held = self._palming_frames // 30
        
        if sec_held >= 60: # 60sec
            self.rep_count = 1
            return (False, "Palming complete. You may rest.")
            
        return (False, f"Relaxing... Hold for {60 - sec_held} more seconds")