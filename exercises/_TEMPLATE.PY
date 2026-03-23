"""
exercises/_template.py — Template for new SKY Yoga exercises
=============================================================

HOW TO CREATE A NEW EXERCISE
──────────────────────────────
  1. Copy this file:   cp exercises/_template.py exercises/leg_exercise.py
  2. Set EXERCISE_KEY to match the key in main.py EXERCISE_TIMELINE
  3. Fill in _PHASES with timestamps from the mentor video
  4. Implement check_pose()  → returns form feedback
  5. Implement detect_rep()  → increments self.rep_count
  6. Optionally override on_phase_change() to reset state machines
  7. Restart — exercise_registry.py auto-discovers it

No other registration is needed.

══════════════════════════════════════════════════════════════
PHASE TIMESTAMPS  (how to fill _PHASES correctly)
══════════════════════════════════════════════════════════════

  start  : video second when the mentor BEGINS showing this move
           → "Watch Carefully" banner appears here
  active : start + ~10s  (mentor finishes demo, user starts doing)
           → Coach switches from WATCH to ACTIVE, reps start counting
  end    : video second when this move ends / next one begins

  Rule: active = start + 10  is a safe default if unsure.
  Keep end < next phase's start OR equal to it (no gaps needed).

══════════════════════════════════════════════════════════════
check_pose() CONTRACT
══════════════════════════════════════════════════════════════

  Returns (is_error: bool, message: str | None)

  (True,  "message")  →  hard error: skeleton turns RED,
                          video pauses after 12 consecutive error frames
  (False, "message")  →  soft hint: skeleton stays GREEN, no pause
  (False, None)       →  good form, no message needed

  Rules:
  • Always call visible() FIRST — return (False, None) if landmarks missing
  • Normalize ALL distances by shoulder_width(lm, w, h)
  • Use angle(a, b, c) from core.utils — never raw math.acos
  • Never add your own debouncing — base_controller handles 12-frame threshold

══════════════════════════════════════════════════════════════
detect_rep() CONTRACT
══════════════════════════════════════════════════════════════

  Called every frame during ACTIVE state (after check_pose).
  Increment self.rep_count when a complete rep is detected.

  CRITICAL: use self._active_phase (NOT self._get_phase) to read
  the current phase id/target — _get_phase returns None during
  HOLD state and inter-phase gaps, breaking rep counting.

  Example pattern (state machine):
    if self._my_state == "DOWN" and wrists_above_nose:
        self._my_state = "UP"
    elif self._my_state == "UP" and wrists_below_hips:
        self._my_state = "DOWN"
        self.rep_count += 1          # ← always additive, never =

══════════════════════════════════════════════════════════════
MEDIAPIPE LANDMARK INDICES (quick reference)
══════════════════════════════════════════════════════════════

  0  nose        11 L shoulder   12 R shoulder
  13 L elbow     14 R elbow      15 L wrist    16 R wrist
  23 L hip       24 R hip        25 L knee     26 R knee
  27 L ankle     28 R ankle      29 L heel     30 R heel

  Coordinate system (normalised 0–1):
    x: 0 = left edge,  1 = right edge  of frame
    y: 0 = top edge,   1 = bottom edge of frame
    → LOWER y value = HIGHER on screen

══════════════════════════════════════════════════════════════
"""

import time
from core.base_controller import BaseController
from core.utils import angle, dist, px, visible, shoulder_width
from core.motion_tracker import MotionTracker   # only import if needed

# ─────────────────────────────────────────────────────────────────────────────
# EXERCISE KEY  — must match the key in EXERCISE_TIMELINE in main.py
# ─────────────────────────────────────────────────────────────────────────────

EXERCISE_KEY = "example"   # ← change this

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS  (timing / threshold values go here, not hardcoded below)
# ─────────────────────────────────────────────────────────────────────────────

# Example: hold-based exercise
HOLD_TARGET_SEC = 10.0    # how long to hold a position
REST_SEC        = 4.0     # rest time between reps

