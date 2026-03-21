"""core/utils.py — geometry helpers"""
import math


def calculate_angle(a, b, c) -> float:
    """Angle at joint b, given three (x,y) points."""
    BA = (a[0]-b[0], a[1]-b[1])
    BC = (c[0]-b[0], c[1]-b[1])
    dot  = BA[0]*BC[0] + BA[1]*BC[1]
    mags = math.sqrt(BA[0]**2+BA[1]**2) * math.sqrt(BC[0]**2+BC[1]**2)
    if mags == 0:
        return 0.0
    return math.degrees(math.acos(max(-1.0, min(1.0, dot/mags))))


def dist(p1, p2) -> float:
    return math.hypot(p1[0]-p2[0], p1[1]-p2[1])


def lm_px(lm, idx, width, height):
    """Return landmark as pixel (x, y) tuple."""
    return (lm[idx].x * width, lm[idx].y * height)