"""
core/base_controller.py — BaseController abstract class

Implements the THREE JOBS of a real AI coach:
  JOB 1 (WATCH)   — Show mentor video, user observes
  JOB 2 (ACTIVE)  — User performs, coach evaluates form
  JOB 3 (HOLD)    — If phase ends before reps complete, freeze video up to 10s

State machine: WATCH → PREPARE → ACTIVE → [HOLD if needed] → next phase
             ↑ (zoom phases skip to WATCH directly)

Each exercise subclasses BaseController and implements:
  - phases() → list of phase dicts
  - check_pose(user_lm, w, h, phase) → (is_error, message | None)
  - detect_rep(user_lm, w, h) → increment rep_count
  - on_phase_change(phase) → optional: reset state machines
"""
import time
from abc import ABC, abstractmethod

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

VISIBILITY_MIN = 0.55  # MediaPipe visibility threshold
ERROR_THRESHOLD = 12  # frames of sustained error to trigger pause
PREPARE_LEAD_SEC = 3.0  # seconds before ACTIVE to show PREPARE
HOLD_MAX_SEC = 10.0  # hard cap on HOLD state duration


class CoachState:
    """State constants for the coach state machine."""
    WATCH = "WATCH"
    PREPARE = "PREPARE"
    ACTIVE = "ACTIVE"
    ZOOM = "ZOOM"
    HOLD = "HOLD"