# Example: position thresholds (normalised by shoulder_width)
WRIST_JOIN_RATIO  = 0.30  # wrists "joined" if gap < 30% of shoulder width
ARM_SPREAD_RATIO  = 1.50  # arms "spread" if gap > 150% of shoulder width

# ─────────────────────────────────────────────────────────────────────────────
# PHASES
# ─────────────────────────────────────────────────────────────────────────────

_PHASES = [
    # ── Phase 1: timed hold ───────────────────────────────────────────────
    {
        "id":               "p1_example_hold",
        "name":             "Example Hold",
        "start":            0,       # ← video second: mentor starts showing
        "active":           10,      # ← video second: user starts doing
        "end":              60,      # ← video second: move ends
        "target":           3,       # reps required (0 = no enforcement)
        "watch_msg":        "Watch — raise both arms and hold for 4 breaths",
        "check_landmarks":  [11, 12, 15, 16, 23, 24],   # landmarks needed
    },

    # ── Phase 2: rotation (use side field) ────────────────────────────────
    {
        "id":               "p2_right_rotation",
        "name":             "Right Hand Rotation",
        "start":            60,
        "active":           70,
        "end":              100,
        "target":           5,
        "side":             "right",  # "right" | "left" | "both"
        "watch_msg":        "Watch — extend right arm, rotate wrist clockwise",
        "check_landmarks":  [12, 14, 16, 24],
    },

    # ── Phase 3: zoom-only (user just watches, no evaluation) ─────────────
    {
        "id":               "p3_zoom",
        "name":             "Watch Detail",
        "start":            100,
        "active":           100,
        "end":              115,
        "target":           0,
        "zoom":             True,    # skips all evaluation
        "watch_msg":        "Watch closely — observe the technique",
        "check_landmarks":  [],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# CONTROLLER
# ─────────────────────────────────────────────────────────────────────────────

class WorkoutController(BaseController):

    def __init__(self):
        super().__init__()

        # ── Motion trackers (one per limb you need to track) ──────────────
        # window_sec: how many seconds of history to keep
        # min_arc_px: minimum movement in pixels to count as "moving"
        self._tracker_r = MotionTracker(window_sec=1.5, min_arc_px=12)
        self._tracker_l = MotionTracker(window_sec=1.5, min_arc_px=12)

        # ── State machine variables ────────────────────────────────────────
        # For hold-based exercises
        self._hold_state   = "REST"   # REST | HOLDING | RESTING
        self._hold_start   = None     # wall-clock when hold began
        self._rest_start   = None     # wall-clock when rest began

        # For position-cycle exercises (e.g. spread → together → spread)
        self._cycle_state  = "POS_A"  # POS_A | POS_B

        # For rotation exercises
        self._last_cyc_r   = 0        # last known cycle count (right)
        self._last_cyc_l   = 0        # last known cycle count (left)

        # Any per-rep flags
        self._did_reach_b  = False    # reached position B this cycle?

    # ─────────────────────────────────────────────────────────────────────
    # REQUIRED: return the phases list
    # ─────────────────────────────────────────────────────────────────────

    def phases(self) -> list:
        return _PHASES

    # ─────────────────────────────────────────────────────────────────────
    # OPTIONAL: reset state when phase changes
    # ─────────────────────────────────────────────────────────────────────

    def on_phase_change(self, phase: dict):
        """Called by base_controller every time a new phase starts."""
        # Always reset motion trackers
        self._tracker_r.reset()
        self._tracker_l.reset()

        # Always reset state machine variables
        self._hold_state   = "REST"
        self._hold_start   = None
        self._rest_start   = None
        self._cycle_state  = "POS_A"
        self._last_cyc_r   = 0
        self._last_cyc_l   = 0
        self._did_reach_b  = False

        # NOTE: self.rep_count is reset automatically by base_controller.
        # Do NOT reset it here.

    # ─────────────────────────────────────────────────────────────────────
    # REQUIRED: evaluate form, return feedback
    # ─────────────────────────────────────────────────────────────────────

    def check_pose(self, user_lm, w: int, h: int, phase: dict) -> tuple:
        """
        Called every ACTIVE frame. Return (is_error, message).
        """
        pid = phase["id"]

        if pid == "p1_example_hold":
            return self._check_hold(user_lm, w, h)

        elif pid == "p2_right_rotation":
            return self._check_rotation(user_lm, w, h, phase)

        # Zoom phases never reach check_pose (filtered by base_controller)
        return (False, None)

    # ─────────────────────────────────────────────────────────────────────
    # REQUIRED: count reps
    # ─────────────────────────────────────────────────────────────────────

    def detect_rep(self, user_lm, w: int, h: int):
        """
        Called every ACTIVE frame (after check_pose).
        Use self._active_phase — NOT self._get_phase() — to read phase id/target.
        _get_phase() returns None during HOLD state and gaps.
        """
        p = self._active_phase   # ← always use this, never _get_phase()
        if not p:
            return
        pid = p["id"]

        if pid == "p1_example_hold":
            self._rep_hold(user_lm, w, h)

        elif pid == "p2_right_rotation":
            self._rep_rotation(p)

    # ─────────────────────────────────────────────────────────────────────
    # PATTERN A: HOLD-BASED REP
    # Raise → hold N seconds → lower → rest → count 1 rep
    # ─────────────────────────────────────────────────────────────────────

    def _is_in_hold_position(self, lm, w, h) -> bool:
        """
        Detect whether user is in the target hold position.
        Replace with your actual position check.
        Example: both wrists above nose AND joined.
        """
        if not visible(lm, 0, 15, 16, 11, 12):
            return False
        # wrists above nose
        if lm[15].y >= lm[0].y or lm[16].y >= lm[0].y:
            return False
        # palms joined
        sw  = shoulder_width(lm, w, h)
        gap = dist(px(lm, 15, w, h), px(lm, 16, w, h)) / sw
        return gap < WRIST_JOIN_RATIO

    def _is_in_rest_position(self, lm) -> bool:
        """Detect arms-down / rest position. Replace with yours."""
        if not visible(lm, 15, 16, 23, 24):
            return False
        hip_y = (lm[23].y + lm[24].y) / 2
        return lm[15].y > hip_y and lm[16].y > hip_y

    def _check_hold(self, lm, w, h) -> tuple:
        """Feedback text for hold phase."""
        if not visible(lm, 11, 12, 15, 16, 23, 24):
            return (False, None)

        now = time.time()
        st  = self._hold_state

        if st == "REST":
            return (False, "Get into position to begin")

        if st == "HOLDING":
            held      = (now - self._hold_start) if self._hold_start else 0.0
            remaining = max(0.0, HOLD_TARGET_SEC - held)
            if not self._is_in_hold_position(lm, w, h):
                return (False, f"Hold released after {held:.0f}s — lower arms to rest")
            if remaining > 0:
                return (False, f"Hold — {remaining:.0f}s remaining")
            return (False, "Hold complete! Return to rest position")

        if st == "RESTING":
            rested    = (now - self._rest_start) if self._rest_start else 0.0
            remaining = max(0.0, REST_SEC - rested)
            if remaining > 0:
                return (False, f"Rest — {remaining:.0f}s more")
            return (False, "Ready — get into position for next rep")

        return (False, None)

    def _rep_hold(self, lm, w, h):
        """State transitions for hold rep counting."""
        now = time.time()
        st  = self._hold_state

        if st == "REST":
            if self._is_in_hold_position(lm, w, h):
                self._hold_state = "HOLDING"
                self._hold_start = now

        elif st == "HOLDING":
            if self._hold_start is None:
                self._hold_start = now
            held = now - self._hold_start
            # Auto-advance after full hold, or on early release
            if held >= HOLD_TARGET_SEC or self._is_in_rest_position(lm):
                self._hold_state = "RESTING"
                self._rest_start = now

        elif st == "RESTING":
            if self._rest_start is None:
                self._rest_start = now
            if now - self._rest_start >= REST_SEC:
                self.rep_count  += 1          # ← count rep here
                self._hold_state = "REST"
                self._hold_start = None
                self._rest_start = None

    # ─────────────────────────────────────────────────────────────────────
    # PATTERN B: ROTATION REP  (wrist/ankle circles via MotionTracker)
    # ─────────────────────────────────────────────────────────────────────

    def _check_rotation(self, lm, w, h, phase) -> tuple:
        """Form check for rotation exercises."""
        side = phase.get("side", "right")
        done = self.rep_count

        if side in ("right", "both"):
            if not visible(lm, 12, 14, 16, 24):
                return (False, None)
            rs  = px(lm, 12, w, h)
            re  = px(lm, 14, w, h)
            rwr = px(lm, 16, w, h)
            rh  = px(lm, 24, w, h)
            sw  = shoulder_width(lm, w, h)
            if dist(rwr, rh) / sw < 0.20:
                return (True, "Extend your right arm further out")
            if angle(rs, re, rwr) < 100:
                return (True, "Straighten your right arm")
            if not self._tracker_r.is_moving():
                return (False, f"Rotate your right hand  {done} / {phase.get('target', 5)}")

        if side in ("left", "both"):
            if not visible(lm, 11, 13, 15, 23):
                return (False, None)
            ls  = px(lm, 11, w, h)
            le  = px(lm, 13, w, h)
            lwr = px(lm, 15, w, h)
            lh  = px(lm, 23, w, h)
            sw  = shoulder_width(lm, w, h)
            if dist(lwr, lh) / sw < 0.20:
                return (True, "Extend your left arm further out")
            if angle(ls, le, lwr) < 100:
                return (True, "Straighten your left arm")
            if not self._tracker_l.is_moving():
                return (False, f"Rotate your left hand  {done} / {phase.get('target', 5)}")

        return (False, f"Keep rotating  {done} / {phase.get('target', 5)}")

    def _rep_rotation(self, phase: dict):
        """Count reps from MotionTracker cycle count."""
        side   = phase.get("side", "right")
        target = phase.get("target", 5)

        # ADDITIVE pattern: new_cycles = total_now - total_at_last_count
        if side == "right":
            c = self._tracker_r.cycle_count()
            n = c - self._last_cyc_r
            if n > 0:
                self.rep_count   = min(self.rep_count + n, target)
                self._last_cyc_r = c

        elif side == "left":
            c = self._tracker_l.cycle_count()
            n = c - self._last_cyc_l
            if n > 0:
                self.rep_count   = min(self.rep_count + n, target)
                self._last_cyc_l = c

        elif side == "both":
            cr = self._tracker_r.cycle_count()
            cl = self._tracker_l.cycle_count()
            n  = max(cr - self._last_cyc_r, cl - self._last_cyc_l)
            if n > 0:
                self.rep_count   = min(self.rep_count + n, target)
                self._last_cyc_r = cr
                self._last_cyc_l = cl

    # ─────────────────────────────────────────────────────────────────────
    # PATTERN C: POSITION CYCLE  (A → B → A = 1 rep)
    # Example: arms forward → spread to T → return forward
    # ─────────────────────────────────────────────────────────────────────

    def _is_pos_a(self, lm, w, h) -> bool:
        """
        Detect position A (e.g. arms forward, palms joined).
        Replace with your actual detection.
        """
        if not visible(lm, 11, 12, 15, 16):
            return False
        sw  = shoulder_width(lm, w, h)
        lwr = px(lm, 15, w, h)
        rwr = px(lm, 16, w, h)
        gap = dist(lwr, rwr) / sw
        # wrists close → arms pointing forward (overlap in 2D)
        if gap > 0.50:
            return False
        # at shoulder height
        mid_y  = (lm[15].y + lm[16].y) / 2
        sh_y   = (lm[11].y + lm[12].y) / 2
        return abs(mid_y - sh_y) < 0.25

    def _is_pos_b(self, lm, w, h) -> bool:
        """
        Detect position B (e.g. arms spread to T-pose).
        Replace with your actual detection.
        """
        if not visible(lm, 11, 12, 15, 16):
            return False
        sw  = shoulder_width(lm, w, h)
        lwr = px(lm, 15, w, h)
        rwr = px(lm, 16, w, h)
        gap = dist(lwr, rwr) / sw
        if gap < ARM_SPREAD_RATIO:
            return False
        if abs(lm[15].y - lm[11].y) > 0.22:
            return False
        if abs(lm[16].y - lm[12].y) > 0.22:
            return False
        return True

    def _check_cycle(self, lm, w, h) -> tuple:
        """Feedback text for A→B→A cycle exercise."""
        if not visible(lm, 11, 12, 15, 16):
            return (False, None)
        done = self.rep_count
        if self._cycle_state == "POS_A":
            if self._is_pos_a(lm, w, h):
                return (False, f"Good — now move to position B  {done}")
            return (False, "Return to starting position A")
        else:  # POS_B
            if self._is_pos_b(lm, w, h):
                return (False, f"Good — now return to position A  {done}")
            return (False, "Move to position B")

    def _rep_cycle(self, lm, w, h):
        """State machine for A→B→A rep counting."""
        if self._cycle_state == "POS_A":
            if self._is_pos_b(lm, w, h):          # reached B
                self._cycle_state = "POS_B"
        elif self._cycle_state == "POS_B":
            if self._is_pos_a(lm, w, h):           # returned to A
                self._cycle_state = "POS_A"
                self.rep_count   += 1               # ← count rep here

    # ─────────────────────────────────────────────────────────────────────
    # MOTION TRACKER UPDATE  (call in check_pose or detect_rep)
    # ─────────────────────────────────────────────────────────────────────

    def _update_trackers(self, lm, w, h):
        """Feed latest landmark positions into motion trackers."""
        self._tracker_r.update(lm[16].x * w, lm[16].y * h)   # right wrist
        self._tracker_l.update(lm[15].x * w, lm[15].y * h)   # left wrist


# ─────────────────────────────────────────────────────────────────────────────
# CHECKLIST BEFORE DEPLOYING A NEW EXERCISE
# ─────────────────────────────────────────────────────────────────────────────
#
#  [ ] EXERCISE_KEY matches a key in EXERCISE_TIMELINE in main.py
#  [ ] All _PHASES have: id, name, start, active, end, target, watch_msg,
#      check_landmarks
#  [ ] active ≈ start + 10  (short watch window before user starts)
#  [ ] No gaps between phases where user would see stale state
#      (set phase end = next phase start)
#
#  check_pose():
#  [ ] Calls visible() first on check_landmarks — returns (False, None) if missing
#  [ ] Uses shoulder_width() to normalise ALL distances
#  [ ] Uses angle() from core.utils
#  [ ] Returns (bool, str|None) on ALL code paths
#  [ ] Hard errors use True  → soft hints use False
#
#  detect_rep():
#  [ ] Uses self._active_phase — NOT self._get_phase()
#  [ ] Only increments self.rep_count (never assigns)
#  [ ] Caps with min(self.rep_count + n, target) for rotation reps
#
#  on_phase_change():
#  [ ] Resets all trackers (.reset())
#  [ ] Resets all state variables
#  [ ] Does NOT reset self.rep_count (base_controller handles that)
#
#  General:
#  [ ] No custom debouncing (base_controller handles 12-frame threshold)
#  [ ] No ref_lm or similarity scoring
#  [ ] MotionTracker imported only if rotation/swing detection needed
#  [ ] time imported only if hold/rest timers are needed
# ─────────────────────────────────────────────────────────────────────────────