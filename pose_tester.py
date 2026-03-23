"""
pose_test.py — SKY Yoga Exercise Tester
========================================
Tests a single exercise in isolation with the reference video.

USAGE
-----
  # Test exercise by key (seeks video to that exercise's active timestamp)
  python pose_test.py --exercise hand
  python pose_test.py --exercise hand --phase p2_t_pose
  python pose_test.py --exercise hand --phase p2_t_pose --seek 160

  # Override video source
  python pose_test.py --exercise hand --video /path/to/local.mp4

CONTROLS (keyboard)
-------------------
  SPACE       pause / resume reference video
  N           jump to NEXT phase in this exercise
  P           jump to PREV phase in this exercise
  R           reset rep counter and state for current phase
  +  /  =     seek forward  +5 seconds
  -           seek backward -5 seconds
  D           toggle debug overlay (raw landmark values)
  Q / ESC     quit

DISPLAY (reference video side)
-------------------------------
  Top-left   : current phase name  |  coach state pill
  Below       : WATCH CAREFULLY banner (during WATCH/PREPARE)
  Left side   : rep counter  X / Y
  Bottom bar  : coach feedback message (green = correct, red = error)
  Top-right   : video timestamp  |  FPS
  Debug panel : raw landmark positions, state machine internals (toggle D)

DISPLAY (user camera side)
--------------------------
  Skeleton drawn green (good form) or red (error)
  Phase state shown top-left
"""

import os
import sys
import cv2
import time
import argparse
import importlib
import mediapipe as mp

# ── Path setup ────────────────────────────────────────────────────────────────
# Allow running from project root OR from tools/ subfolder
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.camera         import Camera
from core.pose_engine    import PoseEngine
from core.video_controller import ReferenceVideo
from core.ui_render      import (draw_phase_banner, draw_watch_carefully,
                                 draw_rep_counter, draw_coach_message,
                                 draw_hold_overlay, draw_fps)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

VIDEO_URL = (
    "https://d2qncakd447jpu.cloudfront.net/"
    "SKY_Yoga_Physical_Exercises_Play_Practice_with_Video_in_ENGLISH_"
    "Vethathiri_Maharishi_480P.mp4"
)

# Global exercise start timestamps (same as main.py)
EXERCISE_TIMELINE = {
    "hand":        67,
    "leg":         727,
    "neuro":       1037,
    "eye":         1497,
    "kapalabhati": 1838,
    "makarasana":  1944,
    "massage":     2584,
    "acupressure": 2756,
    "relaxation":  3100,
}

# ─────────────────────────────────────────────────────────────────────────────
# COLOURS  (BGR)
# ─────────────────────────────────────────────────────────────────────────────

_WHITE  = (240, 240, 240)
_GREY   = (140, 140, 140)
_DARK   = (18,  18,  18)
_GREEN  = (60,  220, 80)
_RED    = (50,  50,  220)
_CYAN   = (220, 200, 0)
_YELLOW = (0,   200, 255)
_ORANGE = (0,   140, 255)

FONT = cv2.FONT_HERSHEY_SIMPLEX

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _pill(frame, text, x, y, bg, fg, scale=0.55, thick=1):
    """Draw a small pill-shaped label."""
    ts  = cv2.getTextSize(text, FONT, scale, thick)[0]
    pad = 5
    cv2.rectangle(frame, (x - pad, y - ts[1] - pad),
                  (x + ts[0] + pad, y + pad), bg, -1)
    cv2.putText(frame, text, (x, y), FONT, scale, fg, thick, cv2.LINE_AA)
    return x + ts[0] + pad * 2 + 6   # return next x


def _text(frame, text, x, y, color=_WHITE, scale=0.55, thick=1):
    cv2.putText(frame, text, (x, y), FONT, scale, color, thick, cv2.LINE_AA)


def draw_timestamp(frame, video_pos: float):
    """Top-right: video position mm:ss."""
    h, w = frame.shape[:2]
    mins = int(video_pos) // 60
    secs = int(video_pos) % 60
    label = f"{mins:02d}:{secs:02d}  ({video_pos:.1f}s)"
    ts = cv2.getTextSize(label, FONT, 0.55, 1)[0]
    x  = w - ts[0] - 12
    _pill(frame, label, x, 28, _DARK, _GREY)


