"""
core/reference_analyzer.py
─────────────────────────────────────────────────────────────
BUG 4 FIX — accepts an explicit base_ts argument so the caller
(main.py) can supply a monotonic counter that is guaranteed to
never collide with the user-engine timestamps.
"""

import cv2
import mediapipe as mp


class ReferenceAnalyzer:
    def __init__(self, pose_engine):
        self._engine = pose_engine
        self.landmarks = None
        self._counter  = 0          # fallback internal counter

    def extract(self, frame, base_ts: int = 0):
        """
        Detect pose in `frame`.

        base_ts — caller-supplied timestamp (use a large offset so it
                  never overlaps the user-engine counter in main.py).
                  If 0, falls back to an internal counter.
        """
        self._counter += 1
        ts = base_ts if base_ts > 0 else self._counter

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        self._engine.detect_async(img, ts)

        if (self._engine.latest_result
                and self._engine.latest_result.pose_landmarks):
            self.landmarks = self._engine.latest_result.pose_landmarks[0]
        return self.landmarks