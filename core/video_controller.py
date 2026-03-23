"""
core/video_controller.py — Video playback controller

PROBLEMS SOLVED:
  1. CAP_PROP_POS_MSEC is unreliable on URL streams (buffers ahead 5-30s)
     → Use wall-clock timing for URL sources
  2. Network stalls cause dropped frames
     → Auto-reconnect on read failure or dim frame
  3. Pause doesn't work on URL streams
     → Cache last good frame, return copy when paused
  4. First-run latency
     → Optional SKY_CACHE_DIR env var for local caching
"""
import os
import cv2
import time
import hashlib


# ─────────────────────────────────────────────────────────────────────────────
# FFMPEG ENVIRONMENT CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
# Set BEFORE any VideoCapture is created

os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    "protocol_whitelist;file,crypto,data,https,http,tcp,tls"
    "|timeout;10000000"
    "|reconnect;1"
    "|reconnect_streamed;1"
    "|reconnect_delay_max;5",
)

os.environ.setdefault("OPENCV_FFMPEG_READ_TIMEOUT", "30000")


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────


def _cache_path(url: str) -> str:
    """
    Generate local cache path for URL.
    Uses MD5 hash of URL as filename.
    """
    cache_dir = os.environ.get("SKY_CACHE_DIR")
    if not cache_dir:
        return None

    os.makedirs(cache_dir, exist_ok=True)
    url_hash = hashlib.md5(url.encode()).hexdigest()
    return os.path.join(cache_dir, f"{url_hash}.mp4")


def download_to_cache(url: str) -> str:
    """
    Pre-download video to local cache.
    Returns path to cached file, or None if cache not configured.

    Usage:
        path = download_to_cache(url)
        if path:
            ref_video = ReferenceVideo(path)  # uses fast local file
    """
    cache_path = _cache_path(url)
    if not cache_path:
        return None

    if os.path.exists(cache_path):
        print(f"✓ Using cached: {cache_path}")
        return cache_path

    print(f"⟳ Downloading to cache: {cache_path}")
    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        print(f"✗ Cannot open: {url}")
        return None

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    out = cv2.VideoWriter(cache_path, fourcc, fps, (w, h))
    frame_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        out.write(frame)
        frame_count += 1
        if frame_count % 30 == 0:
            print(f"  ... {frame_count} frames")

    cap.release()
    out.release()
    print(f"✓ Download complete: {frame_count} frames")
    return cache_path


# ─────────────────────────────────────────────────────────────────────────────
# MAIN CLASS
# ─────────────────────────────────────────────────────────────────────────────


class ReferenceVideo:
    """
    Smart video playback controller.
    Handles local files and URL streams with auto-reconnect and wall-clock tracking.
    """

    def __init__(self, source: str):
        """
        Initialize video playback.

        Args:
            source: local file path or URL
        """
        self.source = source
        self.cap = None
        self._is_url = source.startswith("http")
        self._paused = False
        self._last_frame = None
        self.fps = 30.0

        # Playback position tracking
        self._play_start_wall = None  # time.time() when playback started
        self._play_start_pos = 0.0  # video position at that time
        self._frozen_pos = 0.0  # snapshot position when paused
        self._current_pos = 0.0  # position advanced by read frames to avoid skips

        # Reconnect tracking
        self._last_reconnect = 0.0
        self._reconnect_cooldown = 5.0

        # Frame dimness detection
        self._dim_frame_count = 0
        self._dim_frame_threshold = 3  # reconnect after 3+ dim frames

        self._open()

    def _open(self):
        """Open or reconnect to video source."""
        if self.cap is not None:
            self.cap.release()

        self.cap = cv2.VideoCapture(self.source)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open: {self.source}")

        # Configure for reliable streaming
        # Keep buffer small to avoid skipping frames caused by prefetching
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0

        # Reset playback tracking
        self._play_start_wall = time.time()
        self._play_start_pos = self._frozen_pos
        self._current_pos = self._frozen_pos
        self._dim_frame_count = 0

    def _reconnect(self, seek_to: float = None):
        """
        Attempt to reconnect after network failure.

        Args:
            seek_to: position to seek to after reconnect (optional)
        """
        now = time.time()
        if now - self._last_reconnect < self._reconnect_cooldown:
            return False  # cooldown active

        print(f"⟳ Reconnecting to {self.source}")
        self._last_reconnect = now

        if seek_to is not None:
            self._frozen_pos = seek_to

        self._open()

        if seek_to is not None:
            self.cap.set(cv2.CAP_PROP_POS_MSEC, seek_to * 1000)
            self._play_start_pos = seek_to
            self._play_start_wall = time.time()

        return True

    def read(self):
        """
        Read next frame from video.
        Returns cached frame if paused.
        Auto-reconnects on failure.
        """
        # Return cached frame if paused
        if self._paused and self._last_frame is not None:
            return self._last_frame.copy()

        # Try to read frame
        ret, frame = self.cap.read()

        if not ret:
            # Read failed, try reconnect
            if self._reconnect(seek_to=self._frozen_pos):
                ret, frame = self.cap.read()

            if not ret:
                # Still failing, return last frame
                if self._last_frame is not None:
                    return self._last_frame.copy()
                raise RuntimeError("Cannot read video frame")

        # Check frame brightness (dim = network stall)
        brightness = cv2.mean(frame)[0]
        if brightness < 2.0:
            self._dim_frame_count += 1
            if self._dim_frame_count >= self._dim_frame_threshold:
                self._reconnect(seek_to=self._frozen_pos)
                self._dim_frame_count = 0
        else:
            self._dim_frame_count = 0

        # Cache this frame
        self._last_frame = frame.copy()

        # Update position by frame now, avoiding wall-clock skipping
        frame_duration = 1.0 / max(self.fps, 1.0)
        self._current_pos = self._current_pos + frame_duration
        self._frozen_pos = self._current_pos

        return frame

    def position_seconds(self) -> float:
        """
        Get current playback position in seconds.
        Uses wall-clock timing for URL streams (more reliable than CAP_PROP_POS_MSEC).
        """
        # Playback uses current tracked position from reads to avoid frame skipping,
        # while paused returns frozen position. External position queries always use this.
        if self._paused:
            return self._frozen_pos

        # For local + URL both, use current position updated per frame read.
        return self._current_pos

    def pause(self):
        """Pause playback."""
        self._paused = True
        self._frozen_pos = self.position_seconds()

    def resume(self):
        """Resume playback."""
        if self._paused:
            self._play_start_wall = time.time()
            self._play_start_pos = self._frozen_pos
        self._paused = False

    def seek(self, seconds: float):
        """
        Seek to specific position.

        Args:
            seconds: target position in seconds
        """
        self.cap.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
        self._frozen_pos = seconds
        self._play_start_pos = seconds
        self._play_start_wall = time.time()

    def release(self):
        """Release video resources."""
        if self.cap is not None:
            self.cap.release()
            self.cap = None