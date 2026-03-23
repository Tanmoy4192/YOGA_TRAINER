"""
core/motion_tracker.py — Temporal motion analysis

Tracks cyclic motion (rotations, swings) by monitoring:
  1. Position over time (kept in circular buffer)
  2. Y-axis oscillation (for rotation detection)
  3. Arc distance (for motion speed)

Used by exercises to count reps and detect movement.

KEY FIX: Uses full history window for stable midpoint calculation,
not just recent frames. This prevents baseline drift.
"""
import time
import math
from collections import deque


class MotionTracker:
    """
    Track cyclic motion of a point over time.
    Detects when user crosses a midline (cycle completed).
    """

    def __init__(self, window_sec: float = 1.5, min_arc_px: float = 12.0):
        """
        Initialize tracker.

        Args:
            window_sec: time window to keep (seconds)
            min_arc_px: minimum arc distance to consider "moving" (pixels)
        """
        self._window = window_sec
        self._min_arc = min_arc_px
        self._history = deque()  # (time, x, y) tuples
        self._y_vals = deque()  # separate y-value tracking
        self._cycles = 0
        self._y_phase = None

    def update(self, x: float, y: float):
        """
        Update tracker with new position.
        Call every frame.

        Args:
            x, y: landmark position in pixels
        """
        now = time.time()
        self._history.append((now, x, y))
        self._y_vals.append(y)

        # Trim old data outside window
        cutoff = now - self._window
        removed = 0
        while self._history and self._history[0][0] < cutoff:
            self._history.popleft()
            removed += 1

        # Trim y_vals to match
        for _ in range(removed):
            if self._y_vals:
                self._y_vals.popleft()

        # Update cycle detection
        self._update_cycles()

    def _update_cycles(self):
        """
        Detect cycles by tracking Y-axis oscillation.
        A cycle = moving down then back up (or vice versa) past midline.

        KEY FIX: Use full history window (e.g., 3 sec) for stable
        midpoint calculation, not just recent frames. This prevents
        the baseline from chasing the actual motion.
        """
        if len(self._history) < 6:
            return

        all_y = list(self._y_vals)
        if len(all_y) < 6:
            return

        # Stable midpoint using percentiles
        # (resistant to outliers)
        sorted_y = sorted(all_y)
        low_y = sorted_y[len(sorted_y) // 4]  # 25th percentile
        high_y = sorted_y[3 * len(sorted_y) // 4]  # 75th percentile
        mid_y = (low_y + high_y) / 2

        # Current smoothed y (last 6 frames)
        recent = list(self._history)[-6:]
        avg_y = sum(p[2] for p in recent) / 6

        # Margin for hysteresis
        margin = max(5.0, (high_y - low_y) * 0.2)

        # State machine for cycle detection
        if avg_y < mid_y - margin:
            if self._y_phase == "DOWN":
                self._cycles += 1
            self._y_phase = "UP"
        elif avg_y > mid_y + margin:
            self._y_phase = "DOWN"

    def is_moving(self) -> bool:
        """
        Check if point is currently moving.
        Returns True if arc distance >= min_arc_px in the window.
        """
        if len(self._history) < 3:
            return False

        pts = list(self._history)
        arc = sum(
            math.hypot(
                pts[i][1] - pts[i - 1][1], pts[i][2] - pts[i - 1][2]
            )
            for i in range(1, len(pts))
        )

        return arc >= self._min_arc

    def cycle_count(self) -> int:
        """Get total number of cycles detected."""
        return self._cycles

    def reset(self):
        """Clear motion history and cycle counter."""
        self._history.clear()
        self._y_vals.clear()
        self._cycles = 0
        self._y_phase = None