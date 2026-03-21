"""
core/hold_timer.py

Tracks how long a pose has been held continuously.
If the user breaks the pose, the hold timer resets.
Used for breath-based holds and timed poses.
"""

import time


class HoldTimer:
    def __init__(self):
        self._holding      = False
        self._hold_start   = None
        self._total_held   = 0.0
        self._best_hold    = 0.0

    def update(self, is_correct: bool):
        """Call every frame with whether pose is correct."""
        now = time.time()
        if is_correct:
            if not self._holding:
                self._holding    = True
                self._hold_start = now
            else:
                elapsed = now - self._hold_start
                self._best_hold = max(self._best_hold, elapsed)
        else:
            if self._holding:
                self._holding  = False
                self._hold_start = None

    def held_seconds(self) -> float:
        """How long currently held (0 if not holding)."""
        if self._holding and self._hold_start:
            return time.time() - self._hold_start
        return 0.0

    def is_holding(self) -> bool:
        return self._holding

    def reset(self):
        self._holding    = False
        self._hold_start = None
        self._total_held = 0.0
        self._best_hold  = 0.0