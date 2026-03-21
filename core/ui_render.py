"""core/ui_renderer.py"""
import cv2


def draw_coach_message(frame, message: str, correct: bool):
    """Large message bar at bottom of frame."""
    if not message:
        return
    h, w, _ = frame.shape
    overlay  = frame.copy()
    bar_h    = 80
    cv2.rectangle(overlay, (0, h-bar_h), (w, h), (0,0,0), -1)
    cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)
    color = (100, 255, 100) if correct else (80, 80, 255)

    # wrap text if too long
    font, scale, thick = cv2.FONT_HERSHEY_SIMPLEX, 0.85, 2
    words, lines, line = message.split(), [], ""
    for word in words:
        test = (line + " " + word).strip()
        if cv2.getTextSize(test, font, scale, thick)[0][0] < w - 40:
            line = test
        else:
            if line: lines.append(line)
            line = word
    if line: lines.append(line)

    y = h - bar_h + 28
    for ln in lines[:2]:
        ts = cv2.getTextSize(ln, font, scale, thick)[0]
        cv2.putText(frame, ln, ((w-ts[0])//2, y), font, scale, color, thick)
        y += 34


def draw_rep_counter(frame, done: int, target: int):
    """Top-left of frame."""
    color = (0, 255, 100) if done < target else (0, 220, 255)
    text  = f"{done} / {target}"
    cv2.putText(frame, text, (30, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 1.6, color, 3)


def draw_phase_banner(frame, phase_name: str, coach_state: str):
    """Top banner showing phase name and coach state."""
    h, w, _ = frame.shape
    overlay  = frame.copy()
    cv2.rectangle(overlay, (0,0), (w, 52), (10,10,10), -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

    state_color = {
        "WATCH":   (200, 200,   0),
        "PREPARE": (  0, 200, 255),
        "ACTIVE":  (  0, 255, 100),
        "ZOOM":    (180, 180, 180),
    }.get(coach_state, (255,255,255))

    ts = cv2.getTextSize(phase_name, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)[0]
    cv2.putText(frame, phase_name, ((w-ts[0])//2, 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, state_color, 2)


def draw_countdown(frame, seconds: int):
    h, w, _ = frame.shape
    overlay  = frame.copy()
    cv2.rectangle(overlay, (0,0), (w,h), (0,0,0), -1)
    cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)
    cv2.putText(frame, "Starting In",
                (w//2-160, h//2-50),
                cv2.FONT_HERSHEY_SIMPLEX, 1.6, (255,255,255), 3)
    cv2.putText(frame, str(seconds),
                (w//2-25, h//2+70),
                cv2.FONT_HERSHEY_SIMPLEX, 3.5, (0,255,255), 6)


def draw_intro(frame, title: str):
    h, w, _ = frame.shape
    overlay  = frame.copy()
    cv2.rectangle(overlay, (0,0), (w,h), (0,0,0), -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
    lines = [title, "", "Follow the mentor in the video.",
             "Camera tracks your pose in real time."]
    y = h//2 - 90
    for ln in lines:
        ts = cv2.getTextSize(ln, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)[0]
        cv2.putText(frame, ln, ((w-ts[0])//2, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255,255,255), 2)
        y += 55