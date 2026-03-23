"""
core/ui_render.py — UI rendering for video frames

Displays:
  - Phase banner (top): coach state ONLY (no exercise name)
  - FPS counter (top-left corner): live frames-per-second
  - Coach message (bottom): feedback with color (green/red) and word wrap
  - Rep counter: large "X / Y" with progress bar
  - Hold overlay (center): frozen frame + pulsing orange banner + countdown
  - "Watch Carefully" overlay: shown from phase start → active time
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

_GREEN  = (60, 220, 80)
_RED    = (50, 50, 220)
_YELLOW = (0, 200, 255)
_CYAN   = (220, 200, 0)
_ORANGE = (0, 140, 255)
_WHITE  = (240, 240, 240)
_GREY   = (140, 140, 140)
_BLACK  = (0, 0, 0)
_DARK   = (18, 18, 18)

# State → accent color
_STATE_COLOR = {
    "WATCH":   _YELLOW,
    "PREPARE": _CYAN,
    "ACTIVE":  _GREEN,
    "ZOOM":    _GREY,
    "HOLD":    _ORANGE,
}

# ─────────────────────────────────────────────────────────────────────────────
# FPS TRACKER  (internal, stateful)
# ─────────────────────────────────────────────────────────────────────────────

class _FPSTracker:
    """Rolling-window FPS calculator."""
    def __init__(self, window: int = 30):
        self._times: list = []
        self._window = window

    def tick(self) -> float:
        now = time.time()
        self._times.append(now)
        if len(self._times) > self._window:
            self._times.pop(0)
        if len(self._times) < 2:
            return 0.0
        span = self._times[-1] - self._times[0]
        return (len(self._times) - 1) / span if span > 0 else 0.0


_fps_tracker = _FPSTracker()


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────


def _put_centered(frame, text: str, y: int, font, scale: float, color, thick: int):
    """Draw text centered horizontally at given y."""
    w = frame.shape[1]
    ts = cv2.getTextSize(text, font, scale, thick)[0]
    x = (w - ts[0]) // 2
    cv2.putText(frame, text, (x, y), font, scale, color, thick, cv2.LINE_AA)


def _wrap_text(text: str, frame_w: int, font, scale: float, thick: int,
               max_w_ratio: float = 0.88) -> list:
    """Split text into lines that fit within frame_w * max_w_ratio."""
    max_px = int(frame_w * max_w_ratio)
    words   = text.split()
    lines   = []
    line    = ""
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
# FPS OVERLAY  (top-left)
# ─────────────────────────────────────────────────────────────────────────────


def draw_fps(frame):
    """
    Tick the FPS tracker and draw current FPS in the top-left corner.
    Call this once per frame, AFTER draw_phase_banner so the banner
    background does not cover it.
    """
    fps  = _fps_tracker.tick()
    FONT = cv2.FONT_HERSHEY_SIMPLEX

    label = f"FPS: {fps:.1f}"

    # Tiny dark pill background so it's readable over any frame
    ts   = cv2.getTextSize(label, FONT, 0.55, 1)[0]
    pad  = 4
    x0, y0 = 10, 8
    cv2.rectangle(
        frame,
        (x0 - pad, y0 - pad),
        (x0 + ts[0] + pad, y0 + ts[1] + pad),
        _DARK, -1
    )
    cv2.putText(frame, label, (x0, y0 + ts[1]),
                FONT, 0.55, _GREY, 1, cv2.LINE_AA)


# ─────────────────────────────────────────────────────────────────────────────
# PHASE BANNER  (top strip — state pill ONLY, no exercise name)
# ─────────────────────────────────────────────────────────────────────────────


def draw_phase_banner(frame, coach_state: str):
    """
    Draw top banner showing coach state pill only.
    Exercise name has been removed per design update.

    Layout:
      LEFT: state pill (WATCH / PREPARE / ACTIVE / ZOOM / HOLD)
    """
    h, w = frame.shape[:2]
    FONT       = cv2.FONT_HERSHEY_SIMPLEX
    BAR_HEIGHT = 52

    # Dark semi-transparent background
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, BAR_HEIGHT), _DARK, -1)
    cv2.addWeighted(overlay, 0.80, frame, 0.20, 0, frame)

    # Accent line coloured by state
    sc = _STATE_COLOR.get(coach_state, _WHITE)
    cv2.line(frame, (0, BAR_HEIGHT), (w, BAR_HEIGHT), sc, 2)

    # State pill — left side
    cv2.putText(frame, coach_state, (14, 34),
                FONT, 0.65, sc, 2, cv2.LINE_AA)


# ─────────────────────────────────────────────────────────────────────────────
# WATCH-CAREFULLY OVERLAY  (start → active phase)
# ─────────────────────────────────────────────────────────────────────────────


def draw_watch_carefully(frame, watch_msg: str = ""):
    """
    Shown during WATCH and PREPARE states (phase start → active time).
    Draws a translucent yellow banner with "WATCH CAREFULLY" and
    the phase-specific watch_msg below it.
    """
    h, w = frame.shape[:2]
    FONT = cv2.FONT_HERSHEY_SIMPLEX

    # Pulsing alpha (subtle)
    pulse = abs((time.time() % 1.2) - 0.6) / 0.6   # 0 → 1 → 0 over 1.2s
    alpha = 0.45 + pulse * 0.20

    BANNER_H = 110
    y_start  = 60   # just below the top bar
    y_end    = y_start + BANNER_H

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, y_start), (w, y_end), (0, 100, 180), -1)
    cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0, frame)

    # Top accent line
    cv2.line(frame, (0, y_start), (w, y_start), _YELLOW, 2)

    # "WATCH CAREFULLY" header
    _put_centered(frame, " WATCH CAREFULLY", y_start + 36,
                  FONT, 0.90, _YELLOW, 2)

    # Phase-specific hint below
    if watch_msg:
        lines = _wrap_text(watch_msg, w, FONT, 0.62, 1)
        y = y_start + 68
        for ln in lines[:2]:
            ts = cv2.getTextSize(ln, FONT, 0.62, 1)[0]
            cv2.putText(frame, ln, ((w - ts[0]) // 2, y),
                        FONT, 0.62, _WHITE, 1, cv2.LINE_AA)
            y += 28


# ─────────────────────────────────────────────────────────────────────────────
# REP COUNTER  (positioned below FPS, left side)
# ─────────────────────────────────────────────────────────────────────────────


def draw_rep_counter(frame, done: int, target: int, watch_active: bool = False):
    """
    Draw large rep counter.
    Moves below the Watch Carefully banner when that overlay is visible
    to prevent overlap.
    Shows "X / Y" with progress bar underneath.
    """
    h, w = frame.shape[:2]
    FONT = cv2.FONT_HERSHEY_SIMPLEX
    # Watch banner occupies y=60..170, rep counter must clear it
    Y = 220 if watch_active else 130

    color = _GREEN if done < target else _CYAN
    text  = f"{done} / {target}"

    ts = cv2.getTextSize(text, FONT, 2.0, 4)[0]
    cv2.putText(frame, text, (24, Y), FONT, 2.0, color, 4, cv2.LINE_AA)

    cv2.putText(frame, "REPS", (28, Y + 28),
                FONT, 0.55, _GREY, 1, cv2.LINE_AA)

    # Progress bar
    bar_x, bar_y = 24, Y + 44
    bar_w = int(ts[0])
    bar_h = 6

    cv2.rectangle(frame,
                  (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h),
                  (60, 60, 60), -1)

    if target > 0:
        fill = int(bar_w * min(done, target) / target)
        cv2.rectangle(frame,
                      (bar_x, bar_y), (bar_x + fill, bar_y + bar_h),
                      color, -1)


# ─────────────────────────────────────────────────────────────────────────────
# COACH MESSAGE  (bottom bar)
# ─────────────────────────────────────────────────────────────────────────────


def draw_coach_message(frame, message: str, correct: bool):
    """
    Draw coach message in bottom bar with colour coding.
    Green background if correct form, red if error.
    """
    if not message:
        return

    h, w = frame.shape[:2]
    FONT  = cv2.FONT_HERSHEY_SIMPLEX
    SCALE = 0.80
    THICK = 2
    BAR_H = 90

    if correct:
        bg_color  = (0, 60, 0)
        txt_color = (120, 255, 120)
    else:
        bg_color  = (0, 0, 80)
        txt_color = (100, 100, 255)

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, h - BAR_H), (w, h), bg_color, -1)
    cv2.addWeighted(overlay, 0.70, frame, 0.30, 0, frame)

    cv2.line(frame, (0, h - BAR_H), (w, h - BAR_H), txt_color, 2)

    lines   = _wrap_text(message, w, FONT, SCALE, THICK)
    total_h = len(lines) * 34
    y       = h - BAR_H + (BAR_H - total_h) // 2 + 24

    for ln in lines[:2]:
        ts = cv2.getTextSize(ln, FONT, SCALE, THICK)[0]
        cv2.putText(frame, ln, ((w - ts[0]) // 2, y),
                    FONT, SCALE, txt_color, THICK, cv2.LINE_AA)
        y += 34


# ─────────────────────────────────────────────────────────────────────────────
# HOLD OVERLAY  (frozen frame + pulsing banner + countdown)
# ─────────────────────────────────────────────────────────────────────────────


def draw_hold_overlay(frame, message: str, remaining_sec: float = 0.0):
    """
    Drawn when HOLD state is active (video is frozen).

    Shows:
      - Pulsing orange centre banner
      - Completion message (e.g. "Complete 2 more reps (3/5)")
      - Live countdown: "Resuming in Xs"

    Args:
        frame:         the frozen frame to draw on
        message:       rep-completion instruction from base_controller
        remaining_sec: seconds left in the 10-s HOLD window
    """
    h, w = frame.shape[:2]
    FONT = cv2.FONT_HERSHEY_SIMPLEX

    # ── Darken the whole frame so it clearly looks frozen ──────────────
    dark = frame.copy()
    cv2.rectangle(dark, (0, 0), (w, h), _BLACK, -1)
    cv2.addWeighted(dark, 0.40, frame, 0.60, 0, frame)

    # ── Pulsing orange banner ──────────────────────────────────────────
    pulse    = abs((time.time() % 1.0) - 0.5) * 2   # 0→1→0 per second
    alpha    = 0.55 + pulse * 0.18
    BANNER_H = 140
    y_start  = (h - BANNER_H) // 2
    y_end    = y_start + BANNER_H

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, y_start), (w, y_end), _ORANGE, -1)
    cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0, frame)

    # ── Top/bottom accent lines on banner ─────────────────────────────
    cv2.line(frame, (0, y_start), (w, y_start), _WHITE, 2)
    cv2.line(frame, (0, y_end),   (w, y_end),   _WHITE, 2)

    # ── "FINISH YOUR REPS!" header ────────────────────────────────────
    _put_centered(frame, "⏸  FINISH YOUR REPS!", y_start + 36,
                  FONT, 0.95, _WHITE, 2)

    # ── Rep instruction ───────────────────────────────────────────────
    lines = _wrap_text(message, w, FONT, 0.72, 2)
    y = y_start + 72
    for ln in lines[:2]:
        ts = cv2.getTextSize(ln, FONT, 0.72, 2)[0]
        cv2.putText(frame, ln, ((w - ts[0]) // 2, y),
                    FONT, 0.72, _WHITE, 2, cv2.LINE_AA)
        y += 32

    # ── Countdown pill ─────────────────────────────────────────────────
    countdown_txt = f"Resuming in  {int(remaining_sec)}s"
    ts  = cv2.getTextSize(countdown_txt, FONT, 0.68, 2)[0]
    cx  = (w - ts[0]) // 2
    cy  = y_end + 38

    # pill background
    pad = 8
    cv2.rectangle(frame,
                  (cx - pad, cy - ts[1] - pad),
                  (cx + ts[0] + pad, cy + pad),
                  _DARK, -1)
    cv2.rectangle(frame,
                  (cx - pad, cy - ts[1] - pad),
                  (cx + ts[0] + pad, cy + pad),
                  _ORANGE, 2)

    cv2.putText(frame, countdown_txt, (cx, cy),
                FONT, 0.68, _YELLOW, 2, cv2.LINE_AA)


# ─────────────────────────────────────────────────────────────────────────────
# COUNTDOWN + INTRO  (full-screen)
# ─────────────────────────────────────────────────────────────────────────────


def draw_countdown(frame, seconds: int):
    """Full-screen countdown overlay used during startup (3… 2… 1…)."""
    h, w = frame.shape[:2]
    FONT = cv2.FONT_HERSHEY_SIMPLEX

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, h), _BLACK, -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

    _put_centered(frame, "Get ready", h // 2 - 70, FONT, 1.4, _WHITE, 2)
    _put_centered(frame, str(seconds), h // 2 + 50, FONT, 4.0, _CYAN, 6)


def draw_intro(frame, title: str):
    """Full-screen intro overlay explaining how the system works."""
    h, w = frame.shape[:2]
    FONT = cv2.FONT_HERSHEY_SIMPLEX

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, h), _BLACK, -1)
    cv2.addWeighted(overlay, 0.72, frame, 0.28, 0, frame)

    lines = [
        title,
        "",
        "Your camera is tracking your pose.",
        "Follow the mentor in the video.",
        "The video pauses if your form needs correction.",
    ]

    y = h // 2 - 100
    for i, ln in enumerate(lines):
        sc  = 1.1  if i == 0 else 0.75
        col = _CYAN if i == 0 else _GREY
        th  = 2    if i == 0 else 1
        _put_centered(frame, ln, y, FONT, sc, col, th)
        y  += 52 if i == 0 else 38


# ─────────────────────────────────────────────────────────────────────────────
# COMPOSITE DRAW  — single call from main loop
# ─────────────────────────────────────────────────────────────────────────────


def render_frame(frame, *, coach_state: str, watch_msg: str = "",
                 rep_done: int = 0, rep_target: int = 0,
                 correct: bool = True, message: str = "",
                 hold_remaining: float = 0.0):
    """
    Single entry-point called once per frame from the main loop.

    Draw order (painter's algorithm — later = on top):
      1. Phase banner (top strip, state pill only)
      2. FPS counter (top-left, inside the banner area)
      3. Watch-carefully overlay (WATCH / PREPARE states only)
      4. Rep counter (left side, below FPS)
      5. Coach message (bottom bar)
      6. Hold overlay  (HOLD state only — drawn last, on top of everything)

    Args:
        frame:          BGR frame to draw on (modified in place)
        coach_state:    "WATCH" | "PREPARE" | "ACTIVE" | "ZOOM" | "HOLD"
        watch_msg:      phase watch_msg string (shown during WATCH/PREPARE)
        rep_done:       reps completed so far
        rep_target:     reps required for this phase
        correct:        True = green feedback, False = red
        message:        coaching text to show in bottom bar
        hold_remaining: seconds left in HOLD window (used by hold overlay)
    """

    # 1. Top banner (state pill, no exercise name)
    draw_phase_banner(frame, coach_state)

    # 2. FPS — drawn immediately after banner so it's always visible
    draw_fps(frame)

    # 3. Watch-carefully banner during non-active states
    if coach_state in ("WATCH", "PREPARE", "ZOOM"):
        draw_watch_carefully(frame, watch_msg)

    # 4. Rep counter — only during ACTIVE and HOLD states
    #    (no reps to show during WATCH/PREPARE/ZOOM)
    if rep_target > 0 and coach_state in ("ACTIVE", "HOLD"):
        draw_rep_counter(frame, rep_done, rep_target, watch_active=False)

    # 5. Bottom coach message — ACTIVE state only
    #    HOLD state gets its own overlay (drawn below)
    if coach_state == "ACTIVE" and message:
        draw_coach_message(frame, message, correct)

    # 6. Hold overlay — drawn on top of everything when video is frozen
    if coach_state == "HOLD":
        draw_hold_overlay(frame, message, hold_remaining)