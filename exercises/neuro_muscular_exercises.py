"""
exercises/neuro_muscular_exercise.py — SKY Yoga Neuro Muscular Exercises

SEQUENCE:
  p3  Waist Breathing               — hands on sides of waist, 10 breaths
  p4  Upper Chest Breathing         — fingers near armpits on upper chest, 10 breaths
  p5  Thigh Breathing               — hands flat on thighs near knees, 10 breaths
  p6  Abdomen Breathing             — fists on lower abdomen, 10 breaths
  p7  Forward Bend Breathing        — bend forward, forehead to ground, 10 breaths
  p8  Chin Mudra Relaxation         — sit upright, hands on knees in Chin Mudra

PHILOSOPHY:
  - Matches hand_exercise.py exactly: same base class, same import names,
    same check_pose / detect_rep signatures, same _active_phase usage
  - Rep counting uses BreathDetector — 1 inhale+exhale cycle = 1 rep
  - Pose checks are LENIENT: only fire on clearly wrong position
  - Vajrasana check skipped when leg landmarks are not visible
  - p8_relax has target=0 so no rep counting, pose check is optional feedback only
"""

import math
from core.base_controller import BaseController
from core.utils           import angle, dist, px, visible
from core.breath_detector import BreathDetector

EXERCISE_KEY = "neuro"

# ─────────────────────────────────────────────────────────────────────────────
# PHASE DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────

