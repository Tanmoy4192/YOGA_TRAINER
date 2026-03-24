"""
server.py — SKY Yoga AI Coach REST API Server
Production-ready API with video streaming and exercise control.

Features:
  - REST API with pause/resume control
  - Live video streaming (50/50 split: user feed + reference feed)
  - MJPEG streaming for browser viewing
  - Frame-by-frame processing endpoint
  - Exercise tracking and feedback
  - Real-time rep counting and form analysis

Endpoints:
  GET  /video/stream   → MJPEG video stream
  POST /process        → Process individual frame (returns processed frame as JPEG)
  GET  /api/status     → Current exercise status
  POST /api/pause      → Pause video and exercise
  POST /api/resume     → Resume video and exercise
  POST /api/reset      → Reset current exercise
"""

import os
import cv2
import time
import threading
import mediapipe as mp
import json
import numpy as np
from io import BytesIO
from fastapi import FastAPI, Response, File, UploadFile
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from core.camera import Camera
from core.pose_engine import PoseEngine
from core.video_controller import ReferenceVideo
from core.exercise_registry import ExerciseRegistry
from core.ui_render import (
    render_frame,
    render_user_frame,
    render_reference_frame,
    draw_countdown,
    draw_intro,
    draw_fps,
)

# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

VIDEO_URL = (
    "https://d2qncakd447jpu.cloudfront.net/"
    "SKY_Yoga_Physical_Exercises_Play_Practice_with_Video_in_ENGLISH_"
    "Vethathiri_Maharishi_480P.mp4"
)
VIDEO_SOURCE = os.environ.get("SKY_VIDEO", VIDEO_URL)

EXERCISE_TIMELINE = [
    {"key": "hand", "start": 14},
    {"key": "leg", "start": 661},
    {"key": "neuro", "start": 1331},
    {"key": "eye", "start": 1835},
    {"key": "kapalabhati", "start": 1879},
    {"key": "makarasana", "start": 2418},
    {"key": "massage", "start": 3024},
    {"key": "accupressure", "start": 3197},
    {"key": "relaxation", "start": 3490},
]

INTRO_SEC = 5
COUNTDOWN_SEC = 3

# ─────────────────────────────────────────────────────────────────────────────
# FASTAPI APPLICATION
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="SKY Yoga AI Coach API",
    description="REST API for yoga exercise coaching with AI form analysis",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# SHARED STATE (Thread-Safe)
# ─────────────────────────────────────────────────────────────────────────────


class SessionState:
    """Thread-safe state management for the yoga session."""

    def __init__(self):
        self.lock = threading.Lock()
        self._manual_paused = False
        self._should_stop = False
        self._current_frame = None
        self._frame_timestamp = time.time()

        # Exercise tracking
        self.active_exercise = None
        self.rep_count = 0
        self.target_reps = 0
        self.coach_state = "WATCH"
        self.watch_msg = ""
        self.correct = True
        self.message = ""
        self.hold_remaining = 0.0
        self.video_pos = 0.0

    def pause(self):
        with self.lock:
            self._manual_paused = True

    def resume(self):
        with self.lock:
            self._manual_paused = False

    def is_paused(self):
        with self.lock:
            return self._manual_paused

    def set_frame(self, frame):
        with self.lock:
            self._current_frame = frame.copy() if frame is not None else None
            self._frame_timestamp = time.time()

    def get_frame(self):
        with self.lock:
            if self._current_frame is not None:
                return self._current_frame.copy()
            return None

    def get_state(self):
        """Get current session state for API responses."""
        with self.lock:
            return {
                "paused": self._manual_paused,
                "active_exercise": self.active_exercise,
                "rep_count": self.rep_count,
                "target_reps": self.target_reps,
                "coach_state": self.coach_state,
                "watch_msg": self.watch_msg,
                "correct": self.correct,
                "message": self.message,
                "hold_remaining": self.hold_remaining,
                "video_pos": self.video_pos,
            }


session_state = SessionState()


def current_exercise(pos: float):
    """Return the exercise whose start timestamp is <= current video position."""
    ex = None
    for e in EXERCISE_TIMELINE:
        if pos >= e["start"]:
            ex = e
    return ex


# ─────────────────────────────────────────────────────────────────────────────
# VIDEO STREAMING GENERATOR
# ─────────────────────────────────────────────────────────────────────────────


def generate_video_stream():
    """
    Generate MJPEG stream with 50/50 split (user feed + reference feed).
    Yields JPEG-encoded frames in MJPEG format.
    """
    while not session_state._should_stop:
        frame = session_state.get_frame()
        if frame is None:
            time.sleep(0.01)
            continue

        # Encode frame to JPEG
        ret, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ret:
            continue

        # MJPEG boundary marker
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n"
            b"Content-length: " + str(len(buffer)).encode() + b"\r\n\r\n"
            + buffer.tobytes()
            + b"\r\n"
        )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN PROCESSING LOOP