def draw_phase_selector(frame, phases, current_phase, video_pos):
    """
    Bottom strip on the user-camera side showing all phases as pills.
    Current phase highlighted. Shows which phases are complete / active / upcoming.
    """
    h, w = frame.shape[:2]
    BAR  = 36
    cv2.rectangle(frame, (0, h - BAR), (w, h), _DARK, -1)
    cv2.line(frame, (0, h - BAR), (w, h - BAR), _GREY, 1)

    x = 8
    for p in phases:
        pid   = p["id"]
        name  = p.get("name", pid)[:12]   # truncate long names
        start = p["start"]
        end   = p.get("end", float("inf"))
        active= p.get("active", start)

        is_current = (pid == (current_phase or {}).get("id"))
        is_past    = video_pos >= end
        is_active_now = active <= video_pos < end

        if is_current:
            bg, fg = _CYAN, _DARK
        elif is_past:
            bg, fg = (40, 80, 40), _GREY
        elif is_active_now:
            bg, fg = (0, 60, 0), _GREEN
        else:
            bg, fg = (40, 40, 40), _GREY

        x = _pill(frame, name, x, h - 10, bg, fg, scale=0.42, thick=1)
        if x > w - 60:   # wrap prevention
            break


def draw_debug_panel(frame, controller, video_pos, user_lm, w, h):
    """
    Semi-transparent right-side debug panel showing:
    - Coach state
    - Phase id + time window
    - Rep count
    - Key landmark positions
    - Internal state vars
    """
    fw, fh = frame.shape[1], frame.shape[0]
    PW = 260
    x0 = fw - PW

    overlay = frame.copy()
    cv2.rectangle(overlay, (x0, 52), (fw, fh - 40), (10, 10, 10), -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)
    cv2.line(frame, (x0, 52), (x0, fh - 40), _GREY, 1)

    y = 72
    lh = 20   # line height

    def row(label, val, color=_WHITE):
        nonlocal y
        _text(frame, f"{label:<14}: {val}", x0 + 6, y, _GREY, 0.42)
        y += lh

    ap = controller._active_phase
    row("state",      controller.coach_state)
    row("phase_id",   (ap or {}).get("id", "none"))
    row("phase_name", (ap or {}).get("name", "—")[:16])
    row("video_pos",  f"{video_pos:.1f}s")

    if ap:
        start  = ap.get("start", 0)
        active = ap.get("active", start)
        end    = ap.get("end", 0)
        row("start",  f"{start}s")
        row("active", f"{active}s")
        row("end",    f"{end}s")
        row("target", ap.get("target", 0))

    row("reps",       controller.rep_count)
    row("hold_rem",   f"{controller.hold_remaining:.1f}s")
    row("err_frames", controller.error_frames)

    # Exercise-1 internal state
    if hasattr(controller, "_p1_state"):
        y += 4
        cv2.line(frame, (x0 + 4, y), (fw - 4, y), (60, 60, 60), 1)
        y += 8
        row("p1_state",  controller._p1_state)
        if controller._p1_hold_start:
            row("p1_held",   f"{time.time()-controller._p1_hold_start:.1f}s")
        if controller._p1_down_start:
            row("p1_rested", f"{time.time()-controller._p1_down_start:.1f}s")

    # Exercise-2 internal state
    if hasattr(controller, "_p2_state"):
        y += 4
        cv2.line(frame, (x0 + 4, y), (fw - 4, y), (60, 60, 60), 1)
        y += 8
        row("p2_state",  controller._p2_state)

    # Key landmark values if visible
    if user_lm:
        y += 4
        cv2.line(frame, (x0 + 4, y), (fw - 4, y), (60, 60, 60), 1)
        y += 8
        def lmrow(name, idx):
            if idx < len(user_lm) and user_lm[idx].visibility > 0.3:
                lmk = user_lm[idx]
                row(name, f"({lmk.x:.2f},{lmk.y:.2f})")
            else:
                row(name, "invisible", _RED)

        lmrow("nose[0]",   0)
        lmrow("L_shldr[11]", 11)
        lmrow("R_shldr[12]", 12)
        lmrow("L_wrist[15]", 15)
        lmrow("R_wrist[16]", 16)
        lmrow("L_hip[23]",  23)
        lmrow("R_hip[24]",  24)


