"""
main.py — SKY Yoga AI Coach
"""

import cv2
import time
import mediapipe as mp

from core.camera             import Camera
from core.pose_engine        import PoseEngine
from core.video_controller   import ReferenceVideo
from core.reference_analyzer import ReferenceAnalyzer
from core.exercise_registry  import ExerciseRegistry
from core.ui_render        import (
    draw_coach_message, draw_rep_counter,
    draw_phase_banner, draw_countdown, draw_intro,
)

# ── Video source ──────────────────────────────────────────────────────
# For the full 1-hour video replace with the CDN URL.
# For local testing use the compressed clip path.
VIDEO_SOURCE = (
    "https://d2qncakd447jpu.cloudfront.net/"
    "SKY_Yoga_Physical_Exercises_Play_Practice_with_Video_in_ENGLISH_"
    "Vethathiri_Maharishi_480P.mp4"
)

# ── Top-level exercise timeline ───────────────────────────────────────
# start = video timestamp (seconds) when this exercise begins
# For the full 1-hour video add +67 to each start value.
EXERCISE_TIMELINE = [
    {"key": "hand",        "start":   67},   # 1:07  — add +67 for full video
    {"key": "leg",         "start":  727},   # 12:07
    {"key": "neuro",       "start": 1037},
    {"key": "eye",         "start": 1497},
    {"key": "kapalabhati", "start": 1838},
    {"key": "makarasana",  "start": 1944},
    {"key": "massage",     "start": 2584},
    {"key": "acupressure", "start": 2756},
    {"key": "relaxation",  "start": 3100},
]

INTRO_SEC     = 5
COUNTDOWN_SEC = 3


def current_exercise(pos: float):
    ex = None
    for e in EXERCISE_TIMELINE:
        if pos >= e["start"]:
            ex = e
    return ex


def main():
    registry     = ExerciseRegistry()
    camera       = Camera(0)
    user_engine  = PoseEngine("pose_landmarker_heavy.task")
    ref_engine   = PoseEngine("pose_landmarker_heavy.task")
    ref_video    = ReferenceVideo(VIDEO_SOURCE)
    ref_analyzer = ReferenceAnalyzer(ref_engine)

    wall_start   = time.time()
    active_key   = None
    controller   = None

    while True:
        frame  = camera.read()
        h, w, _ = frame.shape
        elapsed = time.time() - wall_start

        # ── INTRO ────────────────────────────────────────────────
        if elapsed < INTRO_SEC:
            ref_frame = ref_video.read()
            ref_frame = cv2.resize(ref_frame, (w, h))
            draw_intro(ref_frame, "SKY Yoga — AI Coach")
            cv2.imshow("SKY Yoga", cv2.hconcat([frame, ref_frame]))
            if cv2.waitKey(1) & 0xFF == ord("q"): break
            continue

        # ── COUNTDOWN ────────────────────────────────────────────
        if elapsed < INTRO_SEC + COUNTDOWN_SEC:
            secs = int(INTRO_SEC + COUNTDOWN_SEC - elapsed) + 1
            ref_frame = ref_video.read()
            ref_frame = cv2.resize(ref_frame, (w, h))
            draw_countdown(ref_frame, secs)
            cv2.imshow("SKY Yoga", cv2.hconcat([frame, ref_frame]))
            if cv2.waitKey(1) & 0xFF == ord("q"): break
            continue

        # ── VIDEO POSITION ───────────────────────────────────────
        video_pos = ref_video.position_seconds()
        ex_info   = current_exercise(video_pos)

        if ex_info is None:
            ref_frame = ref_video.read()
            ref_frame = cv2.resize(ref_frame, (w, h))
            cv2.imshow("SKY Yoga", cv2.hconcat([frame, ref_frame]))
            if cv2.waitKey(1) & 0xFF == ord("q"): break
            continue

        # ── SWITCH EXERCISE ───────────────────────────────────────
        if ex_info["key"] != active_key:
            active_key = ex_info["key"]
            controller = registry.get(active_key)
            if controller:
                controller.rep_count    = 0
                controller.error_frames = 0
                controller.good_frames  = 0

        # ── USER POSE DETECTION ───────────────────────────────────
        rgb      = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_img   = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        user_engine.detect_async(mp_img, int(time.time() * 1000))
        user_lm  = None
        if (user_engine.latest_result
                and user_engine.latest_result.pose_landmarks):
            user_lm = user_engine.latest_result.pose_landmarks[0]

        # ── REFERENCE FRAME ───────────────────────────────────────
        ref_frame  = ref_video.read()
        ref_frame  = cv2.resize(ref_frame, (w, h))
        ref_lm     = ref_analyzer.extract(ref_frame)

        # ── COACH EVALUATION ──────────────────────────────────────
        if controller:
            correct, message = controller.update(
                video_pos, user_lm, ref_lm, w, h
            )
            phase_name   = controller.current_phase_name
            coach_state  = controller.coach_state
            target       = controller._get_phase(video_pos)
            target_reps  = target["target"] if target else 0
        else:
            correct, message = True, f"{ex_info['key'].upper()} — coming soon"
            phase_name   = ex_info["key"]
            coach_state  = "WATCH"
            target_reps  = 0

        # ── VIDEO CONTROL ─────────────────────────────────────────
        if correct:
            ref_video.resume()
        else:
            ref_video.pause()

        # ── DRAW USER FRAME ───────────────────────────────────────
        frame = user_engine.draw_skeleton(frame, correct)

        # ── DRAW REF FRAME ────────────────────────────────────────
        draw_phase_banner(ref_frame, phase_name, coach_state)
        draw_coach_message(ref_frame, message, correct)
        if controller and target_reps > 0:
            draw_rep_counter(ref_frame, controller.rep_count, target_reps)

        # ── DISPLAY ───────────────────────────────────────────────
        combined = cv2.hconcat([frame, ref_frame])
        cv2.imshow("SKY Yoga", combined)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    camera.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()