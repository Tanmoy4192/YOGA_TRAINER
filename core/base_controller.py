"""
core/base_controller.py — BaseController abstract class

THREE JOBS of the AI coach:
  JOB 1 (WATCH)   — Show mentor video, user observes ("Watch Carefully")
  JOB 2 (ACTIVE)  — User performs, coach evaluates form
  JOB 3 (HOLD)    — Phase ended before 10s window, video frozen
                     After 10s ALWAYS moves on regardless of rep count.

State machine: WATCH → PREPARE → ACTIVE → HOLD (if needed) → next phase

FIXES:
  - HOLD timer now fires ONCE per phase-end, does not repeat
  - After HOLD_MAX_SEC elapses, state transitions to WATCH permanently
  - _end_hold_start is cleared correctly on every phase change
  - hold_remaining exposed to renderer for countdown display
"""
import time
from abc import ABC, abstractmethod
from core.utils import visible

VISIBILITY_MIN   = 0.55
ERROR_THRESHOLD  = 12
PREPARE_LEAD_SEC = 3.0
HOLD_MAX_SEC     = 10.0   # wait 10s then move on no matter what


class CoachState:
    WATCH   = "WATCH"
    PREPARE = "PREPARE"
    ACTIVE  = "ACTIVE"
    ZOOM    = "ZOOM"
    HOLD    = "HOLD"


