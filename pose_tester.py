"""
pose_tester.py — SKY Yoga AI Coach · Exercise Tester

Run and test a specific exercise WITHOUT the full video stream.
Identical UI output to main.py (same render pipeline, same skeleton,
same rep counter, same coach messages, same HOLD overlay).

Usage:
    python pose_tester.py                    # interactive menu — pick exercise
    python pose_tester.py hand               # jump straight to hand exercise
    python pose_tester.py hand p10_knee_cw   # jump to a specific phase

Controls:
    [SPACE]     — pause / resume the simulated video clock
    [N]         — skip to next phase
    [P]         — go back to previous phase
    [R]         — reset current phase (rep count + state)
    [Q] / [ESC] — quit

How the fake video clock works:
    There is no reference video file needed.
    A wall-clock timer drives `video_pos` exactly as ReferenceVideo.position_seconds()
    does in production.  The controller receives the same (video_pos, landmarks, w, h)
    tuple every frame, so all state-machine logic runs identically.

    The tester starts the clock at the 'active' timestamp of the first phase so
    you are immediately in ACTIVE state.  Press [N]/[P] to walk through phases.

Layout:
    Same 50/50 split as main.py.
    LEFT  — user camera feed with skeleton, FPS, rep counter, coach message.
    RIGHT — plain dark panel showing:
              • Phase name
              • Phase timeline bar (watch → prepare → active → end)
              • All phases listed with current highlighted
              • "No video needed" notice
"""

import os
import sys
import cv2
import time
import mediapipe as mp

from core.camera            import Camera
from core.pose_engine       import PoseEngine
from core.exercise_registry import ExerciseRegistry
from core.ui_render         import render_user_frame

# ─────────────────────────────────────────────────────────────────────────────
# COLORS  (BGR)
# ─────────────────────────────────────────────────────────────────────────────

_DARK    = (18,  18,  18)
_WHITE   = (240, 240, 240)
_GREY    = (120, 120, 120)
_CYAN    = (220, 200,   0)
_GREEN   = ( 60, 220,  80)
_YELLOW  = (  0, 200, 255)
_ORANGE  = (  0, 140, 255)

_STATE_COLOR = {
    "WATCH":   _YELLOW,
    "PREPARE": _CYAN,
    "ACTIVE":  _GREEN,
    "ZOOM":    _GREY,
    "HOLD":    _ORANGE,
}

FONT = cv2.FONT_HERSHEY_SIMPLEX


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _put(frame, text, x, y, scale=0.60, color=_WHITE, thick=1):
    cv2.putText(frame, text, (x, y), FONT, scale, color, thick, cv2.LINE_AA)


