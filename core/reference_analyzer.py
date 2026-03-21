"""core/reference_analyzer.py"""
import cv2
import mediapipe as mp
import time


class ReferenceAnalyzer:
    def __init__(self, pose_engine):
        self._engine = pose_engine
        self.landmarks = None

    def extract(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        self._engine.detect_async(img, int(time.time() * 1000))
        if (self._engine.latest_result
                and self._engine.latest_result.pose_landmarks):
            self.landmarks = self._engine.latest_result.pose_landmarks[0]
        return self.landmarks