_PHASES = [
    # ── 1. Waist Breathing — 22:10 → 22:58 → 24:27 ──────────────────────────
    {
        "id":        "p3_waist",
        "name":      "Waist Breathing",
        "start":     1330, "active": 1378, "end": 1467,
        "target":    10,
        "watch_msg": "Keep sitting. Move hands to the sides of your waist.",
        "check_landmarks": [11, 12, 15, 16, 23, 24],
    },
    # ── 2. Upper Chest Breathing — 24:27 → 24:51 → 26:03 ────────────────────
    {
        "id":        "p4_chest",
        "name":      "Upper Chest Breathing",
        "start":     1467, "active": 1491, "end": 1563,
        "target":    10,
        "watch_msg": "Place your fingers on your upper chest near the armpits.",
        "check_landmarks": [11, 12, 13, 14, 15, 16],
    },
    # ── 3. Thigh Breathing — 26:03 → 26:36 → 27:51 ──────────────────────────
    {
        "id":        "p5_thighs",
        "name":      "Thigh Breathing",
        "start":     1563, "active": 1596, "end": 1671,
        "target":    10,
        "watch_msg": "Rest your hands flat on your thighs near the knees.",
        "check_landmarks": [15, 16, 25, 26],
    },
    # ── 4. Abdomen Breathing — 27:51 → 28:04 → 28:40 ────────────────────────
    {
        "id":        "p6_abdomen",
        "name":      "Abdomen Breathing",
        "start":     1671, "active": 1684, "end": 1720,
        "target":    10,
        "watch_msg": "Make fists and press them gently on your lower abdomen.",
        "check_landmarks": [15, 16, 23, 24],
    },
    # ── 5. Forward Bend Breathing — 28:40 → 29:03 → 29:37 ───────────────────
    {
        "id":        "p7_forward",
        "name":      "Forward Bend Breathing",
        "start":     1720, "active": 1743, "end": 1777,
        "target":    10,
        "watch_msg": "From Vajrasana, bend forward and touch your forehead to the ground.",
        "check_landmarks": [0, 11, 12, 23, 24],
    },
    # ── 6. Chin Mudra Relaxation — 29:38 → 29:55 → 30:31 ────────────────────
    {
        "id":        "p8_relax",
        "name":      "Chin Mudra Relaxation",
        "start":     1778, "active": 1795, "end": 1831,
        "target":    0,
        "watch_msg": "Sit upright, rest hands on knees in Chin Mudra. Breathe naturally.",
        "check_landmarks": [11, 12, 15, 16, 25, 26],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# CONTROLLER
# ─────────────────────────────────────────────────────────────────────────────

class WorkoutController(BaseController):

    def __init__(self):
        super().__init__()
        self._breath = BreathDetector(min_breath_sec=3.0)

    # ── required by BaseController ────────────────────────────────────────────

    def phases(self) -> list:
        return _PHASES

    def on_phase_change(self, phase: dict):
        """Reset breath detector whenever a new phase begins."""
        self._breath.reset()

    @property
    def current_phase_name(self) -> str:
        p = self._get_phase(self._video_pos)
        return p["name"] if p else "Neuro Muscular Exercises"

    # ── check_pose — signature MUST match BaseController: (lm, w, h, phase) ──

    def check_pose(self, lm, w, h, phase) -> tuple:
        """
        Returns (is_error: bool, message: str).
        is_error=True  → red skeleton + correction message
        is_error=False → green skeleton (message may still be a positive cue)
        """
        pid = phase["id"]

        # p8 is free relaxation — skip form checking, just encourage
        if pid == "p8_relax":
            return (False, "Good — breathe naturally and relax.")

        # All seated breathing phases require Vajrasana (except forward bend)
        if pid != "p7_forward":
            vajra_ok, vajra_err = self._check_vajrasana(lm, w, h)
            if not vajra_ok:
                return (True, vajra_err)

        if pid == "p3_waist":   return self._check_hands_waist(lm, w, h)
        if pid == "p4_chest":   return self._check_hands_chest(lm, w, h)
        if pid == "p5_thighs":  return self._check_hands_thighs(lm, w, h)
        if pid == "p6_abdomen": return self._check_hands_abdomen(lm, w, h)
        if pid == "p7_forward": return self._check_forward_bend(lm, w, h)

        return (False, "Good form — keep going")

    # ── detect_rep — signature MUST match BaseController: (lm, w, h) ──────────

    def detect_rep(self, lm, w, h):
        """
        Count reps by breath detection (shoulder y-oscillation).
        Uses _active_phase (not _get_phase) so counting persists
        through HOLD state and inter-phase gaps, identical to hand_exercise.py.

        IMPORTANT: Only feeds the breath detector when pose is correct
        (error_frames == 0). This prevents reps counting during wrong pose.
        """
        p = self._active_phase
        if not p or p.get("target", 0) == 0:
            return

        # Do not count breaths while pose errors are active
        if self.error_frames > 0:
            return

        # Feed shoulder midpoint y to breath detector (normalized 0-1)
        if visible(lm, 11, 12):
            self._breath.update((lm[11].y + lm[12].y) / 2)

        new = self._breath.new_breaths()
        if new > 0:
            self.rep_count += new

    # =========================================================================
    # POSE CHECKS
    # =========================================================================

    def _check_vajrasana(self, lm, w, h) -> tuple:
        """
        Check user is sitting in Vajrasana (kneeling on heels).
        LENIENT: skip entirely if leg landmarks are not visible —
        avoids false errors when lower body is off-camera.

        Vajrasana indicators:
          - Hip y-coord close to ankle y-coord (sitting on heels)
          - Knee y between hip and ankle (knees on floor)
        """
        if not visible(lm, 23, 24, 25, 26, 27, 28):
            return (True, None)   # legs not visible — skip, no error

        hip_y   = (lm[23].y + lm[24].y) / 2
        knee_y  = (lm[25].y + lm[26].y) / 2
        ankle_y = (lm[27].y + lm[28].y) / 2

        # Hip should be close to ankle (sitting on heels, not standing)
        if abs(hip_y - ankle_y) > 0.18:
            return (False, "Sit down in Vajrasana — lower your hips onto your heels.")

        # Knee should sit between hip and ankle in y (kneeling, not crossed)
        if not (hip_y <= knee_y <= ankle_y + 0.08):
            return (False, "Keep your knees on the floor in Vajrasana.")

        return (True, None)

    def _check_hands_waist(self, lm, w, h) -> tuple:
        """
        Hands on sides of waist.
        Wrists should be at roughly the same y-level as hips.
        LENIENT: 0.12 normalized y-difference allowed.
        """
        if not visible(lm, 15, 16, 23, 24):
            return (False, "Good — keep your hands on your waist.")

        if abs(lm[15].y - lm[23].y) > 0.12 or abs(lm[16].y - lm[24].y) > 0.12:
            return (True, "Place your hands on the sides of your waist.")
        return (False, "Good — hands on waist. Breathe into your sides.")

    def _check_hands_chest(self, lm, w, h) -> tuple:
        """
        Fingers on upper chest near armpits.
        Wrists (15, 16) should be near shoulders (11, 12).
        LENIENT threshold: 20% of frame width.
        """
        if not visible(lm, 11, 12, 15, 16):
            return (False, "Good — keep fingers on your upper chest.")

        lwr = px(lm, 15, w, h)
        rwr = px(lm, 16, w, h)
        ls  = px(lm, 11, w, h)
        rs  = px(lm, 12, w, h)

        if dist(lwr, ls) > w * 0.20 or dist(rwr, rs) > w * 0.20:
            return (True, "Place your fingers on your upper chest near the armpits.")
        return (False, "Good — fingers on chest. Breathe into your upper lungs.")

    def _check_hands_thighs(self, lm, w, h) -> tuple:
        """
        Hands flat on thighs near knees.
        Wrists (15, 16) should be close to knees (25, 26).
        LENIENT threshold: 18% of frame width.
        """
        if not visible(lm, 15, 16, 25, 26):
            return (False, "Good — keep hands on your thighs.")

        lwr = px(lm, 15, w, h)
        rwr = px(lm, 16, w, h)
        lk  = px(lm, 25, w, h)
        rk  = px(lm, 26, w, h)

        if dist(lwr, lk) > w * 0.18 or dist(rwr, rk) > w * 0.18:
            return (True, "Place your hands flat on your thighs near the knees.")
        return (False, "Good — hands on thighs. Breathe steadily.")

    def _check_hands_abdomen(self, lm, w, h) -> tuple:
        """
        Fists on lower abdomen.
        Both wrists should be close to the hip-center point.
        LENIENT threshold: 15% of frame width.
        """
        if not visible(lm, 15, 16, 23, 24):
            return (False, "Good — keep fists on your abdomen.")

        lwr = px(lm, 15, w, h)
        rwr = px(lm, 16, w, h)
        hc  = ((lm[23].x + lm[24].x) / 2 * w,
               (lm[23].y + lm[24].y) / 2 * h)

        if dist(lwr, hc) > w * 0.15 or dist(rwr, hc) > w * 0.15:
            return (True, "Place your fists together on your lower abdomen.")
        return (False, "Good — fists on abdomen. Breathe into your belly.")

    def _check_forward_bend(self, lm, w, h) -> tuple:
        """
        Torso bent forward from Vajrasana — forehead approaching the ground.
        Nose (0) y-coordinate should be clearly below hip level.
        LENIENT: only fires if nose is still well above hip level (> 0.08 gap).
        """
        if not visible(lm, 0, 23, 24):
            return (False, "Good — keep bending forward.")

        nose_y = lm[0].y
        hip_y  = (lm[23].y + lm[24].y) / 2

        # In a forward bend the nose moves DOWN (higher y value in normalized coords)
        # so nose_y should be GREATER than hip_y (nose is lower on screen than hips)
        if nose_y < hip_y + 0.08:
            return (True, "Bend further forward — try to touch your forehead to the ground.")
        return (False, "Good — stay folded forward. Breathe slowly.")