class BaseController(ABC):

    def __init__(self):
        self.rep_count        = 0
        self.error_frames     = 0
        self.good_frames      = 0
        self._coach_state     = CoachState.WATCH
        self._active_phase    = None
        self._video_pos       = 0.0
        self._end_hold_start  = None   # wall-clock when HOLD started
        self._hold_remaining  = 0.0
        # Track which phase ids have already had their HOLD consumed
        self._hold_done_phases = set()

    def reset_session(self):
        self.rep_count         = 0
        self.error_frames      = 0
        self.good_frames       = 0
        self._end_hold_start   = None
        self._hold_remaining   = 0.0
        self._hold_done_phases = set()

    def update(self, video_pos: float, user_lm, w: int, h: int) -> tuple:
        """
        Main evaluation loop — called every frame.
        Returns: (correct, message, should_pause, hold_remaining)
        """
        self._video_pos = video_pos

        # _get_phase returns None in gaps between phases (pos >= end).
        # Fall back to _active_phase so HOLD/rep-count keep working.
        phase_now = self._get_phase(video_pos)
        if phase_now is not None:
            if phase_now.get("id") != (self._active_phase or {}).get("id"):
                self._on_phase_change(phase_now)
                self._active_phase = phase_now

        phase = self._active_phase
        if phase is None:
            return True, "Follow the mentor...", False, 0.0

        # If we are in a true inter-phase gap (no current phase and
        # the last known phase has ended) return neutral WATCH so
        # no stale watch_msg / HOLD / corrections bleed through.
        in_gap = (phase_now is None) and (
            video_pos >= phase.get("end", float("inf"))
        )
        if in_gap:
            self._coach_state = CoachState.WATCH
            return True, "", False, 0.0

        state = self._compute_state(video_pos, phase)
        self._coach_state = state

        def _ret(correct, msg, pause):
            return correct, msg, pause, self._hold_remaining

        # ── ZOOM ─────────────────────────────────────────────────────────
        if state == CoachState.ZOOM:
            return _ret(True, "Watch closely — observe every detail", False)

        # ── WATCH ─────────────────────────────────────────────────────────
        if state == CoachState.WATCH:
            msg = phase.get("watch_msg", "Watch the mentor")
            return _ret(True, msg, False)

        # ── PREPARE ──────────────────────────────────────────────────────
        if state == CoachState.PREPARE:
            secs = max(0, phase["active"] - video_pos)
            msg  = phase.get("watch_msg", "Get ready")
            return _ret(True, f"{msg} — starting in {secs:.0f}s", False)

        # ── HOLD ─────────────────────────────────────────────────────────
        if state == CoachState.HOLD:
            elapsed   = time.time() - self._end_hold_start
            remaining = max(0.0, HOLD_MAX_SEC - elapsed)
            self._hold_remaining = remaining

            done   = self.rep_count
            target = phase.get("target", 0)
            rem    = max(0, target - done)
            msg    = f"Complete {rem} more rep(s)  ({done}/{target})"
            return _ret(True, msg, True)

        # ── ACTIVE ────────────────────────────────────────────────────────
        self._hold_remaining = 0.0

        if user_lm is None:
            return _ret(False, "Step into the camera view", True)

        # Body visibility should require most key points, not every point.
        key_points = [11, 12, 13, 14, 15, 16, 23, 24, 25, 26]  # shoulders/arms/hips/knees/ankles
        visible_count = sum(1 for idx in key_points
                            if idx < len(user_lm) and user_lm[idx].visibility >= VISIBILITY_MIN)
        if visible_count < len(key_points) * 0.7:  # 70% visible required
            return _ret(False, "Body is not visible, stay in the frame", False)

        is_error, message = self.check_pose(user_lm, w, h, phase)
        self.detect_rep(user_lm, w, h)

        if is_error:
            self.error_frames += 1
            self.good_frames   = 0
            if self.error_frames >= ERROR_THRESHOLD:
                return _ret(False, message, True)
            return _ret(True, message, False)

        self.error_frames = 0
        self.good_frames += 1

        if message:
            return _ret(True, message, False)

        done   = self.rep_count
        target = phase.get("target", 0)

        if target > 0 and done < target:
            # User is active but rep not yet counted. Only show specific corrections.
            # Don't show generic "follow the mentor" — let specific form checks provide feedback.
            return _ret(False, "", False)

        if target > 0 and done >= target:
            if done == target:
                return _ret(True, f"Good job — you have done the goal repetition! ({done}/{target})", False)
            return _ret(True, f"Great work! {done}/{target} reps completed", False)

        # No fixed target; keep encouraging.
        return _ret(True, "Good form — keep going", False)

    def _compute_state(self, video_pos: float, phase: dict) -> str:
        """
        State machine:
          ZOOM > HOLD (once per phase, for 10s max) > ACTIVE > PREPARE > WATCH

        KEY FIX: HOLD only fires once per phase. After HOLD_MAX_SEC elapses
        the phase id is added to _hold_done_phases and state becomes WATCH.
        This prevents the 10-second timer from repeating.
        """
        if phase.get("zoom"):
            self._end_hold_start = None
            self._hold_remaining = 0.0
            return CoachState.ZOOM

        pid         = phase.get("id", "")
        active_time = phase.get("active", phase["start"])
        end_time    = phase.get("end", float("inf"))

        # ── Past end of phase ─────────────────────────────────────────────
        if video_pos >= end_time:
            # Has this phase's HOLD already been consumed?
            if pid in self._hold_done_phases:
                self._hold_remaining = 0.0
                return CoachState.WATCH

            target = phase.get("target", 0)
            if target > 0 and self.rep_count < target:
                # Start HOLD timer if not already started
                if self._end_hold_start is None:
                    self._end_hold_start = time.time()

                elapsed = time.time() - self._end_hold_start
                self._hold_remaining = max(0.0, HOLD_MAX_SEC - elapsed)

                if elapsed < HOLD_MAX_SEC:
                    return CoachState.HOLD

            # HOLD expired (or no reps needed) — mark done, never HOLD again
            self._hold_done_phases.add(pid)
            self._end_hold_start = None
            self._hold_remaining = 0.0
            return CoachState.WATCH

        # ── Reset hold state whenever we're back inside the phase ─────────
        if self._end_hold_start is not None and video_pos < end_time:
            self._end_hold_start = None
            self._hold_remaining = 0.0

        # ── ACTIVE ────────────────────────────────────────────────────────
        if video_pos >= active_time:
            self._hold_remaining = 0.0
            return CoachState.ACTIVE

        # ── PREPARE (3s lead-in) ──────────────────────────────────────────
        if video_pos >= active_time - PREPARE_LEAD_SEC:
            self._hold_remaining = 0.0
            return CoachState.PREPARE

        # ── WATCH ─────────────────────────────────────────────────────────
        self._hold_remaining = 0.0
        return CoachState.WATCH

    def _get_phase(self, pos: float):
        """
        Return the active phase for this video position.
        Returns None if pos is before the first phase OR in a gap between phases
        (i.e. pos >= last matched phase's 'end').
        """
        current = None
        for p in self.phases():
            if pos >= p["start"]:
                current = p
        # If we found a phase but have passed its end, we're in a gap — no phase
        if current is not None:
            end = current.get("end", float("inf"))
            if pos >= end:
                return None
        return current

    def _on_phase_change(self, phase: dict):
        """Called when phase changes. Resets counters but preserves hold_done set."""
        self.rep_count       = 0
        self.error_frames    = 0
        self.good_frames     = 0
        self._end_hold_start = None
        self._hold_remaining = 0.0
        # NOTE: we do NOT clear _hold_done_phases here — it persists for the
        # lifetime of the session so a phase's HOLD is never replayed.
        self.on_phase_change(phase)

    # ── Abstract interface ────────────────────────────────────────────────────

    @abstractmethod
    def phases(self) -> list: ...

    @abstractmethod
    def check_pose(self, user_lm, w: int, h: int, phase: dict) -> tuple: ...

    def detect_rep(self, user_lm, w: int, h: int): pass

    def on_phase_change(self, phase: dict): pass

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def current_phase_name(self) -> str:
        p = self._get_phase(self._video_pos)
        return p["name"] if p else "Exercise"

    @property
    def coach_state(self) -> str:
        return self._coach_state

    @property
    def hold_remaining(self) -> float:
        return self._hold_remaining