# ─────────────────────────────────────────────────────────────────────────────


def main_loop():
    """
    Main video processing loop.
    Runs in background thread to continuously process frames.
    """
    print("\n" + "=" * 80)
    print("SKY YOGA AI COACH — API Server")
    print("=" * 80)
    print(f"Video : {VIDEO_SOURCE}")
    print(f"Cache : SKY_CACHE_DIR = {os.environ.get('SKY_CACHE_DIR', 'none')}")
    print("API    : http://localhost:8000")
    print("=" * 80 + "\n")

    registry = ExerciseRegistry()
    if not registry.keys():
        print("  WARNING: No exercises loaded. Check exercises/ folder.")

    camera = Camera(0)
    user_engine = PoseEngine("pose_landmarker_heavy.task")
    ref_video = ReferenceVideo(VIDEO_SOURCE)

    wall_start = time.time()
    active_key = None
    controller = None

    try:
        while not session_state._should_stop:
            # ── CAMERA FRAME ──────────────────────────────────────────────
            frame = camera.read()
            h, w, _ = frame.shape
            elapsed = time.time() - wall_start

            # ── INTRO PHASE ───────────────────────────────────────────────
            if elapsed < INTRO_SEC:
                ref_frame = cv2.resize(ref_video.read(), (w, h))
                draw_intro(frame, "SKY Yoga - AI Coach")
                draw_fps(frame)
                video_pos = ref_video.position_seconds()
                render_reference_frame(ref_frame, coach_state="WATCH", video_pos=video_pos)
                combined = cv2.hconcat([frame, ref_frame])
                session_state.set_frame(combined)

                session_state.video_pos = video_pos
                session_state.coach_state = "WATCH"
                time.sleep(0.01)
                continue

            # ── COUNTDOWN PHASE ───────────────────────────────────────────
            if elapsed < INTRO_SEC + COUNTDOWN_SEC:
                secs = int(INTRO_SEC + COUNTDOWN_SEC - elapsed) + 1
                ref_frame = cv2.resize(ref_video.read(), (w, h))
                draw_countdown(frame, secs)
                draw_fps(frame)
                video_pos = ref_video.position_seconds()
                render_reference_frame(ref_frame, coach_state="WATCH", video_pos=video_pos)
                combined = cv2.hconcat([frame, ref_frame])
                session_state.set_frame(combined)

                session_state.video_pos = video_pos
                session_state.coach_state = "WATCH"
                time.sleep(0.01)
                continue

            # ── MAIN SESSION ──────────────────────────────────────────────

            # Video position — if manually paused this stays frozen
            video_pos = ref_video.position_seconds()
            ex_info = current_exercise(video_pos)

            session_state.video_pos = video_pos

            # ── No exercise at this timestamp yet ─────────────────────────
            if ex_info is None:
                ref_frame = cv2.resize(ref_video.read(), (w, h))
                draw_fps(frame)
                render_reference_frame(ref_frame, coach_state="WATCH", video_pos=video_pos)
                combined = cv2.hconcat([frame, ref_frame])
                session_state.set_frame(combined)

                session_state.active_exercise = None
                session_state.coach_state = "WATCH"
                session_state.watch_msg = ""
                session_state.rep_count = 0
                session_state.target_reps = 0

                # VIDEO CONTROL
                if session_state.is_paused():
                    ref_video.pause()
                else:
                    ref_video.resume()

                time.sleep(0.01)
                continue

            # ── EXERCISE SWITCH ───────────────────────────────────────────
            if ex_info["key"] != active_key:
                active_key = ex_info["key"]
                controller = registry.get(active_key)
                if controller:
                    controller.reset_session()
                print(f"→ Exercise: {active_key}")
                session_state.active_exercise = active_key

            # ── DETECT USER POSE ──────────────────────────────────────────
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            user_engine.detect_async(mp_img, int(time.time() * 1000))

            user_lm = None
            if user_engine.latest_result and user_engine.latest_result.pose_landmarks:
                user_lm = user_engine.latest_result.pose_landmarks[0]

            # ── READ REFERENCE FRAME ──────────────────────────────────────
            ref_frame = cv2.resize(ref_video.read(), (w, h))

            # ── COACH EVALUATION ──────────────────────────────────────────
            if controller:
                correct, message, should_pause, hold_remaining = controller.update(
                    video_pos, user_lm, w, h
                )
                coach_state = controller.coach_state
                ap = controller._active_phase
                watch_msg = ap.get("watch_msg", "") if ap else ""
                target_reps = ap.get("target", 0) if ap else 0
                rep_done = controller.rep_count
            else:
                correct, message, should_pause, hold_remaining = (
                    True,
                    f"{ex_info['key'].upper()} - coming soon",
                    False,
                    0.0,
                )
                coach_state = "WATCH"
                watch_msg = ""
                target_reps = 0
                rep_done = 0

            # ── UPDATE SESSION STATE ──────────────────────────────────────
            session_state.coach_state = coach_state
            session_state.watch_msg = watch_msg
            session_state.rep_count = rep_done
            session_state.target_reps = target_reps
            session_state.correct = correct
            session_state.message = message
            session_state.hold_remaining = hold_remaining

            # ── VIDEO CONTROL ─────────────────────────────────────────────
            if session_state.is_paused():
                ref_video.pause()
            elif should_pause:
                ref_video.pause()
            else:
                ref_video.resume()

            # ── DRAW USER FRAME ───────────────────────────────────────────
            frame = user_engine.draw_skeleton(frame, correct)

            # ── DRAW USER FRAME OVERLAY ───────────────────────────────────
            render_user_frame(
                frame,
                coach_state=coach_state,
                watch_msg=watch_msg,
                rep_done=rep_done,
                rep_target=target_reps,
                correct=correct,
                message=message,
                hold_remaining=hold_remaining,
                video_pos=video_pos,
            )

            # ── DRAW REF FRAME ────────────────────────────────────────────
            render_reference_frame(ref_frame, coach_state=coach_state, video_pos=video_pos)

            # ── MANUAL PAUSE INDICATOR on ref frame ───────────────────────
            if session_state.is_paused():
                h_ref, w_ref = ref_frame.shape[:2]
                cv2.putText(
                    ref_frame,
                    "⏸ PAUSED  [API Resume to continue]",
                    (10, h_ref - 12),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.62,
                    (0, 200, 255),
                    2,
                    cv2.LINE_AA,
                )

            # ── DISPLAY (50/50 layout: user on left, reference on right) ───
            combined = cv2.hconcat([frame, ref_frame])
            session_state.set_frame(combined)

            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n✓ Server interrupted")
    except Exception as e:
        print(f"\n✗ Error in main loop: {e}")
    finally:
        session_state._should_stop = True
        camera.release()
        ref_video.release()
        print("✓ Resources released")


