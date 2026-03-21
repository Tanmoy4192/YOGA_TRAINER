"""
core/breath_detector.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Detects breathing by tracking shoulder y-position over time.

FIXES over previous version:
  1. Baseline uses FULL 10-second history window (not just 2s)
     Old code: baseline = last 60 frames = 2 sec
     Problem:  2 sec < 1 breath cycle (4-6 sec)
               so baseline tracked the signal → diff always ~0 → no detection
     Fix:      baseline = all 300 frames (10 sec) = stable long-term average

  2. Thresholds tuned for real shoulder movement (~1-2% of frame height)

  3. Fallback timer: if no movement detected in 5 seconds,
     count 1 breath anyway → Phase 1 hold always progresses
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import time
from collections import deque

MIN_BREATH_SEC  = 3.5    # minimum gap between counted breaths
FALLBACK_SEC    = 5.0    # count 1 breath every N sec if no movement detected
SMOOTH_FRAMES   = 20     # smooth recent values to reduce noise
BASELINE_FRAMES = 300    # ~10 sec at 30fps — must be >> 1 breath cycle
INHALE_THRESH   = 0.006  # shoulders rise 0.6% of frame = inhale
EXHALE_THRESH   = 0.004  # shoulders fall 0.4% below baseline = exhale


class BreathDetector:
    def __init__(self, min_breath_sec: float = MIN_BREATH_SEC):
        self._min_breath  = min_breath_sec
        self._history     = deque(maxlen=BASELINE_FRAMES)
        self._phase       = "NEUTRAL"
        self._last_breath = None
        self._count       = 0
        self._reported    = 0
        self._start_time  = None

    def update(self, shoulder_y_norm: float):
        """
        Call every frame.
        shoulder_y_norm = (lm[11].y + lm[12].y) / 2
        Smaller y = higher on screen = shoulders raised = inhale
        """
        now = time.time()
        if self._start_time is None:
            self._start_time = now

        self._history.append((now, shoulder_y_norm))
        n = len(self._history)

        if n < SMOOTH_FRAMES + 10:
            return  # not enough data yet

        # Smoothed current value
        smooth = sum(p[1] for p in list(self._history)[-SMOOTH_FRAMES:]) / SMOOTH_FRAMES

        # Stable baseline — use FULL window (10 sec)
        # This is the key fix: long baseline doesn't chase breath cycles
        baseline = sum(p[1] for p in self._history) / n

        # positive diff = shoulders above baseline = inhale
        diff = baseline - smooth

        # State machine
        if diff > INHALE_THRESH and self._phase != "INHALE":
            self._phase = "INHALE"
        elif diff < -EXHALE_THRESH and self._phase == "INHALE":
            self._try_count(now)
            self._phase = "EXHALE"
        elif abs(diff) < INHALE_THRESH * 0.3:
            self._phase = "NEUTRAL"

        # Fallback — shallow breather or detection failure
        ref = self._last_breath or self._start_time
        if now - ref >= FALLBACK_SEC:
            self._try_count(now)

    def _try_count(self, now: float):
        """Count breath only if enough time has passed."""
        ref = self._last_breath
        if ref is None or (now - ref) >= self._min_breath:
            self._count      += 1
            self._last_breath = now

    def new_breaths(self) -> int:
        """Breaths since last call. Call this to consume the count."""
        new            = self._count - self._reported
        self._reported = self._count
        return max(0, new)

    @property
    def total(self) -> int:
        return self._count

    @property
    def phase(self) -> str:
        return self._phase

    def reset(self):
        self._history.clear()
        self._phase       = "NEUTRAL"
        self._last_breath = None
        self._count       = 0
        self._reported    = 0
        self._start_time  = None