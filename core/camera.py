"""core/camera.py"""
import cv2


class Camera:
    def __init__(self, index=0):
        self.cap = cv2.VideoCapture(index)
        if not self.cap.isOpened():
            raise RuntimeError("Camera not opened")

    def read(self):
        ret, frame = self.cap.read()
        if not ret:
            raise RuntimeError("Frame capture failed")
        return frame

    def release(self):
        self.cap.release()