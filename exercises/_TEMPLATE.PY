"""
exercises/_TEMPLATE.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTRIBUTOR TEMPLATE — SKY Yoga AI Coach

This is the only file you need to write.
Copy this → rename → fill in your exercise → you are done.

DO NOT MODIFY anything in the core/ folder.
DO NOT MODIFY main.py.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 1 — Copy and rename
    cp exercises/_TEMPLATE.py exercises/leg_exercise.py

STEP 2 — Set your EXERCISE_KEY
    Must match exactly with your key in main.py EXERCISE_TIMELINE.
    e.g. EXERCISE_KEY = "leg"

STEP 3 — Define your _PHASES list
    Each phase = one sub-exercise inside your exercise section.
    Every phase needs these fields (see full reference below).

STEP 4 — Write check_pose()
    Return (True, "error message") if user is doing it wrong.
    Return (False, "progress message") if user is doing it right
    but you want to show a coaching tip.
    Return (False, None) if everything is perfect.

STEP 5 — Write detect_rep()
    Increment self.rep_count when user completes one rep.

STEP 6 — Tell the project lead to add your key to main.py
    They add one line to EXERCISE_TIMELINE in main.py:
    {"key": "leg", "start": 727}

That's it. The system loads your file automatically.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE FIELDS REFERENCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Required:
  "id"       : unique string, e.g. "leg_raise"
  "name"     : display name shown on screen, e.g. "Leg Raise"
  "start"    : video seconds when mentor begins demonstrating
               (system shows WATCH state — video plays, no checking)
  "active"   : video seconds when user should start performing
               (system switches to ACTIVE — checking begins)
  "end"      : video seconds when this phase ends
  "target"   : number of reps to complete (0 if not applicable)
  "watch_msg": message shown during WATCH state

Optional:
  "check_landmarks" : list of landmark indices the system uses to
                      detect if reference video is zoomed in.
                      Default: [11,12,13,14,15,16]
                      Use body parts relevant to your exercise.
  "zoom"     : True if this segment is a close-up shot.
               System skips all checks and lets video play freely.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LANDMARK INDEX REFERENCE (MediaPipe Pose)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

HEAD:
  0  = nose
  7  = left ear
  8  = right ear

ARMS:
  11 = left shoulder    12 = right shoulder
  13 = left elbow       14 = right elbow
  15 = left wrist       16 = right wrist

FINGERS (approximate tips from pose model):
  17 = left pinky tip   18 = right pinky tip
  19 = left index tip   20 = right index tip
  21 = left thumb tip   22 = right thumb tip

LEGS:
  23 = left hip         24 = right hip
  25 = left knee        26 = right knee
  27 = left ankle       28 = right ankle
  29 = left heel        30 = right heel
  31 = left foot index  32 = right foot index

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HELPER FUNCTIONS (from core.utils)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

lm_px(lm, index, width, height)
    Converts a landmark to pixel coordinates (x, y).
    Example: knee = lm_px(user_lm, 25, w, h)

calculate_angle(point_a, point_b, point_c)
    Returns angle in degrees at point_b.
    All points must be pixel tuples from lm_px().
    Example: angle = calculate_angle(hip, knee, ankle)
             if angle < 90: return True, "Bend more"

dist(point_a, point_b)
    Returns pixel distance between two points.
    Example: knee_gap = dist(left_knee, right_knee)
             if knee_gap > w * 0.3: return True, "Bring knees closer"

NORMALIZED COORDS (use lm[idx].x and lm[idx].y directly — range 0.0 to 1.0)
    Use these for comparisons like "is wrist above hip":
    if user_lm[15].y < user_lm[23].y:   # wrist y < hip y = wrist is higher
        ...  # arm is raised
    Smaller y = higher on screen.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
check_pose() RETURN VALUES — CRITICAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Returns a TUPLE: (is_error: bool, message: str | None)

(True,  "Your message")   → POSE IS WRONG
                            Video pauses after 10 bad frames.
                            Skeleton turns red.
                            Message shown to user.

(False, "Your message")   → POSE IS RIGHT but show a coaching tip
                            Video keeps playing.
                            Skeleton stays green.
                            Message shown to user.

(False, None)             → POSE IS PERFECT, nothing to say
                            Video keeps playing.
                            Skeleton stays green.
                            System shows "Good form X/Y" automatically.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
self.rep_count and self.phase
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

self.rep_count  — increment this when user completes a rep
self.phase      — use this string to track movement state
                  e.g. "UP" / "DOWN", "WIDE" / "CLOSE", etc.
                  It resets automatically when the phase changes.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WORKED EXAMPLE — Leg Raise
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def check_pose(self, user_lm, ref_lm, w, h, phase):
        lh  = lm_px(user_lm, 23, w, h)   # left hip
        lk  = lm_px(user_lm, 25, w, h)   # left knee
        la  = lm_px(user_lm, 27, w, h)   # left ankle

        # Check knee angle (straight leg = ~180 degrees)
        angle = calculate_angle(lh, lk, la)
        if angle < 160:
            return True, "Keep your leg straight"

        return False, None   # pose is correct

    def detect_rep(self, user_lm, w, h):
        # Rep = leg raised above hip level, then lowered
        ankle_y    = user_lm[27].y   # normalized 0–1
        hip_y      = user_lm[23].y

        leg_raised = ankle_y < hip_y  # ankle higher than hip = leg raised

        if leg_raised and self.phase == "DOWN":
            self.phase = "UP"
        if not leg_raised and self.phase == "UP":
            self.phase = "DOWN"
            self.rep_count += 1

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from core.base_controller import BaseController
from core.utils import calculate_angle, dist, lm_px

# ── STEP 2: Change this to your exercise key ──────────────────────────
EXERCISE_KEY = "template"   # e.g. "leg", "eye", "neuro", "kapalabhati"

# ── STEP 3: Define your phases ────────────────────────────────────────
_PHASES = [
    {
        # --- Required fields ---
        "id":        "phase_1",          # unique id for this phase
        "name":      "My Exercise",      # shown on screen
        "start":     0,                  # video seconds: mentor starts
        "active":    10,                 # video seconds: user starts
        "end":       60,                 # video seconds: phase ends
        "target":    5,                  # reps to complete (0 = no counting)
        "watch_msg": "Watch the mentor carefully",

        # --- Optional fields ---
        "check_landmarks": [11,12,13,14,15,16],   # for zoom detection
        # "zoom": True,                            # uncomment if close-up shot
    },
    # Add more phases below if your exercise has multiple sub-exercises
    # {
    #     "id":        "phase_2",
    #     "name":      "My Exercise Part 2",
    #     "start":     60,
    #     "active":    65,
    #     "end":       120,
    #     "target":    5,
    #     "watch_msg": "Watch the next movement",
    #     "check_landmarks": [23,24,25,26,27,28],
    # },
]


class WorkoutController(BaseController):
    """
    Your exercise controller.
    Only implement check_pose() and detect_rep().
    Everything else (video control, state machine, UI) is handled automatically.
    """

    def __init__(self):
        super().__init__()
        # Add any state variables your exercise needs here
        # self.phase is already available from BaseController for UP/DOWN tracking
        # Examples:
        # self._side = "RIGHT"          # for alternating sides
        # self._hold_start = None       # for timed holds

    def phases(self) -> list:
        """Do not change this. Returns your _PHASES list."""
        return _PHASES

    def on_phase_change(self, phase: dict):
        """
        Called automatically when video moves to a new phase.
        Reset any state variables here.
        self.rep_count and self.phase are reset automatically.
        """
        pass   # add your resets here if needed

    # ── STEP 4: Write your pose check ────────────────────────────────
    def check_pose(self, user_lm, ref_lm, w, h, phase) -> tuple:
        """
        Called every frame during ACTIVE state.
        user_lm  : user's live pose landmarks
        ref_lm   : reference video pose landmarks (may be None if zoomed)
        w, h     : frame width and height in pixels
        phase    : current phase dict (access fields like phase["id"])

        Returns:
            (True,  "message") → wrong pose  → video pauses, red skeleton
            (False, "message") → right pose, show tip → video plays, green
            (False, None)      → perfect → video plays, green, auto "Good form"

        ── WRITE YOUR RULES BELOW ──────────────────────────────────────
        """

        # Example — replace with your exercise logic:
        # pid = phase["id"]
        # if pid == "phase_1":
        #     return self._check_phase_1(user_lm, w, h)
        # elif pid == "phase_2":
        #     return self._check_phase_2(user_lm, w, h)

        return False, None   # ← remove this line and add your logic

    # ── STEP 5: Write your rep counter ───────────────────────────────
    def detect_rep(self, user_lm, w, h):
        """
        Called every frame during ACTIVE state (after check_pose).
        Increment self.rep_count when user completes one rep.

        Use self.phase to track movement state (e.g. "UP"/"DOWN").
        self.phase resets automatically on each phase change.

        ── WRITE YOUR REP LOGIC BELOW ──────────────────────────────────
        """

        # Example — replace with your exercise logic:
        # ankle_y = user_lm[27].y   # normalized 0-1
        # hip_y   = user_lm[23].y
        # raised  = ankle_y < hip_y
        # if raised and self.phase == "DOWN":
        #     self.phase = "UP"
        # if not raised and self.phase == "UP":
        #     self.phase = "DOWN"
        #     self.rep_count += 1

        pass   # ← remove this line and add your logic

    # ── Add your private helper methods below ────────────────────────
    # def _check_phase_1(self, lm, w, h) -> tuple:
    #     knee = lm_px(lm, 25, w, h)
    #     ...
    #     return False, None