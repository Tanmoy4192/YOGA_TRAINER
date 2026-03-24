"""
exercises/acupressure.py — SKY Yoga Acupressure Exercise
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SEQUENCE — 14 Acupressure Points + Finish Rest:
  p1   Left Neck                    — right hand on left side of neck
  p2   Upper Abdomen (Solar Plexus) — right index finger at ribcage center
  p3   Mid Abdomen                  — one inch below p2
  p4   Above Navel                  — one inch above navel
  p5   Navel Pull Up                — right index finger in navel, pull toward head
  p6   Navel Push Down              — right thumb in navel, push toward feet
  p7   Navel Pull Right Shoulder    — right index finger in navel, pull to right shoulder
  p8   Navel Pull Left Shoulder     — right index finger in navel, pull to left shoulder
  p9   Navel Pull Right Thigh       — right index finger in navel, pull to right thigh
  p10  Navel Push Left Thigh        — right thumb in navel, push to left thigh
  p11  Right Ribs                   — right index finger one inch below right ribcage
  p12  Left Ribs                    — right index finger one inch below left ribcage
  p13  Right Waist                  — right thumb on soft area between right rib and hip
  p14  Lower Left Abdomen           — right index + middle fingers between navel and left groin
  p15  Finish Rest                  — arms relaxed to sides, full rest

POSTURE RULES (instructor):
  - Lie flat on back, completely relaxed
  - Hold each point ~30 seconds (~8 deep breaths)
  - Use right index finger or thumb; other fingers extended, not touching body
  - Use fleshy pad of finger — nails must not dig in

REP DETECTION:
  Each phase uses BreathDetector. Target = 8 breaths per point.
  Reps only count when right hand is confirmed touching the correct point.
  error_frames gate prevents counting during wrong pose.

POSE CHECK:
  1. Lying flat check  — only fires when clearly standing
  2. Hand-on-point check — uses body-relative virtual targets + distance threshold
     Skipped silently when landmarks not visible.
"""

from core.base_controller import BaseController
from core.utils           import angle, dist, px, visible, shoulder_width
from core.breath_detector import BreathDetector

EXERCISE_KEY = "accupressure"

HOLD_FRAMES = 8

# ─────────────────────────────────────────────────────────────────────────────
# PHASE DEFINITIONS
# Each watch_msg describes exactly what to do for THAT specific point.
# The lying-flat posture is the global requirement for all phases.
# ─────────────────────────────────────────────────────────────────────────────