def draw_controls_hint(frame):
    """Small controls reminder at very bottom of user frame."""
    h, w = frame.shape[:2]
    hints = "SPACE=pause  N=next  P=prev  R=reset  +/-=seek  D=debug  Q=quit"
    ts = cv2.getTextSize(hints, FONT, 0.38, 1)[0]
    x  = (w - ts[0]) // 2
    cv2.putText(frame, hints, (x, h - 42), FONT, 0.38, _GREY, 1, cv2.LINE_AA)


# ─────────────────────────────────────────────────────────────────────────────
# LOAD EXERCISE MODULE
# ─────────────────────────────────────────────────────────────────────────────

def load_exercise(key: str):
    """Import exercises/<key>_exercise.py and return a WorkoutController."""
    module_names = [
        f"exercises.{key}_exercise",
        f"exercises.{key}",
        f"{key}_exercise",
    ]
    for name in module_names:
        try:
            mod = importlib.import_module(name)
            ctrl = mod.WorkoutController()
            print(f"✓ Loaded exercise module: {name}")
            return ctrl, mod
        except ModuleNotFoundError:
            continue
        except Exception as e:
            print(f"✗ Error loading {name}: {e}")
            raise

    raise SystemExit(
        f"Cannot find exercise module for key='{key}'.\n"
        f"Tried: {module_names}\n"
        f"Make sure exercises/{key}_exercise.py exists."
    )


# ─────────────────────────────────────────────────────────────────────────────
# PHASE NAVIGATION
# ─────────────────────────────────────────────────────────────────────────────

def get_phase_index(phases, phase_id):
    for i, p in enumerate(phases):
        if p["id"] == phase_id:
            return i
    return 0


def seek_to_phase(ref_video, controller, phase, offset_sec=0.0):
    """
    Seek the reference video to the start of a phase.
    Adds a small pre-roll (2s before phase start) so user sees the transition.
    Resets the controller for a clean test.
    """
    target = max(0.0, phase["start"] - 2.0 + offset_sec)
    ref_video.seek(target)
    controller.reset_session()
    # Force _active_phase to the new phase so state is correct immediately
    controller._active_phase = phase
    print(f"  → Seeked to {target:.1f}s  (phase '{phase['id']}' starts at {phase['start']}s)")


# ─────────────────────────────────────────────────────────────────────────────
# RENDER  (ref frame overlay — mirrors main.py render_frame)
# ─────────────────────────────────────────────────────────────────────────────

