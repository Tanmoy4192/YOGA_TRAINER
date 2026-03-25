"""
exercises/leg_exercise.py — Leg Exercises
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
POSE 6 — Seated Foot Massage

Starting position:
  Sit on floor. One leg extended straight.
  Bend the other leg, bringing the foot to rest on/near the opposite thigh or knee.
  Place both hands on the bent foot.

Movement:
  Massage the foot by rubbing your hands from the toes down to the heel/ankle, and back.
  1 Full Stroke (Toes -> Ankle -> Toes) = 1 rep. Target: 10 strokes.

REP DETECTION APPROACH:
  Problem: Standard Pose estimation does not track individual fingers for a "massage".
  Solution: Track the macro movement of the wrists sliding across the foot.
    Dynamically detect which leg is bent (the Active Leg).
    Compare the distance of the wrists to the active foot's Toes vs Ankle.
    
  State Machine:
    TOES -> ANKLE -> TOES = 1 Massage Stroke.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from core.base_controller import BaseController
from core.utils import calculate_angle, dist, lm_px

EXERCISE_KEY = "leg"

# Frames to hold a position to avoid jitter
HOLD_FRAMES = 4

_PHASES = [
    {
        "id":        "leg_p6_setup",
        "name":      "Get Into Position",
        "start":     0, #13.45
        "active":    10,#14.01
        "end":       20,#14.01
        "target":    0,
        "watch_msg": "Sit down. Keep one leg straight, bend the other, and bring that foot to your opposite knee. Grab your foot with both hands.",
        "check_landmarks": [15, 16, 23, 24, 25, 26, 27, 28, 31, 32],
    },
    {
        "id":        "leg_p6_massage",
        "name":      "Foot Massage — 10 Strokes",
        "start":     20,#14.01
        "active":    25,#14.01
        "end":       200,#21.09
        "target":    10,
        "watch_msg": "Massage your foot, sliding your hands from your toes down to your ankle, and back.",
        "check_landmarks": [15, 16, 25, 26, 27, 28, 29, 30, 31, 32],
    },
]

class WorkoutController(BaseController):

    def __init__(self):
        super().__init__()
        # State tracking
        self._massage_state = "TOES"
        self._active_leg    = None  # Will be 'LEFT' or 'RIGHT' based on which is bent
        self._toes_count    = 0
        self._ankle_count   = 0

    def phases(self) -> list:
        return _PHASES

    def on_phase_change(self, phase: dict):
        self._massage_state = "TOES"
        self._toes_count    = 0
        self._ankle_count   = 0
        # We don't reset _active_leg here so it persists from setup to massage

    @property
    def current_phase_name(self) -> str:
        p = self._get_phase(self._video_pos)
        return p["name"] if p else "Foot Massage"

    @property
    def coach_state(self) -> str:
        return self._coach_state

    # ── dispatcher ───────────────────────────────────────────────────
    def check_pose(self, user_lm, ref_lm, w, h, phase) -> tuple:
        pid = phase["id"]
        if pid == "leg_p6_setup":
            return self._check_setup(user_lm, w, h)
        elif pid == "leg_p6_massage":
            return self._check_massage(user_lm, w, h)
        return False, None

    def detect_rep(self, user_lm, w, h):
        p = self._get_phase(self._video_pos)
        if p and p["id"] == "leg_p6_massage":
            self._rep_massage(user_lm, w, h)

    # ══════════════════════════════════════════════════════════════════
    # SETUP — Dynamically detect the bent leg and hand placement
    # ══════════════════════════════════════════════════════════════════
    def _check_setup(self, lm, w, h) -> tuple:
        lh = lm_px(lm, 23, w, h); rh = lm_px(lm, 24, w, h)
        lk = lm_px(lm, 25, w, h); rk = lm_px(lm, 26, w, h)
        la = lm_px(lm, 27, w, h); ra = lm_px(lm, 28, w, h)
        lw = lm_px(lm, 15, w, h); rw = lm_px(lm, 16, w, h)

        l_angle = calculate_angle(lh, lk, la)
        r_angle = calculate_angle(rh, rk, ra)

        # 1. Determine which leg is bent and which is straight
        if l_angle < 120 and r_angle > 140:
            self._active_leg = "LEFT"
        elif r_angle < 120 and l_angle > 140:
            self._active_leg = "RIGHT"
        else:
            return True, "Keep one leg straight, and bend the other leg towards you"

        # 2. Check if foot is placed near the opposite knee/thigh area
        if self._active_leg == "LEFT":
            if dist(la, rk) > w * 0.25:
                return True, "Rest your left foot on or near your right leg"
            active_ankle = la
        else:
            if dist(ra, lk) > w * 0.25:
                return True, "Rest your right foot on or near your left leg"
            active_ankle = ra

        # 3. Check if hands are holding the active foot
        hands_mid_x = (lw[0] + rw[0]) / 2
        hands_mid_y = (lw[1] + rw[1]) / 2
        hands_mid = (hands_mid_x, hands_mid_y)

        if dist(hands_mid, active_ankle) > w * 0.20:
            return True, "Bring both hands to hold your bent foot"

        return False, "Great position. Hold your foot to begin."

    # ══════════════════════════════════════════════════════════════════
    # MASSAGE POSITION DETECTION
    # Compare wrist midpoint distance: Toes vs Ankle
    # ══════════════════════════════════════════════════════════════════
    def _get_massage_position(self, lm, w, h) -> str:
        if not self._active_leg:
            return "UNKNOWN"

        lw = lm_px(lm, 15, w, h); rw = lm_px(lm, 16, w, h)
        hands_mid = ((lw[0] + rw[0]) / 2, (lw[1] + rw[1]) / 2)

        # Get landmarks for the active (bent) foot
        if self._active_leg == "LEFT":
            ankle = lm_px(lm, 27, w, h)
            toes  = lm_px(lm, 31, w, h)
        else:
            ankle = lm_px(lm, 28, w, h)
            toes  = lm_px(lm, 32, w, h)

        dist_to_toes  = dist(hands_mid, toes)
        dist_to_ankle = dist(hands_mid, ankle)

        # If hands are closer to the toes than the ankle
        if dist_to_toes < dist_to_ankle * 0.8:
            return "TOES"
        # If hands are pulled back toward the ankle
        elif dist_to_ankle < dist_to_toes * 0.8:
            return "ANKLE"

        return "MIDDLE"

    # ══════════════════════════════════════════════════════════════════
    # MASSAGE CHECK — coach messages and constraints
    # ══════════════════════════════════════════════════════════════════
    def _check_massage(self, lm, w, h) -> tuple:
        lw = lm_px(lm, 15, w, h); rw = lm_px(lm, 16, w, h)
        done = self.rep_count

        # Get active ankle
        if self._active_leg == "LEFT":
            active_ankle = lm_px(lm, 27, w, h)
        elif self._active_leg == "RIGHT":
            active_ankle = lm_px(lm, 28, w, h)
        else:
            return True, "Setup not detected properly, please reset."

        # Constraint: Hands must stay near the foot
        hands_mid = ((lw[0] + rw[0]) / 2, (lw[1] + rw[1]) / 2)
        if dist(hands_mid, active_ankle) > w * 0.35:
            return True, "Keep your hands on your foot to massage it"

        if done >= 10:
            return False, "Great job! You have finished massaging this foot."

        # Guide based on state
        state = self._massage_state
        if state == "TOES":
            return False, f"Rub down towards your ankle/heel  {done}/10"
        elif state == "ANKLE":
            return False, f"Rub back up towards your toes  {done}/10"

        return False, None

    # ══════════════════════════════════════════════════════════════════
    # REP COUNTING — Stroke Tracking
    # State sequence required for 1 rep:
    # TOES -> ANKLE -> TOES = 1 Rep (Stroke)
    # ══════════════════════════════════════════════════════════════════
    def _rep_massage(self, lm, w, h):
        pos = self._get_massage_position(lm, w, h)

        if pos == "UNKNOWN" or pos == "MIDDLE":
            return

        # Accumulators
        if pos == "TOES":
            self._toes_count  += 1
            self._ankle_count  = 0
        elif pos == "ANKLE":
            self._ankle_count += 1
            self._toes_count   = 0

        toes_held  = self._toes_count >= HOLD_FRAMES
        ankle_held = self._ankle_count >= HOLD_FRAMES

        # State transitions
        if self._massage_state == "TOES" and ankle_held:
            self._massage_state = "ANKLE"

        elif self._massage_state == "ANKLE" and toes_held:
            self._massage_state = "TOES"
            self.rep_count += 1  # 1 Full stroke cycle complete!