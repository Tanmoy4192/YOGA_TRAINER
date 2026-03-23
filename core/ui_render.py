"""
core/ui_render.py — UI rendering for video frames

Displays:
  - Phase banner (top): coach state + phase name
  - Coach message (bottom): feedback with color (green/red) and word wrap
  - Rep counter (top-left): large "X / Y" with progress bar
  - Hold overlay (center): pulsing orange banner during HOLD state
  - Countdown/intro (full-screen): setup screens

Color scheme:
  WATCH   → yellow (mentor is showing)
  PREPARE → cyan (get ready soon)
  ACTIVE  → green (user is evaluating)
  ZOOM    → grey (zoom in, just watch)
  HOLD    → orange (pause, complete reps)
"""
import cv2
import time

# ─────────────────────────────────────────────────────────────────────────────
# COLOR PALETTE (OpenCV uses BGR)
# ─────────────────────────────────────────────────────────────────────────────

_GREEN = (60, 220, 80)
_RED = (50, 50, 220)
_YELLOW = (0, 200, 255)
_CYAN = (220, 200, 0)
_ORANGE = (0, 140, 255)
_WHITE = (240, 240, 240)
_GREY = (140, 140, 140)
_BLACK = (0, 0, 0)
_DARK = (18, 18, 18)

# State color mapping
_STATE_COLOR = {
    "WATCH": _YELLOW,
    "PREPARE": _CYAN,
    "ACTIVE": _GREEN,
    "ZOOM": _GREY,
    "HOLD": _ORANGE,
}


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────


def _put_centered(frame, text: str, y: int, font, scale: float, color, thick: int):
    """Draw text centered horizontally at given y position."""
    _, w, _ = frame.shape[0], frame.shape[1], frame.shape[2]
    ts = cv2.getTextSize(text, font, scale, thick)[0]
    x = (w - ts[0]) // 2
    cv2.putText(frame, text, (x, y), font, scale, color, thick, cv2.LINE_AA)


def _wrap_text(text: str, frame_w: int, font, scale: float, thick: int,
               max_w_ratio: float = 0.88) -> list:
    """
    Split text into lines that fit within frame_w * max_w_ratio.
    Returns list of line strings.
    """
    max_px = int(frame_w * max_w_ratio)
    words = text.split()
    lines = []
    line = ""

    for word in words:
        test = (line + " " + word).strip()
        if cv2.getTextSize(test, font, scale, thick)[0][0] <= max_px:
            line = test
        else:
            if line:
                lines.append(line)
            line = word

    if line:
        lines.append(line)

    return lines


# ─────────────────────────────────────────────────────────────────────────────
# MAIN UI FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────


