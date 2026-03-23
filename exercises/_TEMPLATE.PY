"""
exercises/_template.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW TO ADD A NEW EXERCISE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Copy this file → exercises/my_exercise.py
2. Set EXERCISE_KEY to match the key in main.py's EXERCISE_TIMELINE
3. Fill in _PHASES (see schema below)
4. Implement check_pose() using angle/dist rules — NO similarity
5. Implement detect_rep() to increment self.rep_count
6. Done — the registry auto-discovers it on startup

PHASE SCHEMA:
─────────────────────────────────────────────────────────────────
{
  "id":      str,           # unique within this exercise
  "name":    str,           # shown in UI banner
  "start":   float,         # video timestamp — WATCH begins here
  "active":  float,         # video timestamp — user checking begins
  "end":     float,         # video timestamp — phase ends
  "target":  int,           # minimum reps before video moves on
  "watch_msg": str,         # message shown during WATCH phase
  "check_landmarks": [int], # landmark indices needed (visibility check)
  "zoom":    bool,          # optional — if True, skip user checking entirely
}

FLOW (handled automatically by BaseController):
  video_pos < active   → WATCH  — show watch_msg, no user eval
  active <= pos < end  → ACTIVE — check_pose() + detect_rep() each frame
  pos >= end           → if rep_count < target: hold video 10s
                          else: continue

check_pose() contract:
  Returns (is_error: bool, message: str | None)
  is_error=True  → counts toward error streak → video pauses after 12 frames
  is_error=False → soft guidance only, video keeps playing
  message=None   → show generic "Good form X/Y" from base

detect_rep() contract:
  Increment self.rep_count whenever the user completes one full rep.
  Use MotionTracker.cycle_count() for rotation/oscillation reps.
  Use state machines (UP→DOWN→UP) for directional reps.

AVAILABLE HELPERS (from core.utils):
  angle(a, b, c)          → degrees at joint b
  dist(p1, p2)            → pixel distance
  px(lm, idx, w, h)       → landmark → (x_px, y_px)
  visible(lm, *idxs)      → True if all landmarks visible >= 0.55
  shoulder_width(lm,w,h)  → pixels, use to normalise distances
  torso_len(lm,w,h)       → pixels, use to normalise distances

AVAILABLE TRACKERS:
  MotionTracker(window_sec, min_arc_px)  → .update(x,y) .is_moving() .cycle_count()
  BreathDetector(min_breath_sec)         → .update(shoulder_y) .new_breaths()
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from core.base_controller import BaseController
from core.utils import angle, dist, px, visible, shoulder_width

EXERCISE_KEY = "template"   # ← change this

_PHASES = [
    {
        "id":      "phase_1",
        "name":    "Phase One",
        "start":   0,     # video timestamp — mentor demonstrates
        "active":  10,    # user checking begins here
        "end":     60,
        "target":  5,
        "watch_msg": "Watch the mentor carefully",
        "check_landmarks": [11, 12, 13, 14, 15, 16],
    },
    # add more phases...
]


class WorkoutController(BaseController):

    def __init__(self):
        super().__init__()
        # initialise your trackers / state machines here
        self._my_state = "START"

    def phases(self) -> list:
        return _PHASES

    def on_phase_change(self, phase: dict):
        # reset any internal state when switching phases
        self._my_state = "START"

    def check_pose(self, user_lm, w: int, h: int, phase: dict) -> tuple:
        """
        Return (is_error, message).
        Use angle() / dist() / shoulder_width() for all checks.
        Never call pose_similarity here.
        """
        pid = phase["id"]

        if pid == "phase_1":
            sw  = shoulder_width(user_lm, w, h)
            lwr = px(user_lm, 15, w, h)
            rwr = px(user_lm, 16, w, h)

            # Example: check wrists are raised
            if user_lm[15].y > user_lm[11].y:
                return True, "Raise your left arm"   # is_error=True → counts toward pause
            if user_lm[16].y > user_lm[12].y:
                return True, "Raise your right arm"

        return False, None   # all good

    def detect_rep(self, user_lm, w: int, h: int):
        """Increment self.rep_count when a rep completes."""
        p = self._get_phase(self._video_pos)
        if not p:
            return
        # example: simple up/down state machine
        wrist_up = user_lm[15].y < user_lm[11].y - 0.05
        if wrist_up and self._my_state == "DOWN":
            self._my_state = "UP"
        if not wrist_up and self._my_state == "UP":
            self._my_state = "DOWN"
            self.rep_count += 1