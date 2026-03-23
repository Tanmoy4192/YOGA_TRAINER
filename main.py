"""
main.py — SKY Yoga AI Coach
Production-ready entry point with clean video streaming and exercise flow.

ARCHITECTURE:
  1. Load Camera and PoseEngine (user detection only)
  2. Load ReferenceVideo with smart position tracking
  3. Auto-discover exercises from exercises/ folder
  4. Main loop: detect user pose, evaluate against current phase, control video

NO REFERENCE ENGINE — user form is evaluated using body-scale-normalized rules only.
NO SIMILARITY SCORES — pure joint angle and distance checks.
"""
import os
import cv2
import time
import mediapipe as mp
from core.camera import Camera
from core.pose_engine import PoseEngine
from core.video_controller import ReferenceVideo
from core.exercise_registry import ExerciseRegistry
from core.ui_render import (
    draw_coach_message,
    draw_rep_counter,
    draw_phase_banner,
    draw_countdown,
    draw_intro,
    draw_hold_overlay,
)

# ─────────────────────────────────────────────────────────────────────────────
# VIDEO SOURCE CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

VIDEO_URL = (
    "https://d2qncakd447jpu.cloudfront.net/"
    "SKY_Yoga_Physical_Exercises_Play_Practice_with_Video_in_ENGLISH_"
    "Vethathiri_Maharishi_480P.mp4"
)

VIDEO_SOURCE = os.environ.get("SKY_VIDEO", VIDEO_URL)

# ─────────────────────────────────────────────────────────────────────────────
# EXERCISE TIMELINE (full 1-hour video, timestamps include +67s intro buffer)
# ─────────────────────────────────────────────────────────────────────────────

EXERCISE_TIMELINE = [
    {"key": "hand", "start": 67},  # 1:07 — Hand exercises begin
    {"key": "leg", "start": 727},  # 12:07
    {"key": "neuro", "start": 1037},  # 17:17
    {"key": "eye", "start": 1497},  # 24:57
    {"key": "kapalabhati", "start": 1838},  # 30:38
    {"key": "makarasana", "start": 1944},  # 32:24
    {"key": "massage", "start": 2584},  # 43:04
    {"key": "acupressure", "start": 2756},  # 45:56
    {"key": "relaxation", "start": 3100},  # 51:40
]

INTRO_SEC = 5
COUNTDOWN_SEC = 3


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────


def current_exercise(pos: float):
    """
    Find the exercise active at video_pos.
    Returns the exercise dict, or None if no exercise is active yet.
    """
    ex = None
    for e in EXERCISE_TIMELINE:
        if pos >= e["start"]:
            ex = e
    return ex


# ─────────────────────────────────────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────────────────────────────────────