def render_test_frame(ref_frame, coach_state, watch_msg, rep_done,
                      rep_target, correct, message, hold_remaining):
    """Render the reference frame with all overlays (same as production)."""
    draw_phase_banner(ref_frame, coach_state)
    draw_fps(ref_frame)

    if coach_state in ("WATCH", "PREPARE", "ZOOM"):
        draw_watch_carefully(ref_frame, watch_msg)

    if rep_target > 0 and coach_state in ("ACTIVE", "HOLD"):
        draw_rep_counter(ref_frame, rep_done, rep_target, watch_active=False)

    if coach_state == "ACTIVE" and message:
        draw_coach_message(ref_frame, message, correct)

    if coach_state == "HOLD":
        draw_hold_overlay(ref_frame, message, hold_remaining)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN TEST LOOP
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="SKY Yoga — Exercise Tester")
    parser.add_argument("--exercise", "-e", required=True,
                        help="Exercise key, e.g. hand, leg, neuro")
    parser.add_argument("--phase",    "-p", default=None,
                        help="Phase ID to start at, e.g. p2_t_pose")
    parser.add_argument("--seek",     "-s", type=float, default=None,
                        help="Absolute video seek position (seconds)")
    parser.add_argument("--video",    "-v", default=None,
                        help="Override video source (local file or URL)")
    parser.add_argument("--cam",      "-c", type=int, default=0,
                        help="Camera index (default 0)")
    parser.add_argument("--debug",    "-d", action="store_true",
                        help="Start with debug panel open")
    args = parser.parse_args()

    # ── Load exercise ─────────────────────────────────────────────────────
    controller, mod = load_exercise(args.exercise)
    phases = controller.phases()
    print(f"\n  Exercise : {args.exercise}")
    print(f"  Phases   : {[p['id'] for p in phases]}\n")

    # ── Determine start phase ─────────────────────────────────────────────
    if args.phase:
        start_idx = get_phase_index(phases, args.phase)
        if phases[start_idx]["id"] != args.phase:
            print(f"  WARNING: phase '{args.phase}' not found, using first phase")
    else:
        start_idx = 0

    current_phase_idx = start_idx

    # ── Open video ────────────────────────────────────────────────────────
    video_src = args.video or os.environ.get("SKY_VIDEO", VIDEO_URL)
    print(f"  Video    : {video_src}")
    ref_video = ReferenceVideo(video_src)

    # Offset: the exercise's global timeline start
    global_offset = EXERCISE_TIMELINE.get(args.exercise, 0)

    # ── Initial seek ──────────────────────────────────────────────────────
    if args.seek is not None:
        ref_video.seek(args.seek)
        controller.reset_session()
        print(f"  Seeked   : {args.seek}s (manual)")
    else:
        phase0 = phases[current_phase_idx]
        seek_to_phase(ref_video, controller, phase0)

    # ── Open camera & pose engine ─────────────────────────────────────────
    camera      = Camera(args.cam)
    user_engine = PoseEngine("pose_landmarker_heavy.task")

    # ── State ─────────────────────────────────────────────────────────────
    show_debug   = args.debug
    manual_paused = False

    print("\n  Running — press Q or ESC to quit\n")

    try:
        while True:
            # ── Grab frames ───────────────────────────────────────────────
            cam_frame = camera.read()
            h, w, _   = cam_frame.shape
            video_pos = ref_video.position_seconds()

            # Adjust video_pos by global offset so it matches phase timestamps
            # (phases store timestamps relative to exercise start in the video)
            local_pos = video_pos - global_offset

            # ── Pose detection ────────────────────────────────────────────
            rgb    = cv2.cvtColor(cam_frame, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            user_engine.detect_async(mp_img, int(time.time() * 1000))

            user_lm = None
            if (user_engine.latest_result
                    and user_engine.latest_result.pose_landmarks):
                user_lm = user_engine.latest_result.pose_landmarks[0]

            # ── Coach evaluation ──────────────────────────────────────────
            correct, message, should_pause, hold_remaining = controller.update(
                local_pos, user_lm, w, h
            )
            coach_state = controller.coach_state
            ap          = controller._active_phase
            watch_msg   = ap.get("watch_msg", "") if ap else ""
            rep_target  = ap.get("target", 0)    if ap else 0
            rep_done    = controller.rep_count

            # Track current phase index for navigator
            if ap:
                for i, p in enumerate(phases):
                    if p["id"] == ap["id"]:
                        current_phase_idx = i
                        break

            # ── Video pause control ───────────────────────────────────────
            if manual_paused:
                ref_video.pause()
            elif should_pause:
                ref_video.pause()
            else:
                ref_video.resume()

            # ── Read reference frame ──────────────────────────────────────
            ref_frame = cv2.resize(ref_video.read(), (w, h))

            # ── Draw user frame ───────────────────────────────────────────
            cam_frame = user_engine.draw_skeleton(cam_frame, correct)

            # Phase selector strip at bottom of user frame
            draw_phase_selector(cam_frame, phases, ap, local_pos)
            draw_controls_hint(cam_frame)

            # State pill on user frame top-left
            sc = {"WATCH": _YELLOW, "PREPARE": _CYAN, "ACTIVE": _GREEN,
                  "HOLD": _ORANGE, "ZOOM": _GREY}.get(coach_state, _WHITE)
            _pill(cam_frame, coach_state, 10, 34, _DARK, sc, 0.65, 2)

            # Debug panel
            if show_debug:
                draw_debug_panel(cam_frame, controller, local_pos, user_lm, w, h)

            # Manual pause indicator
            if manual_paused:
                cv2.putText(cam_frame, "PAUSED [SPACE]",
                            (10, h - 55), FONT, 0.55, _YELLOW, 2, cv2.LINE_AA)

            # ── Draw reference frame ──────────────────────────────────────
            render_test_frame(ref_frame, coach_state, watch_msg,
                              rep_done, rep_target, correct,
                              message, hold_remaining)

            # Timestamp on ref frame
            draw_timestamp(ref_frame, video_pos)

            # Phase name banner on ref frame (top centre)
            phase_label = ap.get("name", args.exercise.upper()) if ap else args.exercise.upper()
            ts = cv2.getTextSize(phase_label, FONT, 0.70, 2)[0]
            cx = (w - ts[0]) // 2
            cv2.putText(ref_frame, phase_label, (cx, 34),
                        FONT, 0.70, _WHITE, 2, cv2.LINE_AA)

            # ── Combine and display ───────────────────────────────────────
            combined = cv2.hconcat([cam_frame, ref_frame])
            cv2.imshow(f"SKY Pose Test — {args.exercise}", combined)

            # ── Key handling ──────────────────────────────────────────────
            key = cv2.waitKey(1) & 0xFF

            if key in (ord("q"), 27):          # Q or ESC
                break

            elif key == ord(" "):              # pause / resume
                manual_paused = not manual_paused
                if manual_paused:
                    ref_video.pause()
                    print(f"  ⏸ Paused at {video_pos:.1f}s")
                else:
                    ref_video.resume()
                    print(f"  ▶ Resumed")

            elif key == ord("n"):              # next phase
                next_idx = min(current_phase_idx + 1, len(phases) - 1)
                if next_idx != current_phase_idx:
                    current_phase_idx = next_idx
                    seek_to_phase(ref_video, controller, phases[current_phase_idx])
                    manual_paused = False
                    print(f"  → Phase: {phases[current_phase_idx]['id']}")

            elif key == ord("p"):              # prev phase
                prev_idx = max(current_phase_idx - 1, 0)
                if prev_idx != current_phase_idx:
                    current_phase_idx = prev_idx
                    seek_to_phase(ref_video, controller, phases[current_phase_idx])
                    manual_paused = False
                    print(f"  → Phase: {phases[current_phase_idx]['id']}")

            elif key == ord("r"):              # reset reps
                controller.reset_session()
                controller._active_phase = phases[current_phase_idx]
                print(f"  ↺ Reset — phase: {phases[current_phase_idx]['id']}")

            elif key in (ord("+"), ord("=")):  # seek forward
                target = ref_video.position_seconds() + 5.0
                ref_video.seek(target)
                print(f"  → Seeked to {target:.1f}s")

            elif key == ord("-"):              # seek backward
                target = max(0.0, ref_video.position_seconds() - 5.0)
                ref_video.seek(target)
                print(f"  → Seeked to {target:.1f}s")

            elif key == ord("d"):              # toggle debug
                show_debug = not show_debug
                print(f"  Debug overlay: {'ON' if show_debug else 'OFF'}")

    finally:
        camera.release()
        ref_video.release()
        cv2.destroyAllWindows()

        # ── Session summary ───────────────────────────────────────────────
        ap = controller._active_phase
        print("\n" + "=" * 60)
        print("SESSION SUMMARY")
        print("=" * 60)
        print(f"  Exercise    : {args.exercise}")
        print(f"  Last phase  : {ap['id'] if ap else 'none'}")
        print(f"  Reps done   : {controller.rep_count}")
        if ap:
            print(f"  Target reps : {ap.get('target', 0)}")
            pct = controller.rep_count / max(ap.get("target", 1), 1) * 100
            print(f"  Completion  : {pct:.0f}%")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    main()