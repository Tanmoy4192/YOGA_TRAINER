"""
core/pose_engine.py — MediaPipe Pose detection

Detects 33 body landmarks and draws skeleton.
Skeleton color indicates form correctness (green=correct, red=error).
"""
import cv2
import numpy as np
from mediapipe.tasks.python import vision
from mediapipe.tasks import python

# Body structure: spine, limbs, fingers, feet
BODY_CONNECTIONS = [
    (11, 12),  # shoulders
    (11, 13), (13, 15),  # left arm
    (12, 14), (14, 16),  # right arm
    (11, 23), (12, 24),  # shoulders to hips
    (23, 24),  # hip line
    (23, 25), (25, 27),  # left leg
    (24, 26), (26, 28),  # right leg
    (27, 29), (27, 31),  # left foot
    (28, 30), (28, 32),  # right foot
]

FINGER_CONNECTIONS = [
    (15, 17), (15, 19), (15, 21),  # left hand: wrist to fingers
    (16, 18), (16, 20), (16, 22),  # right hand: wrist to fingers
]

BODY_LANDMARKS = [11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]
FINGER_LANDMARKS = [17, 18, 19, 20, 21, 22]
FEET_LANDMARKS = [29, 30, 31, 32]


class PoseEngine:
    """
    MediaPipe pose detection engine.
    Runs in async mode for real-time performance.
    """

    def __init__(self, model_path: str):
        """
        Initialize pose detector.

        Args:
            model_path: path to pose_landmarker_heavy.task
        """
        base = python.BaseOptions(model_asset_path=model_path)
        opts = vision.PoseLandmarkerOptions(
            base_options=base,
            running_mode=vision.RunningMode.LIVE_STREAM,
            num_poses=1,
            result_callback=self._cb,
        )
        self.landmarker = vision.PoseLandmarker.create_from_options(opts)
        self.latest_result = None

    def _cb(self, result, image, timestamp):
        """Callback when detection completes."""
        self.latest_result = result

    def detect_async(self, mp_image, timestamp_ms: int):
        """
        Queue frame for async detection.

        Args:
            mp_image: MediaPipe Image
            timestamp_ms: timestamp in milliseconds
        """
        self.landmarker.detect_async(mp_image, timestamp_ms)

    def get_landmarks(self):
        """
        Get detected landmarks from latest frame.
        Returns None if no pose detected.
        """
        if self.latest_result and self.latest_result.pose_landmarks:
            return self.latest_result.pose_landmarks[0]
        return None

    # ─────────────────────────────────────────────────────────────────────
    # SKELETON DRAWING
    # ─────────────────────────────────────────────────────────────────────

    def draw_skeleton(self, frame, correct: bool = True):
        """
        Draw skeleton on frame.

        Args:
            frame: OpenCV frame (BGR)
            correct: True = green skeleton (good form), False = red (error)

        Returns:
            frame with skeleton drawn
        """
        if not self.latest_result or not self.latest_result.pose_landmarks:
            return frame

        h, w, _ = frame.shape
        lms = self.latest_result.pose_landmarks[0]

        # Color scheme
        body_col = (200, 255, 200) if correct else (60, 60, 255)
        finger_col = (0, 255, 180) if correct else (0, 120, 255)
        feet_col = (255, 220, 0) if correct else (0, 80, 255)

        def px(idx):
            """Convert landmark to pixel coords."""
            if idx < len(lms):
                return (int(lms[idx].x * w), int(lms[idx].y * h))
            return None

        # Draw body v-bones
        for s, e in BODY_CONNECTIONS:
            p1, p2 = px(s), px(e)
            if p1 and p2:
                col = feet_col if s >= 27 else body_col
                self._v_bone(frame, p1, p2, col)

        # Draw finger lines
        for s, e in FINGER_CONNECTIONS:
            p1, p2 = px(s), px(e)
            if p1 and p2:
                cv2.line(frame, p1, p2, finger_col, 2, cv2.LINE_AA)
                cv2.circle(frame, p2, 4, finger_col, -1, cv2.LINE_AA)

        # Draw spine (smooth curve through shoulders and hips)
        pts = [px(i) for i in [11, 12, 23, 24] if px(i)]
        if len(pts) == 4:
            ls, rs, lh, rh = pts
            sm = ((ls[0] + rs[0]) // 2, (ls[1] + rs[1]) // 2)
            hm = ((lh[0] + rh[0]) // 2, (lh[1] + rh[1]) // 2)
            spine = [
                sm,
                ((sm[0] * 3 + hm[0]) // 4, (sm[1] * 3 + hm[1]) // 4),
                ((sm[0] + hm[0]) // 2, (sm[1] + hm[1]) // 2),
                ((sm[0] + hm[0] * 3) // 4, (sm[1] + hm[1] * 3) // 4),
                hm,
            ]
            for i in range(len(spine) - 1):
                self._v_bone(frame, spine[i], spine[i + 1], body_col, spread=4)
            for p in spine:
                cv2.circle(frame, p, 6, body_col, -1, cv2.LINE_AA)

        # Draw joint circles
        for idx in BODY_LANDMARKS:
            p = px(idx)
            if p:
                cv2.circle(frame, p, 7, body_col, -1, cv2.LINE_AA)

        for idx in FEET_LANDMARKS:
            p = px(idx)
            if p:
                cv2.circle(frame, p, 5, feet_col, -1, cv2.LINE_AA)

        return frame

    def _v_bone(self, frame, p1, p2, color, spread=5):
        """
        Draw a "V-bone" (tapered line) between two points.
        Creates 3D skeletal effect.
        """
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        ln = np.hypot(dx, dy)

        if ln == 0:
            return

        # Normal vector (perpendicular)
        nx, ny = -dy / ln, dx / ln

        # Two offset points at start
        a = (int(p1[0] + nx * spread), int(p1[1] + ny * spread))
        b = (int(p1[0] - nx * spread), int(p1[1] - ny * spread))

        # Draw tapered lines to end point
        cv2.line(frame, a, p2, color, 2, cv2.LINE_AA)
        cv2.line(frame, b, p2, color, 2, cv2.LINE_AA)