# ─────────────────────────────────────────────────────────────────────────────
# API ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────


@app.get("/video/stream")
async def video_stream():
    """Stream video as MJPEG."""
    return StreamingResponse(
        generate_video_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.post("/process")
async def process_frame(file: UploadFile = File(...)):
    """
    Process individual frame sent from client.
    Returns the processed frame with overlays as JPEG.
    
    Usage:
      curl -F "file=@frame.jpg" http://localhost:8000/process > output.jpg
    """
    try:
        # Read the image bytes sent from client
        contents = await file.read()
        np_arr = np.frombuffer(contents, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if frame is None:
            return Response(content=b"", media_type="image/jpeg")

        # Get current session state
        state = session_state.get_state()
        
        # Get the current combined frame from the main loop
        combined = session_state.get_frame()
        
        if combined is not None:
            # Encode and return the current combined frame
            _, buffer = cv2.imencode('.jpg', combined, [cv2.IMWRITE_JPEG_QUALITY, 80])
            return Response(content=buffer.tobytes(), media_type="image/jpeg")
        else:
            # If no frame available yet, return the input frame
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            return Response(content=buffer.tobytes(), media_type="image/jpeg")
            
    except Exception as e:
        print(f"Frame processing error: {e}")
        return Response(content=b"", media_type="image/jpeg")

async def get_status():
    """Get current exercise status."""
    return JSONResponse(content=session_state.get_state())


@app.post("/api/pause")
async def pause_exercise():
    """Pause video and freeze exercise."""
    session_state.pause()
    return JSONResponse(
        content={"success": True, "message": "Exercise paused", "paused": True}
    )


@app.post("/api/resume")
async def resume_exercise():
    """Resume video and exercise."""
    session_state.resume()
    return JSONResponse(
        content={"success": True, "message": "Exercise resumed", "paused": False}
    )


@app.post("/api/reset")
async def reset_exercise():
    """Reset current exercise."""
    session_state.pause()
    session_state.rep_count = 0
    return JSONResponse(
        content={
            "success": True,
            "message": "Exercise reset",
            "rep_count": session_state.rep_count,
        }
    )



# ─────────────────────────────────────────────────────────────────────────────
# STARTUP & SHUTDOWN HANDLERS
# ─────────────────────────────────────────────────────────────────────────────


@app.on_event("startup")
async def startup():
    """Start background processing thread on server startup."""
    thread = threading.Thread(target=main_loop, daemon=True)
    thread.start()
    print("✓ Background processing started")


@app.on_event("shutdown")
async def shutdown():
    """Clean shutdown."""
    session_state._should_stop = True
    print("✓ Server shutting down")


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("Starting SKY Yoga AI Coach API Server...")
    print("=" * 80)
    print("\nWeb Dashboard: http://localhost:8000")
    print("API Docs:      http://localhost:8000/docs")
    print("=" * 80 + "\n")

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
