"""core/base_controller.py"""
from abc import ABC, abstractmethod

VISIBILITY_MIN   = 0.5
ERROR_THRESHOLD  = 10
PREPARE_LEAD_SEC = 3.0


class CoachState:
    WATCH   = "WATCH"
    PREPARE = "PREPARE"
    ACTIVE  = "ACTIVE"
    ZOOM    = "ZOOM"


class BaseController(ABC):

    def __init__(self):
        self.rep_count     = 0
        self.error_frames  = 0
        self.good_frames   = 0
        self._coach_state  = CoachState.WATCH
        self._active_phase = None
        self._video_pos    = 0.0

    def update(self, video_pos: float, user_lm, ref_lm, width, height):
        """Returns (correct: bool, message: str)"""
        self._video_pos = video_pos
        phase = self._get_phase(video_pos)

        if phase is None:
            return True, "Follow the mentor..."

        if phase.get("id") != (self._active_phase or {}).get("id"):
            self._on_phase_change(phase)
        self._active_phase = phase

        state = self._get_coach_state(video_pos, phase)
        self._coach_state = state

        if state == CoachState.ZOOM:
            return True, "Watch closely..."

        if state == CoachState.WATCH:
            return True, f"Watch the mentor — {phase.get('watch_msg', '')}"

        if state == CoachState.PREPARE:
            secs = max(0, phase["active"] - video_pos)
            return True, f"Get ready — {phase.get('name','')} in {secs:.0f}s"

        # ── ACTIVE ────────────────────────────────────────────────
        if user_lm is None:
            return False, "Step into camera view"

        if ref_lm is not None and not self._ref_visible(ref_lm, phase):
            # FIX: call check_pose first (updates trackers), then detect_rep
            self.check_pose(user_lm, ref_lm, width, height, phase)
            self.detect_rep(user_lm, width, height)
            return True, "Follow along..."

        # FIX: check_pose first (updates trackers/breath), then detect_rep
        is_error, message = self.check_pose(user_lm, ref_lm, width, height, phase)
        self.detect_rep(user_lm, width, height)

        done   = self.rep_count
        target = phase.get("target", 0)

        if is_error and message:
            self.error_frames += 1
            self.good_frames   = 0
            if self.error_frames >= ERROR_THRESHOLD:
                return False, message
            return True, message
        else:
            self.error_frames = 0
            self.good_frames += 1
            if message:
                return True, message
            if target > 0:
                if done >= target:
                    return True, f"Excellent! All {target} done"
                return True, f"Good form  {done}/{target}"
            return True, "Good form"

    def _get_phase(self, pos: float):
        current = None
        for p in self.phases():
            if pos >= p["start"]:
                current = p
        return current

    def _get_coach_state(self, pos: float, phase: dict) -> str:
        if phase.get("zoom"):
            return CoachState.ZOOM
        active = phase.get("active", phase["start"])
        end    = phase.get("end", float("inf"))
        if pos >= end:
            return CoachState.WATCH
        if pos >= active:
            return CoachState.ACTIVE
        if pos >= active - PREPARE_LEAD_SEC:
            return CoachState.PREPARE
        return CoachState.WATCH

    def _on_phase_change(self, phase: dict):
        self.rep_count    = 0
        self.error_frames = 0
        self.good_frames  = 0
        self.on_phase_change(phase)

    def _ref_visible(self, ref_lm, phase: dict) -> bool:
        idxs = phase.get("check_landmarks", [11,12,13,14,15,16])
        for i in idxs:
            if i < len(ref_lm) and ref_lm[i].visibility < VISIBILITY_MIN:
                return False
        return True

    @abstractmethod
    def phases(self) -> list: ...

    @abstractmethod
    def check_pose(self, user_lm, ref_lm, width, height, phase) -> tuple[bool, str | None]:
        """(is_error, message). is_error=True pauses video."""
        ...

    def detect_rep(self, user_lm, width, height): pass
    def on_phase_change(self, phase: dict): pass