def draw_phase_banner(frame, phase_name: str, coach_state: str):
    """
    Draw top banner showing coach state and phase name.

    Layout:
      LEFT:   state pill (WATCH / PREPARE / ACTIVE / ZOOM / HOLD)
      CENTER: phase name
    """
    h, w, _ = frame.shape
    FONT = cv2.FONT_HERSHEY_SIMPLEX
    BAR_HEIGHT = 52

    # Dark overlay background
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, BAR_HEIGHT), _DARK, -1)
    cv2.addWeighted(overlay, 0.80, frame, 0.20, 0, frame)

    # Accent line (color by state)
    sc = _STATE_COLOR.get(coach_state, _WHITE)
    cv2.line(frame, (0, BAR_HEIGHT), (w, BAR_HEIGHT), sc, 2)

    # State pill — left side
    cv2.putText(frame, coach_state, (14, 34), FONT, 0.65, sc, 2, cv2.LINE_AA)

    # Phase name — centered
    ts = cv2.getTextSize(phase_name, FONT, 0.85, 2)[0]
    cv2.putText(
        frame,
        phase_name,
        ((w - ts[0]) // 2, 34),
        FONT,
        0.85,
        _WHITE,
        2,
        cv2.LINE_AA,
    )


def draw_rep_counter(frame, done: int, target: int):
    """
    Draw large rep counter in top-left.
    Shows "X / Y" with progress bar underneath.
    """
    h, w, _ = frame.shape
    FONT = cv2.FONT_HERSHEY_SIMPLEX
    Y = 110

    # Color: green if working, cyan if complete
    color = _GREEN if done < target else _CYAN
    text = f"{done} / {target}"

    # Large number
    ts = cv2.getTextSize(text, FONT, 2.0, 4)[0]
    cv2.putText(frame, text, (24, Y), FONT, 2.0, color, 4, cv2.LINE_AA)

    # Label below
    cv2.putText(frame, "REPS", (28, Y + 28), FONT, 0.55, _GREY, 1, cv2.LINE_AA)

    # Progress bar
    bar_x, bar_y = 24, Y + 44
    bar_w = int(ts[0])
    bar_h = 6

    # Background
    cv2.rectangle(
        frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (60, 60, 60), -1
    )

    # Filled portion
    if target > 0:
        fill = int(bar_w * min(done, target) / target)
        cv2.rectangle(
            frame, (bar_x, bar_y), (bar_x + fill, bar_y + bar_h), color, -1
        )


def draw_coach_message(frame, message: str, correct: bool):
    """
    Draw coach message in bottom bar with color coding.

    Green background if correct form, red if error.
    Message wraps to fit frame width.
    """
    if not message:
        return

    h, w, _ = frame.shape
    FONT = cv2.FONT_HERSHEY_SIMPLEX
    SCALE = 0.80
    THICK = 2
    BAR_H = 90

    # Choose colors
    if correct:
        bg_color = (0, 60, 0)
        txt_color = (120, 255, 120)
    else:
        bg_color = (0, 0, 80)
        txt_color = (100, 100, 255)

    # Background bar
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, h - BAR_H), (w, h), bg_color, -1)
    cv2.addWeighted(overlay, 0.70, frame, 0.30, 0, frame)

    # Top accent line
    cv2.line(
        frame, (0, h - BAR_H), (w, h - BAR_H), txt_color, 2
    )

    # Wrap and draw text
    lines = _wrap_text(message, w, FONT, SCALE, THICK)
    total_h = len(lines) * 34
    y = h - BAR_H + (BAR_H - total_h) // 2 + 24

    for ln in lines[:2]:  # max 2 lines
        ts = cv2.getTextSize(ln, FONT, SCALE, THICK)[0]
        cv2.putText(
            frame, ln, ((w - ts[0]) // 2, y), FONT, SCALE, txt_color, THICK, cv2.LINE_AA
        )
        y += 34


def draw_hold_overlay(frame, message: str):
    """
    Draw pulsing orange banner during HOLD state.
    Indicates user must complete reps before video resumes.

    Pulse effect: alpha = 0.55 + 0.15 * abs((time % 1.0) - 0.5)
    """
    h, w, _ = frame.shape
    FONT = cv2.FONT_HERSHEY_SIMPLEX

    # Pulsing alpha
    pulse = abs((time.time() % 1.0) - 0.5) * 2  # 0 to 1 to 0 over 1 sec
    alpha = 0.55 + pulse * 0.15

    # Banner overlay in center
    banner_h = 120
    y_start = (h - banner_h) // 2
    y_end = y_start + banner_h

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, y_start), (w, y_end), _ORANGE, -1)
    cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0, frame)

    # Draw message in center
    lines = _wrap_text(message, w, FONT, 0.90, 2)
    total_h = len(lines) * 36
    y = y_start + (banner_h - total_h) // 2 + 28

    for ln in lines[:2]:
        ts = cv2.getTextSize(ln, FONT, 0.90, 2)[0]
        cv2.putText(
            frame,
            ln,
            ((w - ts[0]) // 2, y),
            FONT,
            0.90,
            _WHITE,
            2,
            cv2.LINE_AA,
        )
        y += 36


def draw_countdown(frame, seconds: int):
    """
    Draw full-screen countdown overlay.
    Used during startup countdown (e.g., "3... 2... 1...")
    """
    h, w, _ = frame.shape
    FONT = cv2.FONT_HERSHEY_SIMPLEX

    # Dark overlay
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, h), _BLACK, -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

    # "Get ready" text
    _put_centered(frame, "Get ready", h // 2 - 70, FONT, 1.4, _WHITE, 2)

    # Countdown number (large)
    _put_centered(frame, str(seconds), h // 2 + 50, FONT, 4.0, _CYAN, 6)


def draw_intro(frame, title: str):
    """
    Draw full-screen intro overlay.
    Explains how the system works.
    """
    h, w, _ = frame.shape
    FONT = cv2.FONT_HERSHEY_SIMPLEX

    # Dark overlay
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, h), _BLACK, -1)
    cv2.addWeighted(overlay, 0.72, frame, 0.28, 0, frame)

    # Text lines
    lines = [
        title,
        "",
        "Your camera is tracking your pose.",
        "Follow the mentor in the video.",
        "The video pauses if your form needs correction.",
    ]

    y = h // 2 - 100
    for i, ln in enumerate(lines):
        sc = 1.1 if i == 0 else 0.75
        col = _CYAN if i == 0 else _GREY
        th = 2 if i == 0 else 1
        _put_centered(frame, ln, y, FONT, sc, col, th)
        y += 52 if i == 0 else 38