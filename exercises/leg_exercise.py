"""
exercises/leg_exercise.py — Leg Exercises
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
POSE 1 — Toe Rotation (11:10)

Starting position:
  Sit on floor. Legs extended forward. 18 inches apart.
  Both hands on floor behind your body.

Movement:
  Step 1 → Rotate both feet INWARD  — big toe side touches floor
  Step 2 → Rotate both feet OUTWARD — little toe side touches floor
  Step 1 + Step 2 = 1 rep. Target: 5 reps.

REP DETECTION APPROACH:
  Problem: foot landmark visibility is low when sitting on floor.
  Solution: Use ANKLE → FOOT_INDEX direction vector.
    When foot rotates INWARD:
      foot_index moves toward body center → foot_index.x < ankle.x (left)
                                         → foot_index.x > ankle.x (right)
    When foot rotates OUTWARD:
      foot_index moves away from center  → foot_index.x > ankle.x (left)
                                         → foot_index.x < ankle.x (right)

  Additionally track BOTH feet must move together.
  Use SUSTAINED frames (8 frames) to avoid noise.
  Visibility fallback: if landmarks unreliable, use ankle Y-oscillation
  as secondary signal (feet rocking inward/outward causes ankle to shift).
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from core.base_controller import BaseController
from core.utils import angle, dist, px

EXERCISE_KEY = "leg"

# How many consecutive frames foot must hold rotation
HOLD_FRAMES = 8

_PHASES = [
    {
        "id":        "leg_p1_setup",
        "name":      "Get Into Position",
        "start":     660,
        "active":    668,
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
        "end":       860,
        "target":    5,
        "watch_msg": "Watch carefully — rotate both feet inward so big toes touch down, then outward so little toes touch down",
        "check_landmarks": [23, 24, 25, 26, 27, 28],
    },
]


class WorkoutController(BaseController):

    def __init__(self):
        super().__init__()
        self._toe_step       = "NEUTRAL"
        self._inward_count   = 0
        self._outward_count  = 0
        self._neutral_count  = 0

    def phases(self) -> list:
        return _PHASES

    def on_phase_change(self, phase: dict):
        self._toe_step      = "NEUTRAL"
        self._inward_count  = 0
        self._outward_count = 0
        self._neutral_count = 0

    @property
    def current_phase_name(self) -> str:
        p = self._get_phase(self._video_pos)
        return p["name"] if p else "Leg Exercises"

    @property
    def coach_state(self) -> str:
        return self._coach_state

    # ── dispatcher ───────────────────────────────────────────────────
    def check_pose(self, user_lm, ref_lm, w, h, phase) -> tuple:
        pid = phase["id"]
        if pid == "leg_p1_setup":
            return self._check_setup(user_lm, w, h)
        elif pid == "leg_p1_toe_rotation":
            return self._check_toe_rotation(user_lm, w, h)
        return False, None

    def detect_rep(self, user_lm, w, h):
        p = self._get_phase(self._video_pos)
        if p and p["id"] == "leg_p1_toe_rotation":
            self._rep_toe_rotation(user_lm, w, h)

    # ══════════════════════════════════════════════════════════════════
    # SETUP — guide user into correct starting position
    # ══════════════════════════════════════════════════════════════════
    def _check_setup(self, lm, w, h) -> tuple:
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

    # ══════════════════════════════════════════════════════════════════
    # FOOT ROTATION DIRECTION
    #
    # Compare foot_index X position relative to ankle X.
    # LEFT foot:
    #   foot_index.x < ankle.x → foot rotated INWARD (big toe side down)
    #   foot_index.x > ankle.x → foot rotated OUTWARD (little toe side down)
    # RIGHT foot (mirror):
    #   foot_index.x > ankle.x → INWARD
    #   foot_index.x < ankle.x → OUTWARD
    #
    # Returns "INWARD", "OUTWARD", or "NEUTRAL"
    # ══════════════════════════════════════════════════════════════════
    def _get_foot_rotation(self, lm) -> str:
        # Check landmark visibility — sitting on floor makes feet hard to see
        l_ankle_vis  = lm[27].visibility
        r_ankle_vis  = lm[28].visibility
        l_foot_vis   = lm[31].visibility
        r_foot_vis   = lm[32].visibility

        # If any key landmark is invisible, can't determine rotation
        if min(l_ankle_vis, r_ankle_vis, l_foot_vis, r_foot_vis) < 0.35:
            return "UNKNOWN"

        l_ankle_x = lm[27].x
        r_ankle_x = lm[28].x
        l_foot_x  = lm[31].x   # left foot_index
        r_foot_x  = lm[32].x   # right foot_index

        thr = 0.025  # 2.5% of normalized frame width

        l_inward  = l_foot_x < l_ankle_x - thr
        l_outward = l_foot_x > l_ankle_x + thr
        r_inward  = r_foot_x > r_ankle_x + thr
        r_outward = r_foot_x < r_ankle_x - thr

        if l_inward and r_inward:
            return "INWARD"
        if l_outward and r_outward:
            return "OUTWARD"
        return "NEUTRAL"

    # ══════════════════════════════════════════════════════════════════
    # TOE ROTATION CHECK — coach messages
    # ══════════════════════════════════════════════════════════════════
    def _check_toe_rotation(self, lm, w, h) -> tuple:
        lh = px(lm, 23, w, h); rh = px(lm, 24, w, h)
        lk = px(lm, 25, w, h); rk = px(lm, 26, w, h)
        la = px(lm, 27, w, h); ra = px(lm, 28, w, h)
        done = self.rep_count

        # Must keep legs straight throughout
        if angle(lh, lk, la) < 145:
            return True, "Keep your left leg straight — do not bend the knee"
        if angle(rh, rk, ra) < 145:
            return True, "Keep your right leg straight — do not bend the knee"

        # Must keep legs spread
        if dist(la, ra) / (dist(lh, rh) or 1) < 0.7:
            return True, "Keep your legs spread apart while rotating"

        if done >= 5:
            return False, "Well done — you have completed all 5 repetitions"

        # Guide based on state — natural coach voice
        step = self._toe_step
        if step == "NEUTRAL":
            return False, f"Rotate both feet inward now — press your big toes toward the floor  {done}/5"
        elif step == "INWARD":
            return False, f"Good — now rotate outward, press the outer edge of your feet down  {done}/5"
        elif step == "OUTWARD":
            return False, f"Rep {done} complete! Rotate inward again  {done}/5"

        return False, None

    # ══════════════════════════════════════════════════════════════════
    # REP COUNTING — sustained rotation detection
    #
    # Foot must hold INWARD or OUTWARD for HOLD_FRAMES frames.
    # Neutral frames slowly decay the counters.
    #
    # State: NEUTRAL → INWARD (step 1) → OUTWARD (step 2) = 1 rep
    #        OUTWARD → INWARD = next rep begins
    # ══════════════════════════════════════════════════════════════════
    def _rep_toe_rotation(self, lm, w, h):
        rotation = self._get_foot_rotation(lm)

        # UNKNOWN means landmarks not visible — don't count, don't reset
        if rotation == "UNKNOWN":
            return

        # Accumulate or decay frame counts
        if rotation == "INWARD":
            self._inward_count  += 1
            self._outward_count  = max(0, self._outward_count - 1)
            self._neutral_count  = 0
        elif rotation == "OUTWARD":
            self._outward_count += 1
            self._inward_count   = max(0, self._inward_count - 1)
            self._neutral_count  = 0
        else:  # NEUTRAL
            self._neutral_count += 1
            # slowly decay on neutral — don't hard-reset
            self._inward_count   = max(0, self._inward_count  - 1)
            self._outward_count  = max(0, self._outward_count - 1)

        inward_held  = self._inward_count  >= HOLD_FRAMES
        outward_held = self._outward_count >= HOLD_FRAMES

        # State transitions
        if self._toe_step == "NEUTRAL" and inward_held:
            self._toe_step      = "INWARD"
            self._inward_count  = 0

        elif self._toe_step == "INWARD" and outward_held:
            self._toe_step       = "OUTWARD"
            self._outward_count  = 0
            self.rep_count      += 1   # ← 1 rep complete

        elif self._toe_step == "OUTWARD" and inward_held:
            self._toe_step      = "INWARD"   # next rep starts
            self._inward_count  = 0