class BaseController(ABC):
    """
    Abstract base class for all exercises.
    Implements state machine and shared coaching logic.
    """

    def __init__(self):
        """Initialize controller state."""
        self.rep_count = 0
        self.error_frames = 0
        self.good_frames = 0
        self._coach_state = CoachState.WATCH
        self._active_phase = None
        self._video_pos = 0.0
        self._end_hold_start = None  # timestamp when HOLD phase began

    def reset_session(self):
        """Reset counters when exercise switches."""
        self.rep_count = 0
        self.error_frames = 0
        self.good_frames = 0
        self._end_hold_start = None

    def update(self, video_pos: float, user_lm, w: int, h: int) -> tuple:
        """
        Main evaluation loop.
        Called every frame with user landmarks.

        Args:
            video_pos: current video time in seconds
            user_lm: MediaPipe landmarks or None
            w, h: frame dimensions

        Returns:
            (correct: bool, message: str, should_pause: bool)
            - correct: True = green skeleton, False = red skeleton
            - message: plain English coaching feedback
            - should_pause: True = freeze video this frame
        """
        self._video_pos = video_pos
        phase = self._get_phase(video_pos)

        if phase is None:
            return True, "Follow the mentor...", False

        # ─── PHASE CHANGE DETECTION ──────────────────────────────────────
        if phase.get("id") != (self._active_phase or {}).get("id"):
            self._on_phase_change(phase)
            self._active_phase = phase

        # ─── COMPUTE STATE ───────────────────────────────────────────────
        state = self._compute_state(video_pos, phase)
        self._coach_state = state

        # ─── HANDLE EACH STATE ───────────────────────────────────────────

        # ZOOM state: skip evaluation, just watch
        if state == CoachState.ZOOM:
            return True, "Watch closely — observe every detail", False

        # WATCH state: mentor video, no evaluation
        if state == CoachState.WATCH:
            msg = phase.get("watch_msg", "Watch the mentor")
            return True, f"👁  {msg}", False

        # PREPARE state: countdown to active
        if state == CoachState.PREPARE:
            secs = max(0, phase["active"] - video_pos)
            return True, f"Get ready — {phase.get('name', '')} starts in {secs:.0f}s", False

        # HOLD state: user hasn't completed reps, hold position
        if state == CoachState.HOLD:
            if self._end_hold_start is None:
                self._end_hold_start = time.time()

            elapsed = time.time() - self._end_hold_start
            remaining = max(0, HOLD_MAX_SEC - elapsed)
            done = self.rep_count
            target = phase.get("target", 0)
            rem = max(0, target - done)

            msg = (
                f"Complete {rem} more rep(s) ({done}/{target}) — "
                f"resuming in {remaining:.0f}s"
            )
            return True, msg, True  # pause video during HOLD

        # ─── ACTIVE STATE: EVALUATE USER FORM ────────────────────────────
        if user_lm is None:
            return False, "Step into the camera view", True

        # Call exercise's check_pose() method
        is_error, message = self.check_pose(user_lm, w, h, phase)

        # Update rep counter
        self.detect_rep(user_lm, w, h)

        # ─── ERROR STREAK LOGIC ──────────────────────────────────────────
        if is_error:
            self.error_frames += 1
            self.good_frames = 0

            if self.error_frames >= ERROR_THRESHOLD:
                # 12+ consecutive error frames = hard pause
                return False, message, True

            # Soft warning: show message but don't pause yet
            return True, message, False

        # ─── GOOD FORM ───────────────────────────────────────────────────
        else:
            self.error_frames = 0
            self.good_frames += 1

            if message:
                # Guidance message (not an error, but informative)
                return True, message, False

            # Pure positive feedback
            done = self.rep_count
            target = phase.get("target", 0)

            if target > 0:
                if done >= target:
                    return True, f"✅ All {target} done — great work!", False
                return True, f"Good form  {done} / {target}", False

            return True, "Good form — keep going", False

    def _compute_state(self, video_pos: float, phase: dict) -> str:
        """
        Strict state machine implementation.
        
        Exact logic flow:
        1. ZOOM phase (watch only, no evaluation)
        2. Phase ended? Check HOLD condition
        3. Active phase? Return ACTIVE
        4. Prepare phase (3s before active)? Return PREPARE
        5. Default: WATCH
        
        Final states: WATCH, PREPARE, ACTIVE, ZOOM, HOLD
        
        HOLD State:
        - Triggered when phase ends AND reps < target
        - Freezes video for max 10 seconds
        - Shows countdown timer
        - Auto-transitions to WATCH when time expires or phase changes
        """
        
        # STATE 1: ZOOM phase (observe only, no evaluation)
        if phase.get("zoom"):
            # Reset HOLD on zoom phase
            if self._end_hold_start is not None:
                self._end_hold_start = None
            return CoachState.ZOOM
        
        # Extract timing boundaries
        active_time = phase.get("active", phase["start"])
        end_time = phase.get("end", float("inf"))
        
        # STATE 5: Check HOLD condition first (highest priority after ZOOM)
        # HOLD is triggered when phase ends AND reps incomplete
        if video_pos >= end_time:
            rep_count = self.rep_count
            target = phase.get("target", 0)
            
            # HOLD logic: only if target exists AND reps incomplete
            if target > 0 and rep_count < target:
                # First time entering HOLD?
                if self._end_hold_start is None:
                    self._end_hold_start = time.time()
                
                # Check HOLD time limit (MUST NOT exceed 10s)
                elapsed = time.time() - self._end_hold_start
                if elapsed < HOLD_MAX_SEC:
                    # HOLD state (max 10 seconds)
                    return CoachState.HOLD
                else:
                    # HOLD time expired - move to WATCH
                    self._end_hold_start = None
                    return CoachState.WATCH
            
            # Reps complete or no target - go to WATCH
            self._end_hold_start = None
            return CoachState.WATCH
        
        # STATE 3: ACTIVE phase (video reached active time)
        if video_pos >= active_time:
            # Reset HOLD timer when in ACTIVE
            if self._end_hold_start is not None:
                self._end_hold_start = None
            return CoachState.ACTIVE
        
        # STATE 2: PREPARE phase (3 seconds before active)
        if video_pos >= active_time - PREPARE_LEAD_SEC:
            # Reset HOLD timer when in PREPARE
            if self._end_hold_start is not None:
                self._end_hold_start = None
            return CoachState.PREPARE
        
        # STATE 4: WATCH (default, preamble phase)
        self._end_hold_start = None
        return CoachState.WATCH

    def _get_phase(self, pos: float):
        """Get the phase active at video position."""
        current = None
        for p in self.phases():
            if pos >= p["start"]:
                current = p
        return current

    def _on_phase_change(self, phase: dict):
        """Called when transitioning to a new phase."""
        self.rep_count = 0
        self.error_frames = 0
        self.good_frames = 0
        self._end_hold_start = None
        # Allow subclass to reset state machines
        self.on_phase_change(phase)

    # ─────────────────────────────────────────────────────────────────────
    # ABSTRACT METHODS (implemented by exercise subclasses)
    # ─────────────────────────────────────────────────────────────────────

    @abstractmethod
    def phases(self) -> list:
        """
        Return list of phase dicts. Each phase must have:
          id (str), name (str), start (float), active (float), end (float),
          target (int), watch_msg (str), check_landmarks (list)
        Optional: zoom (bool), side (str)
        """
        ...

    @abstractmethod
    def check_pose(self, user_lm, w: int, h: int, phase: dict) -> tuple:
        """
        Evaluate user's form in current phase.

        Args:
            user_lm: MediaPipe landmarks
            w, h: frame dimensions
            phase: current phase dict

        Returns:
            (is_error: bool, message: str | None)
            - is_error=False: guidance/soft warning (no pause)
            - is_error=True: hard error (triggers pause after 12 frames)
            - message: None if all is good, str if guidance/error needed
        """
        ...

    def detect_rep(self, user_lm, w: int, h: int):
        """
        Optional: detect and count completed reps.
        Default does nothing. Override in subclass to count reps.
        """
        pass

    def on_phase_change(self, phase: dict):
        """
        Optional: called when phase changes.
        Use to reset state machines specific to your exercise.
        """
        pass

    # ─────────────────────────────────────────────────────────────────────
    # PROPERTIES FOR SUBCLASSES
    # ─────────────────────────────────────────────────────────────────────

    @property
    def current_phase_name(self) -> str:
        """Get name of current phase for UI display."""
        p = self._get_phase(self._video_pos)
        return p["name"] if p else "Exercise"

    @property
    def coach_state(self) -> str:
        """Get current coach state for UI display."""
        return self._coach_state