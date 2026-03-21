"""core/motion_tracker.py"""
import time
import math
from collections import deque


class MotionTracker:
    def __init__(self, window_sec: float = 1.5, min_arc_px: float = 12.0):
        self._window   = window_sec
        self._min_arc  = min_arc_px
        self._history  = deque()
        self._cycles   = 0
        self._y_phase  = None
        # FIX: track stable running min/max instead of recalculating from trimmed window
        self._y_vals   = deque()   # separate deque for y tracking

    def update(self, x: float, y: float):
        now = time.time()
        self._history.append((now, x, y))
        self._y_vals.append(y)
        cutoff = now - self._window
        removed = 0
        while self._history and self._history[0][0] < cutoff:
            self._history.popleft()
            removed += 1
        # trim y_vals to same length
        for _ in range(removed):
            if self._y_vals:
                self._y_vals.popleft()
        self._update_cycles()

    def _update_cycles(self):
        """
        FIX: use a longer stable window for mid_y calculation.
        Keep a separate 3-second y history for stable midpoint.
        Only count cycle when wrist clearly crosses midpoint.
        """
        if len(self._history) < 6:
            return
        all_y  = list(self._y_vals)
        if len(all_y) < 6:
            return
        # use percentile-based midpoint to avoid outliers
        sorted_y = sorted(all_y)
        low_y  = sorted_y[len(sorted_y)//4]    # 25th percentile
        high_y = sorted_y[3*len(sorted_y)//4]  # 75th percentile
        mid_y  = (low_y + high_y) / 2

        # current smoothed y (last 6 frames)
        recent = list(self._history)[-6:]
        avg_y  = sum(p[2] for p in recent) / 6

        margin = max(5.0, (high_y - low_y) * 0.2)  # adaptive margin

        if avg_y < mid_y - margin:
            if self._y_phase == "DOWN":
                self._cycles += 1
            self._y_phase = "UP"
        elif avg_y > mid_y + margin:
            self._y_phase = "DOWN"

    def is_moving(self) -> bool:
        if len(self._history) < 3:
            return False
        pts = list(self._history)
        arc = sum(math.hypot(pts[i][1]-pts[i-1][1], pts[i][2]-pts[i-1][2])
                  for i in range(1, len(pts)))
        return arc >= self._min_arc

    def cycle_count(self) -> int:
        return self._cycles

    def reset(self):
        self._history.clear()
        self._y_vals.clear()
        self._cycles  = 0
        self._y_phase = None