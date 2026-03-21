"""core/video_controller.py — supports URL and local file"""
import cv2


class ReferenceVideo:
    def __init__(self, source: str):
        self.cap        = cv2.VideoCapture(source)
        self._paused    = False
        self._last      = None
        self.fps        = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open: {source}")

    def read(self):
        if self._paused and self._last is not None:
            return self._last.copy()
        ret, frame = self.cap.read()
        if not ret:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            _, frame = self.cap.read()
        self._last = frame
        return frame

    def pause(self):  self._paused = True
    def resume(self): self._paused = False

    def position_seconds(self) -> float:
        return self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0

    def seek(self, seconds: float):
        self.cap.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)

    def release(self):
        self.cap.release()