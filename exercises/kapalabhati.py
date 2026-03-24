import time
from core.base_controller import BaseController
from core.utils import angle, dist, px, visible, shoulder_width
from core.motion_tracker import MotionTracker

# EXERCISE CONFIGURATION
EXERCISE_KEY = "kapalabhati"

# CONSTANTS
# ═════════════════════════════════════════════════════════════════════════
# For kapalabhati threshold
STRAIGT_BACK_THRESHOLD = 80.0 #Threshold for spine alignment
HAND_TO_NOSE_RATIO = 0.40 # Stricter < 0.40 < Lenient (normalized by shoulder width)
MAX_SHOULDER_TILT_RATIO = 0.12  # Max allowable vertical diff between shoulders
MAX_HEAD_DRIFT_RATIO = 0.20    # Max distance nose can drift from center
HAND_LOW_OFFSET = 0.15 # Higher means hands must be further below the hip line

_PHASES = [
    # ROUND 1
    {
        "id": "r1_intake",
        "name": "Breath Intake & Sit",
        "start": 2266,        # 37:46
        "active": 2266,
        "end": 2276,          # 37:56
        "target": 1,
        "watch_msg": "Deep inhale and sit in stillness.",
    },
    {
        "id": "r1_alt_breathing",
        "name": "Alternative Breathing",
        "start": 2277,        # 37:57
        "active": 2277,
        "end": 2300,          # 38:20
        "target": 10,         # Adjust target reps as needed
        "watch_msg": "Perform alternative nostril breathing.",
    },
    # ROUND 2
    {
        "id": "r2_intake",
        "name": "Breath Intake & Sit",
        "start": 2301,        # 38:21
        "active": 2301,
        "end": 2326,          # 38:46
        "target": 1,
        "watch_msg": "Deep inhale and sit in stillness.",
    },
    {
        "id": "r2_alt_breathing",
        "name": "Alternative Breathing",
        "start": 2327,        # 38:47
        "active": 2327,
        "end": 2349,          # 39:09
        "target": 10,
        "watch_msg": "Perform alternative nostril breathing.",
    },
    # ROUND 3
    {
        "id": "r3_intake",
        "name": "Breath Intake & Sit",
        "start": 2350,        # 39:10
        "active": 2350,
        "end": 2369,          # 39:29
        "target": 1,
        "watch_msg": "Deep inhale and sit in stillness.",
    },
    {
        "id": "r3_alt_breathing",
        "name": "Alternative Breathing",
        "start": 2370,        # 39:30
        "active": 2370,
        "end": 2392,          # 39:52
        "target": 10,
        "watch_msg": "Perform alternative nostril breathing.",
    },
    # FINAL RETENTION
    {
        "id": "r4_intake_final",
        "name": "Final Intake & Sit",
        "start": 2393,        # 39:53
        "active": 2393,
        "end": 2413,          # 40:13
        "target": 1,
        "watch_msg": "Final deep inhale. Observe the stillness.",
    }
]

# WORKOUT CONTROLLER
# ═════════════════════════════════════════════════════════════════════════