_PHASES = [
    # ── Intro — zoom / watch ──────────────────────────────────────────────────
    {
        "id":        "ac_p0_intro",
        "name":      "Acupressure — General Rules",
        "start":     3197, "active": 3197, "end": 3200,
        "zoom":      True,
        "watch_msg": "Lie flat on your back. Use right index finger or thumb. Hold each point ~30 seconds (~8 deep breaths).",
    },
    # ── 1. Left Neck ──────────────────────────────────────────────────────────
    {
        "id":        "ac_p1_neck",
        "name":      "Point 1 — Left Neck",
        "start":     3200, "active": 3202, "end": 3210,
        "target":    8,
        "watch_msg": "Place your RIGHT hand gently on the LEFT side of your neck. Hold and breathe.",
        "check_landmarks": [11, 12, 15, 16, 0],
    },
    # ── 2. Solar Plexus ───────────────────────────────────────────────────────
    {
        "id":        "ac_p2_solar",
        "name":      "Point 2 — Solar Plexus",
        "start":     3210, "active": 3212, "end": 3240,
        "target":    8,
        "watch_msg": "Right index finger at the CENTER of your upper abdomen where the ribcage meets. Press gently.",
        "check_landmarks": [11, 12, 15, 16, 23, 24],
    },
    # ── 3. Mid Abdomen ────────────────────────────────────────────────────────
    {
        "id":        "ac_p3_mid_abdomen",
        "name":      "Point 3 — Mid Abdomen",
        "start":     3240, "active": 3242, "end": 3260,
        "target":    8,
        "watch_msg": "Move right index finger ONE INCH below the solar plexus and press gently.",
        "check_landmarks": [11, 12, 15, 16, 23, 24],
    },
    # ── 4. Above Navel ────────────────────────────────────────────────────────
    {
        "id":        "ac_p4_above_navel",
        "name":      "Point 4 — Above Navel",
        "start":     3260, "active": 3262, "end": 3276,
        "target":    8,
        "watch_msg": "Move right index finger ONE INCH above your navel and press gently.",
        "check_landmarks": [11, 12, 15, 16, 23, 24],
    },
    # ── 5. Navel Pull Up ──────────────────────────────────────────────────────
    {
        "id":        "ac_p5_navel_up",
        "name":      "Point 5 — Navel Pull Up",
        "start":     3276, "active": 3278, "end": 3298,
        "target":    8,
        "watch_msg": "Right index finger INSIDE the navel. Pull the inner edge UPWARD toward your head.",
        "check_landmarks": [11, 12, 15, 16, 23, 24],
    },
    # ── 6. Navel Push Down ────────────────────────────────────────────────────
    {
        "id":        "ac_p6_navel_down",
        "name":      "Point 6 — Navel Push Down",
        "start":     3298, "active": 3300, "end": 3313,
        "target":    8,
        "watch_msg": "Switch to RIGHT THUMB inside the navel. Press the inner edge DOWNWARD toward your feet.",
        "check_landmarks": [11, 12, 15, 16, 23, 24],
    },
    # ── 7. Navel Pull Right Shoulder ──────────────────────────────────────────
    {
        "id":        "ac_p7_navel_r_shoulder",
        "name":      "Point 7 — Navel → Right Shoulder",
        "start":     3313, "active": 3315, "end": 3339,
        "target":    8,
        "watch_msg": "Right index finger inside navel. Pull inner edge diagonally toward your RIGHT SHOULDER.",
        "check_landmarks": [11, 12, 15, 16, 23, 24],
    },
    # ── 8. Navel Pull Left Shoulder ───────────────────────────────────────────
    {
        "id":        "ac_p8_navel_l_shoulder",
        "name":      "Point 8 — Navel → Left Shoulder",
        "start":     3339, "active": 3341, "end": 3366,
        "target":    8,
        "watch_msg": "Right index finger inside navel. Pull diagonally toward your LEFT SHOULDER.",
        "check_landmarks": [11, 12, 15, 16, 23, 24],
    },
    # ── 9. Navel Pull Right Thigh ─────────────────────────────────────────────
    {
        "id":        "ac_p9_navel_r_thigh",
        "name":      "Point 9 — Navel → Right Thigh",
        "start":     3366, "active": 3368, "end": 3387,
        "target":    8,
        "watch_msg": "Right index finger inside navel. Pull inner edge diagonally toward your RIGHT THIGH.",
        "check_landmarks": [11, 12, 15, 16, 23, 24],
    },
    # ── 10. Navel Push Left Thigh ─────────────────────────────────────────────
    {
        "id":        "ac_p10_navel_l_thigh",
        "name":      "Point 10 — Navel → Left Thigh",
        "start":     3387, "active": 3389, "end": 3405,
        "target":    8,
        "watch_msg": "Switch to RIGHT THUMB inside navel. Push diagonally downward toward your LEFT THIGH.",
        "check_landmarks": [11, 12, 15, 16, 23, 24],
    },
    # ── 11. Right Ribs ────────────────────────────────────────────────────────
    {
        "id":        "ac_p11_right_ribs",
        "name":      "Point 11 — Right Ribs",
        "start":     3405, "active": 3407, "end": 3419,
        "target":    8,
        "watch_msg": "Right index finger ONE INCH below your RIGHT ribcage on the center line. Press gently.",
        "check_landmarks": [11, 12, 15, 16, 23, 24],
    },
    # ── 12. Left Ribs ─────────────────────────────────────────────────────────
    {
        "id":        "ac_p12_left_ribs",
        "name":      "Point 12 — Left Ribs",
        "start":     3419, "active": 3421, "end": 3438,
        "target":    8,
        "watch_msg": "Right index finger ONE INCH below your LEFT ribcage on the center line. Press gently.",
        "check_landmarks": [11, 12, 15, 16, 23, 24],
    },
    # ── 13. Right Waist ───────────────────────────────────────────────────────
    {
        "id":        "ac_p13_right_waist",
        "name":      "Point 13 — Right Waist",
        "start":     3438, "active": 3440, "end": 3458,
        "target":    8,
        "watch_msg": "Right thumb on the soft area between your RIGHT lower rib and hip bone (side waist).",
        "check_landmarks": [11, 12, 15, 16, 23, 24],
    },
    # ── 14. Lower Left Abdomen ────────────────────────────────────────────────
    {
        "id":        "ac_p14_lower_left_abdomen",
        "name":      "Point 14 — Lower Left Abdomen",
        "start":     3458, "active": 3460, "end": 3479,
        "target":    8,
        "watch_msg": "Right index AND middle fingers together on the midpoint between navel and LEFT groin crease.",
        "check_landmarks": [11, 12, 15, 16, 23, 24],
    },
    # ── Finish Rest ───────────────────────────────────────────────────────────
    {
        "id":        "ac_p15_rest",
        "name":      "Finish — Rest",
        "start":     3479, "active": 3481, "end": 3489,
        "target":    0,
        "watch_msg": "Relax your arms to your sides. Rest completely. Acupressure is complete.",
        "check_landmarks": [11, 12, 15, 16],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# CONTROLLER
# ─────────────────────────────────────────────────────────────────────────────

class WorkoutController(BaseController):
    """
    Acupressure exercise controller.

    Each of the 14 points is a timed hold (~30s / 8 breaths).
    Rep counting uses BreathDetector gated on:
      1. error_frames == 0  (pose is currently correct)
      2. hand IS touching the target point  (confirmed each frame)
    Pose checking uses body-relative virtual targets.
    """

    def __init__(self):
        super().__init__()
        self._breath = BreathDetector(min_breath_sec=3.0)

    # ── required by BaseController ────────────────────────────────────────────

    def phases(self) -> list:
        return _PHASES

    def on_phase_change(self, phase: dict):
        self._breath.reset()

    @property
    def current_phase_name(self) -> str:
        p = self._get_phase(self._video_pos)
        return p["name"] if p else "Acupressure"

    # ── check_pose ────────────────────────────────────────────────────────────

    def check_pose(self, lm, w, h, phase) -> tuple:
        pid = phase["id"]

        # Intro and rest — no pose check
        if pid in ("ac_p0_intro", "ac_p15_rest"):
            return (False, "Good — relax completely.")

        # 1. Lying flat check
        flat_ok, flat_err = self._check_lying_flat(lm, w, h)
        if not flat_ok:
            return (True, flat_err)

        # 2. Hand on correct point
        touched, msg = self._check_hand_on_point(lm, w, h, pid)
        if not touched:
            return (True, msg)

        return (False, msg)

    # ── detect_rep ────────────────────────────────────────────────────────────

    def detect_rep(self, lm, w, h):
        """
        Count breaths only when:
          - error_frames == 0  (no active pose error)
          - hand is confirmed touching the correct point this frame
        """
        p = self._active_phase
        if not p or p.get("target", 0) == 0:
            return

        # Gate 1: pose error active
        if self.error_frames > 0:
            return

        # Gate 2: hand must be on the point right now
        touched, _ = self._check_hand_on_point(lm, w, h, p["id"])
        if not touched:
            return

        # Feed breath detector with shoulder/chest y-position
        if visible(lm, 11, 12):
            self._breath.update((lm[11].y + lm[12].y) / 2)

        new = self._breath.new_breaths()
        if new > 0:
            self.rep_count = min(self.rep_count + new, p.get("target", 8))

    # =========================================================================
    # LYING FLAT CHECK
    # =========================================================================

    def _check_lying_flat(self, lm, w, h) -> tuple:
        """
        Verify user is lying flat on their back.
        Only fires when landmarks clearly show standing posture.
        Skipped when landmarks not visible.

        Standing signal: shoulders near top of frame (y < 0.35) AND
        large vertical gap between shoulders and hips (> 0.25).
        When lying down the camera is overhead/side so both landmarks
        sit in the mid-y range.
        """
        if not visible(lm, 11, 12, 23, 24):
            return (True, None)   # can't determine — skip silently

        shoulder_y   = (lm[11].y + lm[12].y) / 2
        hip_y        = (lm[23].y + lm[24].y) / 2
        vertical_gap = abs(hip_y - shoulder_y)

        if shoulder_y < 0.35 and vertical_gap > 0.25:
            return (False, "Please lie flat on your back before starting acupressure.")

        return (True, None)

    # =========================================================================
    # HAND-ON-POINT CHECK
    # =========================================================================

    def _check_hand_on_point(self, lm, w, h, pid) -> tuple:
        """
        Check whether the right hand is touching the current acupressure point.

        Steps:
          1. Compute virtual target pixel using body-relative landmarks
          2. Find closest visible right-hand landmark (wrist / finger tips)
          3. Compare distance to a body-scale threshold
          4. Return (touched: bool, message: str)

        Returns (True, positive_msg) when hand is on the point.
        Returns (False, correction_msg) when hand is off the point or
        landmarks are not visible enough to compute the target.
        """
        target = self._target_point_px(lm, w, h, pid)
        if target is None:
            # Can't compute target — landmarks not visible, give benefit of doubt
            return (True, "Good — keep your right hand on the pressure point.")

        hand = self._best_right_hand_px(lm, w, h, target)
        if hand is None:
            # Right hand landmarks completely invisible
            return (False, self._correction_msg(pid))

        sw        = max(1.0, shoulder_width(lm, w, h))
        threshold = self._threshold(sw, pid)

        if dist(hand, target) <= threshold:
            return (True, self._hold_msg(pid))

        return (False, self._correction_msg(pid))

    # ── virtual target computation ────────────────────────────────────────────

    def _target_point_px(self, lm, w, h, pid):
        """
        Return the pixel coordinates of the expected acupressure point
        based on body landmarks. Returns None if required landmarks invisible.

        All points are expressed as a blend ratio between two anchor landmarks:
          blend(A, B, 0.0) = A,  blend(A, B, 1.0) = B

        Body geometry used:
          sternum  = midpoint between shoulders (11, 12)
          navel    = midpoint of the shoulder-midpoint and hip-midpoint quad
          left/right hip, shoulder, knee landmarks as needed
        """
        if not visible(lm, 11, 12, 23, 24):
            return None

        ls = px(lm, 11, w, h)   # left shoulder
        rs = px(lm, 12, w, h)   # right shoulder
        lh = px(lm, 23, w, h)   # left hip
        rh = px(lm, 24, w, h)   # right hip

        def blend(a, b, t):
            return (a[0] + (b[0] - a[0]) * t,
                    a[1] + (b[1] - a[1]) * t)

        sternum = blend(ls, rs, 0.5)                   # center between shoulders
        hip_mid = blend(lh, rh, 0.5)                   # center between hips
        navel   = blend(sternum, hip_mid, 0.55)        # slightly below torso center

        # ── p1: Left Neck ─────────────────────────────────────────────────────
        if pid == "ac_p1_neck":
            # Neck = halfway between left shoulder and nose/ear
            if visible(lm, 7):                          # left ear
                return blend(ls, px(lm, 7, w, h), 0.45)
            if visible(lm, 0):                          # nose fallback
                return blend(ls, px(lm, 0, w, h), 0.40)
            return blend(ls, sternum, -0.30)            # above left shoulder

        # ── p2: Solar Plexus — upper abdomen, ribcage center ──────────────────
        if pid == "ac_p2_solar":
            return blend(sternum, navel, 0.22)

        # ── p3: Mid Abdomen — one inch below solar plexus ─────────────────────
        if pid == "ac_p3_mid_abdomen":
            return blend(sternum, navel, 0.45)

        # ── p4: Above Navel — one inch above navel ────────────────────────────
        if pid == "ac_p4_above_navel":
            return blend(sternum, navel, 0.70)

        # ── p5–p10: Navel points — all centered on navel ──────────────────────
        if pid in ("ac_p5_navel_up", "ac_p6_navel_down",
                   "ac_p7_navel_r_shoulder", "ac_p8_navel_l_shoulder",
                   "ac_p9_navel_r_thigh", "ac_p10_navel_l_thigh"):
            return navel

        # ── p11: Right Ribs — one inch below right ribcage ────────────────────
        if pid == "ac_p11_right_ribs":
            return blend(rs, rh, 0.32)

        # ── p12: Left Ribs — one inch below left ribcage ──────────────────────
        if pid == "ac_p12_left_ribs":
            return blend(ls, lh, 0.32)

        # ── p13: Right Waist — soft area between right rib and hip ────────────
        if pid == "ac_p13_right_waist":
            return blend(rs, rh, 0.65)

        # ── p14: Lower Left Abdomen — midpoint navel → left groin ─────────────
        if pid == "ac_p14_lower_left_abdomen":
            if visible(lm, 25):                         # left knee
                lk = px(lm, 25, w, h)
                groin = blend(lh, lk, 0.20)             # just below left hip
            else:
                groin = blend(lh, hip_mid, 1.30)        # estimate groin
            return blend(navel, groin, 0.50)

        return None

    # ── best right-hand landmark ──────────────────────────────────────────────

    def _best_right_hand_px(self, lm, w, h, target):
        """
        Find the closest visible right-hand landmark to the target point.
        Candidate order: index fingertip (20), middle fingertip (22), wrist (16),
        thumb tip (18), ring fingertip (20), pinky (22).
        We use wrist + all right-hand fingertips for maximum coverage.
        """
        candidates = [16, 18, 20, 22]   # wrist, thumb, index, middle
        best_pt   = None
        best_d    = float("inf")
        for idx in candidates:
            if not visible(lm, idx):
                continue
            pt = px(lm, idx, w, h)
            d  = dist(pt, target)
            if d < best_d:
                best_d  = d
                best_pt = pt
        return best_pt

    # ── thresholds ────────────────────────────────────────────────────────────

    def _threshold(self, shoulder_w, pid) -> float:
        """
        Distance threshold in pixels for hand-on-point detection.
        Expressed as a fraction of shoulder_width so it scales with
        how close the person is to the camera.

        Neck point gets a larger threshold — hand covers the whole neck area.
        Abdomen / navel points get medium threshold.
        Rib / waist points get standard threshold.
        """
        if pid == "ac_p1_neck":
            return shoulder_w * 0.75    # neck area is broad
        if pid in ("ac_p5_navel_up", "ac_p6_navel_down",
                   "ac_p7_navel_r_shoulder", "ac_p8_navel_l_shoulder",
                   "ac_p9_navel_r_thigh", "ac_p10_navel_l_thigh"):
            return shoulder_w * 0.45    # navel — finger must be close
        if pid in ("ac_p2_solar", "ac_p3_mid_abdomen",
                   "ac_p4_above_navel", "ac_p14_lower_left_abdomen"):
            return shoulder_w * 0.50    # abdomen center — slightly relaxed
        return shoulder_w * 0.42        # ribs / waist — more precise

    # ── messages ──────────────────────────────────────────────────────────────

    def _correction_msg(self, pid) -> str:
        msgs = {
            "ac_p1_neck":                  "Place your RIGHT hand on the LEFT side of your neck.",
            "ac_p2_solar":                 "Touch the CENTER of your upper abdomen (solar plexus) with your right index finger.",
            "ac_p3_mid_abdomen":           "Move right index finger one inch BELOW the solar plexus.",
            "ac_p4_above_navel":           "Move right index finger one inch ABOVE your navel.",
            "ac_p5_navel_up":              "Place right index finger INSIDE your navel and pull upward.",
            "ac_p6_navel_down":            "Place right THUMB inside your navel and press downward.",
            "ac_p7_navel_r_shoulder":      "Right index finger in navel — pull toward your RIGHT SHOULDER.",
            "ac_p8_navel_l_shoulder":      "Right index finger in navel — pull toward your LEFT SHOULDER.",
            "ac_p9_navel_r_thigh":         "Right index finger in navel — pull toward your RIGHT THIGH.",
            "ac_p10_navel_l_thigh":        "Right THUMB in navel — push toward your LEFT THIGH.",
            "ac_p11_right_ribs":           "Right index finger one inch below your RIGHT ribcage.",
            "ac_p12_left_ribs":            "Right index finger one inch below your LEFT ribcage.",
            "ac_p13_right_waist":          "Right thumb on the soft area between your RIGHT rib and hip bone.",
            "ac_p14_lower_left_abdomen":   "Right index + middle fingers between navel and LEFT groin crease.",
        }
        return msgs.get(pid, "Keep your right hand on the pressure point.")

    def _hold_msg(self, pid) -> str:
        msgs = {
            "ac_p1_neck":                  "Good — right hand on left neck. Hold and breathe deeply.",
            "ac_p2_solar":                 "Good — touching solar plexus. Hold and breathe.",
            "ac_p3_mid_abdomen":           "Good — touching mid abdomen. Hold and breathe.",
            "ac_p4_above_navel":           "Good — touching above navel. Hold and breathe.",
            "ac_p5_navel_up":              "Good — navel point (pull up). Hold and breathe.",
            "ac_p6_navel_down":            "Good — navel point (push down). Hold and breathe.",
            "ac_p7_navel_r_shoulder":      "Good — navel (right shoulder direction). Hold and breathe.",
            "ac_p8_navel_l_shoulder":      "Good — navel (left shoulder direction). Hold and breathe.",
            "ac_p9_navel_r_thigh":         "Good — navel (right thigh direction). Hold and breathe.",
            "ac_p10_navel_l_thigh":        "Good — navel (left thigh direction). Hold and breathe.",
            "ac_p11_right_ribs":           "Good — below right ribs. Hold and breathe.",
            "ac_p12_left_ribs":            "Good — below left ribs. Hold and breathe.",
            "ac_p13_right_waist":          "Good — right waist point. Hold and breathe.",
            "ac_p14_lower_left_abdomen":   "Good — lower left abdomen point. Hold and breathe.",
        }
        return msgs.get(pid, "Good — hold the point and breathe deeply.")