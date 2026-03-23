"""
core/utils.py — Geometry and measurement helpers

Key principle: ALL body position measurements use shoulder_width() normalization.
This makes checks invariant to camera distance and person size.

DO NOT use raw pixel thresholds for body joints.
DO use raw pixels only for absolute screen positions (e.g., feet spacing).
"""
import math
from collections import deque


# ─────────────────────────────────────────────────────────────────────────────
# GEOMETRY FUNCTIONS (all return pixels or degrees, no normalization)
# ─────────────────────────────────────────────────────────────────────────────


def angle(a, b, c) -> float:
    """
    Calculate angle in degrees at joint b.
    a, b, c are (x_px, y_px) tuples.

    Example: angle((0,0), (1,0), (1,1)) = 90 degrees (right angle at center)
    """
    BA = (a[0] - b[0], a[1] - b[1])
    BC = (c[0] - b[0], c[1] - b[1])

    dot = BA[0] * BC[0] + BA[1] * BC[1]
    mag_ba = math.sqrt(BA[0] ** 2 + BA[1] ** 2)
    mag_bc = math.sqrt(BC[0] ** 2 + BC[1] ** 2)

    if mag_ba == 0 or mag_bc == 0:
        return 0.0

    cos_angle = dot / (mag_ba * mag_bc)
    cos_angle = max(-1.0, min(1.0, cos_angle))  # clamp to [-1, 1]
    return math.degrees(math.acos(cos_angle))


def dist(p1, p2) -> float:
    """
    Euclidean distance between two (x, y) points in pixels.
    """
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def px(lm, idx: int, w: int, h: int) -> tuple:
    """
    Convert MediaPipe landmark to pixel coordinates.
    MediaPipe uses normalized coords [0, 1], multiply by frame size.

    Args:
        lm: MediaPipe landmarks object
        idx: landmark index
        w, h: frame width and height

    Returns:
        (x_px, y_px) tuple
    """
    if idx < len(lm):
        return (lm[idx].x * w, lm[idx].y * h)
    return (0, 0)


def visible(lm, *idxs) -> bool:
    """
    Check if all requested landmarks are visible enough.
    Returns True if all have visibility >= 0.55.

    Usage: visible(lm, 11, 12, 13) checks shoulders and elbow
    """
    for idx in idxs:
        if idx >= len(lm) or lm[idx].visibility < 0.55:
            return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# BODY-SCALE NORMALIZATION
# ─────────────────────────────────────────────────────────────────────────────


def shoulder_width(lm, w: int, h: int) -> float:
    """
    Distance between shoulders (landmarks 11 and 12) in pixels.
    Use this to normalize all body joint measurements.

    If shoulders are not visible, returns 1.0 (identity).

    Example:
        gap = dist(left_wrist, right_wrist)
        normalized_gap = gap / shoulder_width(lm, w, h)
        if normalized_gap > 0.30:  # hands more than 30% of shoulder width apart
            ...
    """
    if not visible(lm, 11, 12):
        return 1.0

    l_shoulder = px(lm, 11, w, h)
    r_shoulder = px(lm, 12, w, h)
    return dist(l_shoulder, r_shoulder) or 1.0


def torso_len(lm, w: int, h: int) -> float:
    """
    Distance from shoulder to hip (landmarks 11 to 23) in pixels.
    Alternative normalization for torso-relative measurements.

    If not visible, returns 1.0 (identity).
    """
    if not visible(lm, 11, 23):
        return 1.0

    shoulder = px(lm, 11, w, h)
    hip = px(lm, 23, w, h)
    return dist(shoulder, hip) or 1.0


# ─────────────────────────────────────────────────────────────────────────────
# TEMPORAL SMOOTHING
# ─────────────────────────────────────────────────────────────────────────────


def smooth(buf: deque, val: float) -> float:
    """
    Add value to circular buffer and return mean.
    Used for noise reduction in landmark streams.

    Args:
        buf: collections.deque with preset maxlen
        val: float value to add

    Returns:
        mean of all values in buffer

    Usage:
        from collections import deque
        smooth_y = deque(maxlen=5)
        ...
        avg_y = smooth(smooth_y, lm[11].y)
    """
    buf.append(val)
    return sum(buf) / len(buf) if buf else 0.0