"""
main.py — SKY Yoga AI Coach
Production-ready entry point with clean video streaming and exercise flow.

FIXES:
  - SPACE bar pauses/resumes reference video properly
  - While paused, exercise at the FROZEN timestamp still runs (form + rep count)
  - Watch Carefully is shown from phase start → active time (WATCH/PREPARE states)
  - HOLD timer fires once per phase and always expires after 10s
  - Hand exercise p1: raise+join+lower = 1 rep
"""
import os
import cv2
import time
import mediapipe as mp
from core.camera import Camera
from core.pose_engine import PoseEngine
from core.video_controller import ReferenceVideo
from core.exercise_registry import ExerciseRegistry
from core.sarvam_voice import SarvamVoiceCoach, VoiceFrame
from core.ui_render import render_frame, render_user_frame, render_reference_frame, draw_countdown, draw_intro, draw_fps

# ─────────────────────────────────────────────────────────────────────────────
# VIDEO SOURCE
# ─────────────────────────────────────────────────────────────────────────────

VIDEO_URL = (
    "https://d2qncakd447jpu.cloudfront.net/"
    "SKY_Yoga_Physical_Exercises_Play_Practice_with_Video_in_ENGLISH_"
    "Vethathiri_Maharishi_480P.mp4"
)
VIDEO_SOURCE = os.environ.get("SKY_VIDEO", VIDEO_URL)

# ─────────────────────────────────────────────────────────────────────────────
# EXERCISE TIMELINE  (video timestamps in seconds)
# ─────────────────────────────────────────────────────────────────────────────

EXERCISE_TIMELINE = [
    {"key": "hand",        "start": 14},
    {"key": "leg",         "start": 661},
    {"key": "neuro",       "start": 1331},
    {"key": "eye",         "start": 1835},
    {"key": "kapalabhati", "start": 1879},
    {"key": "makarasana",  "start": 2418},
    {"key": "massage",     "start": 3024},
    {"key": "accupressure", "start": 3197},
    {"key": "relaxation",  "start": 3490},
]

INTRO_SEC     = 5
COUNTDOWN_SEC = 3


def current_exercise(pos: float):
    """Return the exercise whose start timestamp is <= current video position."""
    ex = None
    for e in EXERCISE_TIMELINE:
        if pos >= e["start"]:
            ex = e
    return ex