class WorkoutController(BaseController):
    """
    Main controller for this exercise.
    Implement check_pose(), detect_rep(), and optionally on_phase_change().
    """

    def __init__(self):
        super().__init__()
        self._tracker_r = MotionTracker(window_sec=1.5, min_arc_px=12)
        self._tracker_l = MotionTracker(window_sec=1.5, min_arc_px=12)
        self._hold_state = "REST"
        self._hold_start = None
        self._rest_start = None

    def phases(self) -> list:
        """Required: return the _PHASES list."""
        return _PHASES

    def on_phase_change(self, phase: dict):
        """Optional: reset state machines when phase changes."""
        self._tracker_r.reset()
        self._tracker_l.reset()
        self._hold_state = "REST"
        self._hold_start = None
        self._rest_start = None

    def check_pose(self, lm, w: int, h: int, phase: dict) -> tuple:
        """
        Validate visibility, spine alignment, and phase-specific hand positions.
        Returns: (is_error: bool, message: str | None)
        """
        pid = phase["id"]
        sw = shoulder_width(lm,w,h)

        # Visibility check
        # Ensures if head, shoulders, wrists, and hips are in the frame
        required_ids = [0, 11, 12, 15, 16, 23, 24]
        if not visible(lm, *required_ids):
            return (True, "Ensure your full upper body is visible")
        
        # Spine and alignment (front view)
        # Check for side-leaning (shoulder Y-diff)
        shoulder_tilt = abs(lm[11].y - lm[12].y)
        if sw > MAX_SHOULDER_TILT_RATIO:
            return (True, "Level your shoulders and sit straight")
        
        # Check for head centered (Nose relative to shoulders)
        shoulder_mid_x = (lm[11].x + lm[12].x) /2
        head_drift = abs(lm[0].x - shoulder_mid_x)
        if head_drift > MAX_HEAD_DRIFT_RATIO :
            return (True, "Keep your head centered over your spine")
        
        # Phase routing
        if "intake" in pid:
            return self._check_intake_pose(lm, w, h, sw)
        
        if "alt_breathing" in pid:
            return self._check_breathing_pose(lm, w, h, sw)
        
        return (False, None)

    def detect_rep(self, lm, w: int, h: int):
        """
        Detects Kapalabhati breaths by tracking shoulder  movement.
        Updates self.rep_count according to base_controller requirements.
        """
        # Only detects shoulder jerks during 'alt_breathing' phase 
        # or self._active_phases
        if not self._active_phase or "alt_breathing" not in self._active_phase.get("id", ""):
            return
        
        # Get pixel coordinates for the shoulders to track the Y-coordinates
        # for the "jerk"
        r_shoulder_y = lm[12].y * h
        l_shoulder_y = lm[11].y * h

        # Update motion trackers with the current vertical position
        # Returns True if it detects an 'arc' (sudden updward-downward jerk)
        is_jerk_r = self._tracker_r.update(r_shoulder_y)
        is_jerk_l = self._tracker_l.update(l_shoulder_y)

        # Increment the rep count
        # Updates the rep_count if a jerk is noticed via Motion Capture
        # base_controller handles the reset
        if is_jerk_r or is_jerk_l:
            self.rep_count += 1

    # ─────────────────────────────────────────────────────────────────────
    # POSE DETECTION FOR THE PHASES
    # ─────────────────────────────────────────────────────────────────────
    def _check_intake_pose(self, lm, w, h, sw) -> tuple:
        """
        Logic for the 'Sit & Inhale' phases.
        In Mediapipe, Y increases downward. Hands on knees must have 
        a HIGHER Y value than the hips.
        """
        avg_hip_y = (lm[23].y + lm[24].y) / 2
        knee_zone_y = avg_hip_y + HAND_LOW_OFFSET

        # If hand Y is LESS than hip Y, it is ABOVE the hips.
        # (Because the camera captures a 2D projection while you are facing it, 
        # your hips appear higher on the screen than your knees.)
        if lm[15].y < knee_zone_y or lm[16].y < knee_zone_y:
            return (True, "Lower your hands to your knees")
        
        return (False, 'Hold the breath and stay still')
        

    def _check_breathing_pose(self, lm, w, h, sw) -> tuple:
        """
        Ensures the left thumb (21) and left index finger (19) 
        are positioned near the nose (0).
        """
        # Get pixel coordinates for the nose and the specific fingers
        nose_px = px(lm, 0, w, h)
        l_thumb_px = px(lm, 21, w, h)
        l_index_px = px(lm, 19, w, h)

        # Calculate the normalized distances(divided by shoulder width)
        dist_thumb = dist(l_thumb_px, nose_px) / sw
        dist_index = dist(l_index_px, nose_px) / sw

        # Validation logic
        if dist_thumb > HAND_TO_NOSE_RATIO or dist_index > HAND_TO_NOSE_RATIO:
            return (True, "Place your left thumb and index finger near your nose")
        
        return (False, "Continue rhythmic breathing")