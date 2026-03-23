"""
core/camera.py — Camera input wrapper
"""
import cv2


class Camera:
    """Simple webcam capture."""

    def __init__(self, index: int = 0):
        """
        Initialize camera.

        Args:
            index: camera device index (0 = default)
        """
        self.cap = cv2.VideoCapture(index)
        if not self.cap.isOpened():
            raise RuntimeError("Camera not opened")

    def read(self):
        """
        Read next frame from camera.

        Returns:
            OpenCV frame (BGR)
        """
        ret, frame = self.cap.read()
        if not ret:
            raise RuntimeError("Frame capture failed")
        return frame

    def release(self):
        """Release camera resources."""
        self.cap.release()