# ─────────────────────────────────────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 80)
    print("SKY YOGA AI COACH — Production Ready")
    print("=" * 80)
    print(f"Video : {VIDEO_SOURCE}")
    print(f"Cache : SKY_CACHE_DIR = {os.environ.get('SKY_CACHE_DIR', 'none')}")
    print("Controls: [SPACE] pause/resume video  |  [Q] quit")
    print("=" * 80 + "\n")

    registry = ExerciseRegistry()
    if not registry.keys():
        print("  WARNING: No exercises loaded. Check exercises/ folder.")

    camera      = Camera(0)
    user_engine = PoseEngine("pose_landmarker_heavy.task")
    ref_video   = ReferenceVideo(VIDEO_SOURCE)
    voice_coach = SarvamVoiceCoach()

    wall_start = time.time()
    active_key = None
    controller = None

    # Track manual pause (SPACE) separately from coach-driven pause
    _manual_paused = False

    try:
        while True:
            # ── CAMERA FRAME ─────────────────────────────────────────────
            frame   = camera.read()
            h, w, _ = frame.shape
            elapsed = time.time() - wall_start

            # ── INTRO PHASE ───────────────────────────────────────────────
            if elapsed < INTRO_SEC:
                ref_frame = cv2.resize(ref_video.read(), (w, h))
                draw_intro(frame, "SKY Yoga - AI Coach")
                draw_fps(frame)
                video_pos = ref_video.position_seconds()
                render_reference_frame(ref_frame, coach_state="WATCH", video_pos=video_pos)
                cv2.imshow("SKY Yoga", cv2.hconcat([frame, ref_frame]))
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                continue

            # ── COUNTDOWN PHASE ───────────────────────────────────────────
            if elapsed < INTRO_SEC + COUNTDOWN_SEC:
                secs      = int(INTRO_SEC + COUNTDOWN_SEC - elapsed) + 1
                ref_frame = cv2.resize(ref_video.read(), (w, h))
                draw_countdown(frame, secs)
                draw_fps(frame)
                video_pos = ref_video.position_seconds()
                render_reference_frame(ref_frame, coach_state="WATCH", video_pos=video_pos)
                cv2.imshow("SKY Yoga", cv2.hconcat([frame, ref_frame]))
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                continue

            # ── MAIN SESSION ──────────────────────────────────────────────

            # Video position — if manually paused this stays frozen
            video_pos = ref_video.position_seconds()
            ex_info   = current_exercise(video_pos)

            # ── No exercise at this timestamp yet ─────────────────────────
            if ex_info is None:
                ref_frame = cv2.resize(ref_video.read(), (w, h))
                draw_fps(frame)
                render_reference_frame(ref_frame, coach_state="WATCH", video_pos=video_pos)
                cv2.imshow("SKY Yoga", cv2.hconcat([frame, ref_frame]))
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                elif key == ord(" "):
                    _manual_paused = not _manual_paused
                    if _manual_paused:
                        ref_video.pause()
                        print("⏸ Video paused")
                    else:
                        ref_video.resume()
                        print("▶ Video resumed")
                continue

            # ── EXERCISE SWITCH ───────────────────────────────────────────
            if ex_info["key"] != active_key:
                active_key = ex_info["key"]
                controller = registry.get(active_key)
                if controller:
                    controller.reset_session()
                    voice_coach.warm_phase_prompts(controller.phases())
                print(f"→ Exercise: {active_key}")

            # ── DETECT USER POSE ──────────────────────────────────────────
            rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            user_engine.detect_async(mp_img, int(time.time() * 1000))

            user_lm = None
            if (user_engine.latest_result
                    and user_engine.latest_result.pose_landmarks):
                user_lm = user_engine.latest_result.pose_landmarks[0]

            # ── READ REFERENCE FRAME ──────────────────────────────────────
            ref_frame = cv2.resize(ref_video.read(), (w, h))

            # ── COACH EVALUATION ──────────────────────────────────────────
            if controller:
                correct, message, should_pause, hold_remaining = controller.update(
                    video_pos, user_lm, w, h
                )
                coach_state  = controller.coach_state
                # Use _active_phase (cached by update()) - persists through gaps
                # and HOLD so rep counter / watch_msg never go blank mid-exercise
                ap           = controller._active_phase
                watch_msg    = ap.get("watch_msg", "") if ap else ""
                target_reps  = ap.get("target", 0)    if ap else 0
                rep_done     = controller.rep_count
            else:
                correct, message, should_pause, hold_remaining = (
                    True,
                    f"{ex_info['key'].upper()} - coming soon",
                    False,
                    0.0,
                )
                coach_state = "WATCH"
                watch_msg   = ""
                target_reps = 0
                rep_done    = 0

            active_phase = controller._active_phase if controller else None
            voice_coach.update(
                VoiceFrame(
                    exercise_key = active_key,
                    phase_id = active_phase.get("id") if active_phase else None,
                    phase_name = active_phase.get("name", "") if active_phase else "",
                    coach_state = coach_state,
                    watch_msg = watch_msg,
                    message = message,
                    correct = correct,
                    rep_done = rep_done,
                    rep_target = target_reps,
                    hold_remaining = hold_remaining,
                    paused = _manual_paused,
                    video_pos = video_pos,
                    phase_active = active_phase.get("active") if active_phase else None,
                    phase_end = active_phase.get("end") if active_phase else None,
                )
            )

            # ── VIDEO CONTROL ─────────────────────────────────────────────
            # Coach-driven pause (form error / HOLD state)
            # Manual pause overrides both: once user presses SPACE, video
            # stays paused until SPACE is pressed again regardless of coach.
            if _manual_paused:
                ref_video.pause()          # keep frozen
            elif should_pause:
                ref_video.pause()
            else:
                ref_video.resume()

            # ── DRAW USER FRAME ───────────────────────────────────────────
            frame = user_engine.draw_skeleton(frame, correct)

            # ── DRAW USER FRAME OVERLAY ───────────────────────────────────
            # Apply all FPS, rep counter, and feedback messages to user frame
            render_user_frame(
                frame,
                coach_state    = coach_state,
                watch_msg      = watch_msg,
                rep_done       = rep_done,
                rep_target     = target_reps,
                correct        = correct,
                message        = message,
                hold_remaining = hold_remaining,
                video_pos      = video_pos,
            )

            # ── DRAW REF FRAME ────────────────────────────────────────────
            # Keep reference frame clean with minimal UI + timer
            render_reference_frame(ref_frame, coach_state=coach_state, video_pos=video_pos)

            # ── MANUAL PAUSE INDICATOR on ref frame ───────────────────────
            if _manual_paused:
                h_ref, w_ref = ref_frame.shape[:2]
                cv2.putText(
                    ref_frame,
                    "⏸ PAUSED  [SPACE to resume]",
                    (10, h_ref - 12),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.62, (0, 200, 255), 2, cv2.LINE_AA,
                )

            # ── DISPLAY (50/50 layout: user on left, reference on right) ───
            cv2.imshow("SKY Yoga", cv2.hconcat([frame, ref_frame]))

            # ── KEY HANDLING ──────────────────────────────────────────────
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord(" "):
                _manual_paused = not _manual_paused
                if _manual_paused:
                    ref_video.pause()
                    print(" Video paused by user")
                else:
                    ref_video.resume()
                    print(" Video resumed by user")

    finally:
        voice_coach.shutdown()
        camera.release()
        ref_video.release()
        cv2.destroyAllWindows()
        print("\n✓ Session ended cleanly.\n")


if __name__ == "__main__":
    main()