def main():
    """Main application loop."""
    print("\n" + "=" * 80)
    print("SKY YOGA AI COACH — Production Ready")
    print("=" * 80)
    print(f"Video: {VIDEO_SOURCE}")
    print(f"Cache: SKY_CACHE_DIR = {os.environ.get('SKY_CACHE_DIR', 'none')}")
    print("=" * 80 + "\n")

    # Load registry (auto-discovers exercises/)
    registry = ExerciseRegistry()
    if not registry.keys():
        print("  WARNING: No exercises loaded. Check exercises/ folder.")

    # Initialize camera and pose detection
    camera = Camera(0)
    user_engine = PoseEngine("pose_landmarker_heavy.task")

    # Initialize reference video with smart position tracking
    ref_video = ReferenceVideo(VIDEO_SOURCE)

    # Timeline tracking
    wall_start = time.time()
    active_key = None
    controller = None

    # Main loop
    try:
        while True:
            # ─── READ FRAMES ─────────────────────────────────────────────────
            frame = camera.read()
            h, w, _ = frame.shape
            elapsed = time.time() - wall_start

            # ─── INTRO PHASE (5 seconds) ─────────────────────────────────────
            if elapsed < INTRO_SEC:
                ref_frame = ref_video.read()
                ref_frame = cv2.resize(ref_frame, (w, h))
                draw_intro(ref_frame, "SKY Yoga - AI Coach")
                cv2.imshow("SKY Yoga", cv2.hconcat([frame, ref_frame]))
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
                continue

            # ─── COUNTDOWN PHASE (3 seconds) ─────────────────────────────────
            if elapsed < INTRO_SEC + COUNTDOWN_SEC:
                secs = int(INTRO_SEC + COUNTDOWN_SEC - elapsed) + 1
                ref_frame = ref_video.read()
                ref_frame = cv2.resize(ref_frame, (w, h))
                draw_countdown(ref_frame, secs)
                cv2.imshow("SKY Yoga", cv2.hconcat([frame, ref_frame]))
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
                continue

            # ─── MAIN SESSION ────────────────────────────────────────────────

            # Get current video position
            video_pos = ref_video.position_seconds()

            # Find current exercise
            ex_info = current_exercise(video_pos)
            if ex_info is None:
                ref_frame = ref_video.read()
                ref_frame = cv2.resize(ref_frame, (w, h))
                cv2.imshow("SKY Yoga", cv2.hconcat([frame, ref_frame]))
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
                continue

            # ─── EXERCISE SWITCH ────────────────────────────────────────────
            if ex_info["key"] != active_key:
                active_key = ex_info["key"]
                controller = registry.get(active_key)
                if controller:
                    controller.reset_session()

            # ─── DETECT USER POSE ───────────────────────────────────────────
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            user_engine.detect_async(mp_img, int(time.time() * 1000))

            user_lm = None
            if (user_engine.latest_result
                    and user_engine.latest_result.pose_landmarks):
                user_lm = user_engine.latest_result.pose_landmarks[0]

            # ─── READ REFERENCE FRAME ───────────────────────────────────────
            ref_frame = ref_video.read()
            ref_frame = cv2.resize(ref_frame, (w, h))

            # ─── COACH EVALUATION ────────────────────────────────────────────
            # Controller is the ONLY authority for pause decisions
            if controller:
                # Controller.update() returns: (correct, message, should_pause)
                # - correct: bool - skeleton color (True=green, False=red)
                # - message: str - coaching feedback
                # - should_pause: bool - controller decides if video should pause
                correct, message, should_pause = controller.update(
                    video_pos, user_lm, w, h
                )
                phase_name = controller.current_phase_name
                coach_state = controller.coach_state
                target = controller._get_phase(video_pos)
                target_reps = target["target"] if target else 0
            else:
                # Exercise not implemented yet
                correct, message, should_pause = (
                    True,
                    f"{ex_info['key'].upper()} — coming soon",
                    False,
                )
                phase_name = ex_info["key"]
                coach_state = "WATCH"
                target_reps = 0

            # ─── VIDEO CONTROL (Controller Has Full Authority) ──────────────
            # Controller is the ONLY authority for pause/resume decisions
            # This is the ONLY place where video pause is controlled from main.py
            if should_pause:
                ref_video.pause()
            else:
                ref_video.resume()

            # ─── DRAW USER FRAME (skeleton) ──────────────────────────────────
            frame = user_engine.draw_skeleton(frame, correct)

            # ─── DRAW REF FRAME (mentor + UI) ───────────────────────────────
            draw_phase_banner(ref_frame, phase_name, coach_state)

            # Draw HOLD overlay if in HOLD state
            if coach_state == "HOLD":
                draw_hold_overlay(ref_frame, message)
            else:
                draw_coach_message(ref_frame, message, correct)

            if controller and target_reps > 0:
                draw_rep_counter(ref_frame, controller.rep_count, target_reps)

            # ─── DISPLAY ─────────────────────────────────────────────────────
            combined = cv2.hconcat([frame, ref_frame])
            cv2.imshow("SKY Yoga", combined)

            # ─── KEYBOARD CONTROLS ───────────────────────────────────────
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord(" "):  # Spacebar - pause/resume video
                if ref_video._paused:
                    ref_video.resume()
                    print("▶ Video resumed")
                else:
                    ref_video.pause()
                    print("⏸ Video paused (press SPACE to resume)")

    finally:
        camera.release()
        ref_video.release()
        cv2.destroyAllWindows()
        print("\n✓ Session ended cleanly.\n")


if __name__ == "__main__":
    main()