"""
core/breath_detector.py — Breath cycle detection

Detects breathing by tracking shoulder y-position.
Used for timed holds (e.g., "hold for 4 breaths").

KEY FIXES:
  1. Baseline uses FULL 10-second history (not 2 sec)
     Old problem: 2 sec < breath cycle duration (4-6 sec)
     → baseline tracked the signal itself → no detection
     Fix: full window = stable long-term average

  2. Thresholds tuned for real shoulder movement (~1-2% of frame height)

  3. Fallback timer: if no movement detected in 5 seconds,
     count 1 breath anyway → phase always progresses
"""
import time
from collections import deque

MIN_BREATH_SEC = 3.5  # minimum gap between counted breaths
FALLBACK_SEC = 5.0  # count 1 breath every N sec if no movement detected
SMOOTH_FRAMES = 20  # smooth recent values to reduce noise
BASELINE_FRAMES = 300  # ~10 sec at 30fps — must be >> 1 breath cycle
INHALE_THRESH = 0.006  # shoulders rise 0.6% of frame = inhale
EXHALE_THRESH = 0.004  # shoulders fall 0.4% below baseline = exhale


class BreathDetector:
    """
    Detect breathing cycles from shoulder position over time.
    """

    def __init__(self, min_breath_sec: float = MIN_BREATH_SEC):
        """
        Initialize detector.

        Args:
            min_breath_sec: minimum time between counted breaths (seconds)
        """
        self._min_breath = min_breath_sec
        self._history = deque(maxlen=BASELINE_FRAMES)
        self._phase = "NEUTRAL"
        self._last_breath = None
        self._count = 0
        self._reported = 0
        self._start_time = None

    def update(self, shoulder_y_norm: float):
        """
        Update detector with shoulder y-position.
        Call every frame.

        Args:
            shoulder_y_norm: (lm[11].y + lm[12].y) / 2
                           (normalized coords 0-1, lower = higher on screen)
        """
        now = time.time()
        if self._start_time is None:
            self._start_time = now

        self._history.append((now, shoulder_y_norm))

        n = len(self._history)
        if n < SMOOTH_FRAMES + 10:
            return  # not enough data yet

        # ─── SMOOTHED CURRENT VALUE ─────────────────────────────────────
        recent = list(self._history)[-SMOOTH_FRAMES:]
        smooth = sum(p[1] for p in recent) / SMOOTH_FRAMES

        # ─── STABLE BASELINE (FULL WINDOW) ──────────────────────────────
        # KEY FIX: use FULL history, not trimmed window
        # This prevents baseline from chasing the signal
        baseline = sum(p[1] for p in self._history) / n

        # positive diff = shoulders above baseline = inhale
        diff = baseline - smooth

        # ─── STATE MACHINE ───────────────────────────────────────────────
        if diff > INHALE_THRESH and self._phase != "INHALE":
            self._phase = "INHALE"
        elif diff < -EXHALE_THRESH and self._phase == "INHALE":
            self._try_count(now)
            self._phase = "EXHALE"
        elif abs(diff) < INHALE_THRESH * 0.3:
            self._phase = "NEUTRAL"

        # ─── FALLBACK TIMER ─────────────────────────────────────────────
        # If no movement detected, count 1 breath anyway
        # (prevents phase from getting stuck)
        ref = self._last_breath or self._start_time
        if now - ref >= FALLBACK_SEC:
            self._try_count(now)

    def _try_count(self, now: float):
        """Count breath only if enough time has passed since last."""
        ref = self._last_breath
        if ref is None or (now - ref) >= self._min_breath:
            self._count += 1
            self._last_breath = now

    def new_breaths(self) -> int:
        """
        Get number of new breaths since last call.
        Call this to "consume" the count.

        Returns:
            number of breaths detected since last call
        """
        new = self._count - self._reported
        self._reported = self._count
        return max(0, new)

    @property
    def total(self) -> int:
        """Total breaths detected so far."""
        return self._count

    @property
    def phase(self) -> str:
        """Current breath phase (INHALE, EXHALE, NEUTRAL)."""
        return self._phase

    def reset(self):
        """Reset detector for new phase."""
        self._history.clear()
        self._phase = "NEUTRAL"
        self._last_breath = None
        self._count = 0
        self._reported = 0
        self._start_time = None