def _put_centered(frame, text, y, scale=0.65, color=_WHITE, thick=1):
    w = frame.shape[1]
    ts = cv2.getTextSize(text, FONT, scale, thick)[0]
    cv2.putText(frame, text, ((w - ts[0]) // 2, y),
                FONT, scale, color, thick, cv2.LINE_AA)


def _pill(frame, text, x, y, fg, scale=0.52, thick=1):
    ts  = cv2.getTextSize(text, FONT, scale, thick)[0]
    pad = 5
    cv2.rectangle(frame,
                  (x - pad, y - ts[1] - pad),
                  (x + ts[0] + pad, y + pad), fg, -1)
    cv2.putText(frame, text, (x, y), FONT, scale, _DARK, thick, cv2.LINE_AA)


def _dark_panel(w, h):
    import numpy as np
    return np.zeros((h, w, 3), dtype="uint8")


# ─────────────────────────────────────────────────────────────────────────────
# INFO PANEL  (right side — replaces reference video)
# ─────────────────────────────────────────────────────────────────────────────

def _draw_info_panel(panel, exercise_key, phases, phase_idx,
                     video_pos, coach_state, rep_done, rep_target):
    """
    Draw the right-hand info panel.

    Sections:
      1. Exercise key badge + coach state pill  (top)
      2. Current phase name
      3. Phase timeline bar  (WATCH region | ACTIVE region, with cursor)
      4. All phases list, current highlighted
      5. Rep progress bar  (bottom)
      6. Keyboard shortcuts  (very bottom)
    """
    h, w = panel.shape[:2]
    panel[:] = _DARK

    # accent line at very top
    sc = _STATE_COLOR.get(coach_state, _WHITE)
    cv2.line(panel, (0, 0), (w, 0), sc, 3)

    y = 30
    # ── 1. exercise key + state ───────────────────────────────────────────
    _pill(panel, exercise_key.upper(), 14, y, sc, scale=0.68, thick=2)
    state_ts = cv2.getTextSize(coach_state, FONT, 0.58, 1)[0]
    _put(panel, coach_state, w - state_ts[0] - 14, y, 0.58, sc, 1)

    y += 20
    cv2.line(panel, (0, y), (w, y), (40, 40, 40), 1)

    # ── 2. current phase name ─────────────────────────────────────────────
    y += 26
    phase = phases[phase_idx] if phases else None
    if phase:
        name = phase.get("name", phase.get("id", "—"))
        _put_centered(panel, name, y, scale=0.68, color=_WHITE, thick=2)

    # video clock readout
    y += 24
    _put_centered(panel, f"clock  {video_pos:.1f}s", y, scale=0.48, color=_GREY)

    # ── 3. phase timeline bar ─────────────────────────────────────────────
    y += 22
    if phase:
        p_start  = phase.get("start",  0)
        p_active = phase.get("active", p_start)
        p_end    = phase.get("end",    p_active + 30)
        duration = max(p_end - p_start, 1)

        BAR_X = 20
        BAR_W = w - 40
        BAR_H = 16

        # background track
        cv2.rectangle(panel, (BAR_X, y),
                      (BAR_X + BAR_W, y + BAR_H), (40, 40, 40), -1)

        # WATCH region (start → active)
        watch_w = int(BAR_W * (p_active - p_start) / duration)
        if watch_w > 0:
            cv2.rectangle(panel, (BAR_X, y),
                          (BAR_X + watch_w, y + BAR_H), _YELLOW, -1)

        # ACTIVE region (active → end)
        active_x = BAR_X + watch_w
        active_w = BAR_W - watch_w
        if active_w > 0:
            cv2.rectangle(panel, (active_x, y),
                          (active_x + active_w, y + BAR_H), _GREEN, -1)

        # cursor (current position)
        clamped = max(p_start, min(video_pos, p_end))
        cur_x   = BAR_X + int(BAR_W * (clamped - p_start) / duration)
        cv2.line(panel, (cur_x, y - 5), (cur_x, y + BAR_H + 5), _WHITE, 3)

        y += BAR_H + 16
        _put(panel, "WATCH", BAR_X, y, 0.42, _YELLOW)
        al_ts = cv2.getTextSize("ACTIVE", FONT, 0.42, 1)[0]
        _put(panel, "ACTIVE", BAR_X + BAR_W - al_ts[0], y, 0.42, _GREEN)

    # ── 4. phase list ─────────────────────────────────────────────────────
    y += 22
    cv2.line(panel, (0, y), (w, y), (40, 40, 40), 1)
    y += 14
    _put(panel, "PHASES", 14, y, 0.46, _GREY)
    y += 20

    max_visible = 10
    start_i = max(0, phase_idx - max_visible // 2)
    end_i   = min(len(phases), start_i + max_visible)

    for i in range(start_i, end_i):
        p          = phases[i]
        is_current = (i == phase_idx)
        label      = f"  {p.get('name', p.get('id', '?'))}"

        # truncate label if it would overflow
        while cv2.getTextSize(label, FONT, 0.50, 1)[0][0] > w - 28 and len(label) > 5:
            label = label[:-2]

        row_color = sc    if is_current else _GREY
        row_thick = 2     if is_current else 1

        if is_current:
            cv2.rectangle(panel, (0, y - 15), (w, y + 7), (30, 30, 30), -1)
            # left accent bar for selected row
            cv2.line(panel, (0, y - 15), (0, y + 7), sc, 5)

        _put(panel, label, 14, y, 0.50, row_color, row_thick)
        y += 23
        if y > h - 90:
            break

    # ── 5. rep progress (bottom section) ─────────────────────────────────
    if rep_target > 0:
        y = h - 78
        cv2.line(panel, (0, y), (w, y), (40, 40, 40), 1)
        y += 22
        rep_txt = f"REPS  {rep_done} / {rep_target}"
        col = _GREEN if rep_done < rep_target else _CYAN
        _put_centered(panel, rep_txt, y, scale=0.72, color=col, thick=2)

        # bar
        BAR_X2, BAR_W2, BAR_H2 = 20, w - 40, 8
        y += 14
        cv2.rectangle(panel, (BAR_X2, y),
                      (BAR_X2 + BAR_W2, y + BAR_H2), (40, 40, 40), -1)
        fill = int(BAR_W2 * min(rep_done, rep_target) / rep_target)
        cv2.rectangle(panel, (BAR_X2, y),
                      (BAR_X2 + fill, y + BAR_H2), col, -1)

    # ── 6. keyboard shortcuts ──────────────────────────────────────────────
    shortcuts = "[N] next  [P] prev  [R] reset  [SPACE] pause  [Q] quit"
    ts = cv2.getTextSize(shortcuts, FONT, 0.37, 1)[0]
    _put(panel, shortcuts, (w - ts[0]) // 2, h - 14, 0.37, (65, 65, 65))


# ─────────────────────────────────────────────────────────────────────────────
# FAKE VIDEO CLOCK
# ─────────────────────────────────────────────────────────────────────────────

class FakeClock:
    """
    Simulates ReferenceVideo.position_seconds() without any video file.
    Starts at a given position and advances with wall time.
    Supports pause / resume identical to ReferenceVideo.
    """

    def __init__(self, start_pos: float = 0.0):
        self._pos    = start_pos
        self._paused = False
        self._wall   = time.time()

    def position_seconds(self) -> float:
        if self._paused:
            return self._pos
        return self._pos + (time.time() - self._wall)

    def seek(self, pos: float):
        self._pos  = pos
        self._wall = time.time()

    def pause(self):
        if not self._paused:
            self._pos    = self.position_seconds()
            self._paused = True

    def resume(self):
        if self._paused:
            self._wall   = time.time()
            self._paused = False

    @property
    def paused(self) -> bool:
        return self._paused


# ─────────────────────────────────────────────────────────────────────────────
# INTERACTIVE MENU
# ─────────────────────────────────────────────────────────────────────────────

def _pick_exercise(registry) -> str:
    keys = registry.keys()
    print("\n" + "=" * 50)
    print("  SKY Yoga — Exercise Tester")
    print("=" * 50)
    for i, k in enumerate(keys, 1):
        print(f"  [{i}]  {k}")
    print("=" * 50)
    while True:
        raw = input("Pick exercise (number or key): ").strip().lower()
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(keys):
                return keys[idx]
        elif raw in keys:
            return raw
        print("  Invalid — try again.")


def _pick_phase(phases: list, hint: str = "") -> int:
    """Return phase index matching hint string, or 0."""
    if not hint:
        return 0
    h = hint.lower()
    for i, p in enumerate(phases):
        if h in p.get("id", "").lower() or h in p.get("name", "").lower():
            return i
    return 0


def _phase_clock_start(phase: dict) -> float:
    """Start clock just before active time so PREPARE briefly shows."""
    return max(phase["start"], phase.get("active", phase["start"]) - 3.0)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    args          = sys.argv[1:]
    exercise_hint = args[0].lower() if len(args) >= 1 else ""
    phase_hint    = args[1].lower() if len(args) >= 2 else ""

    print("\n" + "=" * 60)
    print("  SKY Yoga AI Coach — Pose Tester")
    print("=" * 60)
    print("  [N] next phase  [P] prev phase  [R] reset")
    print("  [SPACE] pause/resume  [Q / ESC] quit")
    print("=" * 60 + "\n")

    # ── load registry ──────────────────────────────────────────────────────
    registry = ExerciseRegistry()
    if not registry.keys():
        print("ERROR: No exercises loaded. Check exercises/ folder.")
        sys.exit(1)

    # ── choose exercise ────────────────────────────────────────────────────
    if exercise_hint and exercise_hint in registry.keys():
        exercise_key = exercise_hint
    else:
        exercise_key = _pick_exercise(registry)

    controller = registry.get(exercise_key)
    phases     = controller.phases()
    if not phases:
        print(f"ERROR: '{exercise_key}' has no phases defined.")
        sys.exit(1)

    # ── choose starting phase ──────────────────────────────────────────────
    phase_idx = _pick_phase(phases, phase_hint)
    print(f"Exercise : {exercise_key}")
    print(f"Start    : {phases[phase_idx].get('name', phases[phase_idx]['id'])}")
    print(f"Total    : {len(phases)} phases\n")

    # ── hardware setup ─────────────────────────────────────────────────────
    camera      = Camera(0)
    user_engine = PoseEngine("pose_landmarker_heavy.task")

    # ── fake clock ────────────────────────────────────────────────────────
    clock = FakeClock(start_pos=_phase_clock_start(phases[phase_idx]))
    controller.reset_session()

    _manual_paused = False

    try:
        while True:
            # ── camera frame ───────────────────────────────────────────────
            frame   = camera.read()
            h, w, _ = frame.shape

            # ── clock ──────────────────────────────────────────────────────
            if _manual_paused:
                clock.pause()
            video_pos = clock.position_seconds()

            # ── pose detection ─────────────────────────────────────────────
            rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            user_engine.detect_async(mp_img, int(time.time() * 1000))

            user_lm = None
            if (user_engine.latest_result
                    and user_engine.latest_result.pose_landmarks):
                user_lm = user_engine.latest_result.pose_landmarks[0]

            # ── coach evaluation ───────────────────────────────────────────
            correct, message, should_pause, hold_remaining = controller.update(
                video_pos, user_lm, w, h
            )
            coach_state = controller.coach_state
            ap          = controller._active_phase
            watch_msg   = ap.get("watch_msg", "") if ap else ""
            target_reps = ap.get("target", 0)     if ap else 0
            rep_done    = controller.rep_count

            # ── clock pause logic ──────────────────────────────────────────
            if _manual_paused or should_pause:
                clock.pause()
            else:
                clock.resume()

            # ── auto-advance to next phase when clock passes phase end ─────
            current_phase = phases[phase_idx]
            phase_end     = current_phase.get("end", float("inf"))
            if video_pos >= phase_end and phase_idx < len(phases) - 1:
                phase_idx += 1
                controller.reset_session()
                clock.seek(_phase_clock_start(phases[phase_idx]))
                print(f"→ Auto: {phases[phase_idx].get('name', phases[phase_idx]['id'])}")

            # ── draw user frame ────────────────────────────────────────────
            frame = user_engine.draw_skeleton(frame, correct)

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

            # paused badge on user frame (top-right, consistent with main.py)
            if _manual_paused:
                ts  = cv2.getTextSize("PAUSED", FONT, 0.62, 2)[0]
                cv2.putText(frame, "PAUSED", (w - ts[0] - 14, 28),
                            FONT, 0.62, _ORANGE, 2, cv2.LINE_AA)

            # ── info panel ────────────────────────────────────────────────
            panel = _dark_panel(w, h)
            _draw_info_panel(
                panel,
                exercise_key = exercise_key,
                phases       = phases,
                phase_idx    = phase_idx,
                video_pos    = video_pos,
                coach_state  = coach_state,
                rep_done     = rep_done,
                rep_target   = target_reps,
            )

            # ── display ────────────────────────────────────────────────────
            cv2.imshow("SKY Yoga — Tester", cv2.hconcat([frame, panel]))

            # ── keys ───────────────────────────────────────────────────────
            key = cv2.waitKey(1) & 0xFF

            if key in (ord("q"), 27):                   # Q / ESC
                break

            elif key == ord(" "):                        # SPACE
                _manual_paused = not _manual_paused
                if _manual_paused:
                    clock.pause()
                    print("⏸ Paused")
                else:
                    clock.resume()
                    print("▶ Resumed")

            elif key == ord("n"):                        # N — next phase
                if phase_idx < len(phases) - 1:
                    phase_idx += 1
                    controller.reset_session()
                    clock.seek(_phase_clock_start(phases[phase_idx]))
                    print(f"→ {phases[phase_idx].get('name', phases[phase_idx]['id'])}")
                else:
                    print("  Already at last phase.")

            elif key == ord("p"):                        # P — previous phase
                if phase_idx > 0:
                    phase_idx -= 1
                    controller.reset_session()
                    clock.seek(_phase_clock_start(phases[phase_idx]))
                    print(f"← {phases[phase_idx].get('name', phases[phase_idx]['id'])}")
                else:
                    print("  Already at first phase.")

            elif key == ord("r"):                        # R — reset
                controller.reset_session()
                clock.seek(_phase_clock_start(phases[phase_idx]))
                print(f"↺ Reset: {phases[phase_idx].get('name', phases[phase_idx]['id'])}")

    finally:
        camera.release()
        cv2.destroyAllWindows()
        print("\n✓ Tester closed.\n")


if __name__ == "__main__":
    main()