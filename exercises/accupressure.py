"""
exercises/accupressure.py — SKY Yoga Acupressure Exercise

CONVERTED FROM THE STANDALONE ACUPRESSURE MODULE INTO THE REPO'S
STANDARD SINGLE-FILE EXERCISE FORMAT.

SEQUENCE:
  p1   Left Neck
  p2   Solar Plexus
  p3   Mid Abdomen
  p4   Above Navel
  p5   Navel Pull Up
  p6   Navel Push Down
  p7   Navel → Right Shoulder
  p8   Navel → Left Shoulder
  p9   Navel → Right Thigh
  p10  Navel → Left Thigh
  p11  Right Ribs
  p12  Left Ribs
  p13  Right Waist
  p14  Lower Left Abdomen
  p15  Relax

DETECTION MODEL:
  - Dynamic body-relative points computed from pose landmarks
  - Right index / thumb taken from pose finger landmarks already available
  - Touch requires XY proximity, Z-depth proximity and valid direction when needed
  - Each point is treated as a ~30 second / ~8 breath hold
"""

import math
import time
from collections import deque
from dataclasses import dataclass, field

from core.base_controller import BaseController
from core.breath_detector import BreathDetector
from core.utils import visible

EXERCISE_KEY = "accupressure"

# Pose landmark indices already used elsewhere in this project
L_SHOULDER = 11
R_SHOULDER = 12
L_HIP = 23
R_HIP = 24
L_EAR = 7
NOSE = 0
L_KNEE = 25
R_INDEX_TIP = 20
R_THUMB_TIP = 22
L_WRIST = 15
R_WRIST = 16

TARGET_BREATHS = 1
TARGET_HOLD_SEC = 30.0
HOLD_CONFIRM_SEC = 2.0
TIME_STEP_SEC = TARGET_HOLD_SEC
SMOOTH_N = 6
DIR_THRESHOLD = 0.004
Z_TOUCH_THRESHOLD = 0.18


# ─────────────────────────────────────────────────────────────────────────────
# PHASE DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────

_PHASES = [
    {
        "id": "ac_p0_intro",
        "name": "Acupressure — General Rules",
        "start": 3197, "active": 3197, "end": 3200,
        "zoom": True,
        "watch_msg": "Lie flat on your back. Use your right index finger or thumb and observe the pressure points.",
    },
    {
        "id": "ac_p1_neck",
        "name": "Step 1 — Left Neck",
        "start": 3200, "active": 3202, "end": 3210,
        "target": 1,
        "finger": "index",
        "watch_msg": "Place your right index finger gently on the left side of your neck.",
    },
    {
        "id": "ac_p2_solar",
        "name": "Step 2 — Solar Plexus",
        "start": 3210, "active": 3212, "end": 3240,
        "target": 1,
        "finger": "index",
        "watch_msg": "Touch the center of the upper abdomen below the chest.",
    },
    {
        "id": "ac_p3_mid_abdomen",
        "name": "Step 3 — Mid Abdomen",
        "start": 3240, "active": 3242, "end": 3260,
        "target": 1,
        "finger": "index",
        "watch_msg": "Move one finger-width below the solar plexus and hold.",
    },
    {
        "id": "ac_p4_above_navel",
        "name": "Step 4 — Above Navel",
        "start": 3260, "active": 3262, "end": 3276,
        "target": 1,
        "finger": "index",
        "watch_msg": "Place the right index finger slightly above the navel.",
    },
    {
        "id": "ac_p5_navel_up",
        "name": "Step 5 — Navel Pull Up",
        "start": 3276, "active": 3278, "end": 3298,
        "target": 1,
        "finger": "index",
        "direction": "up",
        "watch_msg": "Touch the navel with the right index finger and pull upward toward the head.",
    },
    {
        "id": "ac_p6_navel_down",
        "name": "Step 6 — Navel Push Down",
        "start": 3298, "active": 3300, "end": 3313,
        "target": 1,
        "finger": "thumb",
        "direction": "down",
        "watch_msg": "Touch the navel with the right thumb and push downward toward the feet.",
    },
    {
        "id": "ac_p7_navel_r_shoulder",
        "name": "Step 7 — Navel to Right Shoulder",
        "start": 3313, "active": 3315, "end": 3339,
        "target": 1,
        "finger": "index",
        "direction": "right_shoulder",
        "watch_msg": "Touch the navel with the right index finger and pull toward the right shoulder.",
    },
    {
        "id": "ac_p8_navel_l_shoulder",
        "name": "Step 8 — Navel to Left Shoulder",
        "start": 3339, "active": 3341, "end": 3366,
        "target": 1,
        "finger": "index",
        "direction": "left_shoulder",
        "watch_msg": "Touch the navel with the right index finger and pull toward the left shoulder.",
    },
    {
        "id": "ac_p9_navel_r_thigh",
        "name": "Step 9 — Navel to Right Thigh",
        "start": 3366, "active": 3368, "end": 3387,
        "target": 1,
        "finger": "index",
        "direction": "right_thigh",
        "watch_msg": "Touch the navel with the right index finger and pull toward the right thigh.",
    },
    {
        "id": "ac_p10_navel_l_thigh",
        "name": "Step 10 — Navel to Left Thigh",
        "start": 3387, "active": 3389, "end": 3405,
        "target": 1,
        "finger": "thumb",
        "direction": "left_thigh",
        "watch_msg": "Touch the navel with the right thumb and push toward the left thigh.",
    },
    {
        "id": "ac_p11_right_ribs",
        "name": "Step 11 — Right Ribs",
        "start": 3405, "active": 3407, "end": 3419,
        "target": 1,
        "finger": "index",
        "watch_msg": "Move below the right ribcage and press gently.",
    },
    {
        "id": "ac_p12_left_ribs",
        "name": "Step 12 — Left Ribs",
        "start": 3419, "active": 3421, "end": 3438,
        "target": 1,
        "finger": "index",
        "watch_msg": "Move below the left ribcage and press gently.",
    },
    {
        "id": "ac_p13_right_waist",
        "name": "Step 13 — Right Waist",
        "start": 3438, "active": 3440, "end": 3458,
        "target": 1,
        "finger": "thumb",
        "watch_msg": "Place the right thumb on the soft area between your right ribs and hip.",
    },
    {
        "id": "ac_p14_lower_left_abdomen",
        "name": "Step 14 — Lower Left Abdomen",
        "start": 3458, "active": 3460, "end": 3479,
        "target": 1,
        "finger": "index",
        "watch_msg": "Place the right index finger between the navel and left groin crease.",
    },
    {
        "id": "ac_p15_rest",
        "name": "Finish — Rest",
        "start": 3479, "active": 3481, "end": 3489,
        "target": 0,
        "watch_msg": "Relax both arms by your sides and rest.",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# DATA TYPES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Point3D:
    x: float
    y: float
    z: float = 0.0


@dataclass
class TouchResult:
    touched: bool = False
    xy_close: bool = False
    z_close: bool = False
    approaching: bool = False
    distance_xy: float = 999.0
    direction: str = "none"
    confidence: float = 0.0
    message: str = ""


@dataclass
class FrameEval:
    phase_id: str = ""
    touch: TouchResult = field(default_factory=TouchResult)
    hold_elapsed: float = 0.0


class HoldTimer:
    """Continuous-touch timer used inside ACTIVE state."""

    def __init__(self, required_seconds: float = TARGET_HOLD_SEC):
        self.required = required_seconds
        self._start = None
        self._held = 0.0

    def update(self, touching: bool) -> float:
        now = time.monotonic()
        if touching:
            if self._start is None:
                self._start = now
            self._held = min(now - self._start, self.required)
        else:
            self._start = None
            self._held = 0.0
        return self._held

    def reset(self, required_seconds: float | None = None):
        if required_seconds is not None:
            self.required = required_seconds
        self._start = None
        self._held = 0.0

    @property
    def elapsed(self) -> float:
        return self._held


class FingerState:
    """Smoothed fingertip position with simple velocity tracking."""

    def __init__(self):
        self._history = deque(maxlen=SMOOTH_N)

    def reset(self):
        self._history.clear()

    def update(self, pt: Point3D):
        self._history.append((pt.x, pt.y, pt.z))

    @property
    def pos(self):
        if not self._history:
            return None
        xs = [p[0] for p in self._history]
        ys = [p[1] for p in self._history]
        zs = [p[2] for p in self._history]
        return Point3D(sum(xs) / len(xs), sum(ys) / len(ys), sum(zs) / len(zs))

    @property
    def velocity(self):
        if len(self._history) < 3:
            return None
        old = self._history[0]
        new = self._history[-1]
        span = len(self._history) - 1
        return ((new[0] - old[0]) / span, (new[1] - old[1]) / span)


# ─────────────────────────────────────────────────────────────────────────────
# BODY GEOMETRY + POINTS
# ─────────────────────────────────────────────────────────────────────────────

def _dist(a: Point3D, b: Point3D) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _blend(a: Point3D, b: Point3D, t: float) -> Point3D:
    return Point3D(
        a.x + (b.x - a.x) * t,
        a.y + (b.y - a.y) * t,
        a.z + (b.z - a.z) * t,
    )


def _point(lm, idx: int):
    if idx >= len(lm):
        return None
    src = lm[idx]
    return Point3D(src.x, src.y, src.z)


class BodyGeometry:
    """Per-frame body anchors used to derive all acupressure targets."""

    def __init__(self, lm):
        self.valid = False

        if not visible(lm, L_SHOULDER, R_SHOULDER, L_HIP, R_HIP):
            return

        self.ls = _point(lm, L_SHOULDER)
        self.rs = _point(lm, R_SHOULDER)
        self.lh = _point(lm, L_HIP)
        self.rh = _point(lm, R_HIP)
        self.nose = _point(lm, NOSE)
        self.l_ear = _point(lm, L_EAR)
        self.l_knee = _point(lm, L_KNEE)

        self.shoulder_mid = _blend(self.ls, self.rs, 0.5)
        self.hip_mid = _blend(self.lh, self.rh, 0.5)
        self.torso_height = _dist(self.shoulder_mid, self.hip_mid)
        self.unit = max(self.torso_height * 0.08, 0.005)
        self.body_z = (self.ls.z + self.rs.z + self.lh.z + self.rh.z) / 4.0
        self.valid = True


def get_left_neck(geo: BodyGeometry):
    if not geo.valid:
        return None
    if geo.l_ear:
        return _blend(geo.ls, geo.l_ear, 0.45)
    if geo.nose:
        return _blend(geo.ls, geo.nose, 0.38)
    return Point3D(geo.ls.x, geo.ls.y - geo.unit * 1.5, geo.ls.z)


def get_solar_plexus(geo: BodyGeometry):
    if not geo.valid:
        return None
    return _blend(geo.shoulder_mid, geo.hip_mid, 0.22)


def get_mid_abdomen(geo: BodyGeometry):
    solar = get_solar_plexus(geo)
    if not solar:
        return None
    return Point3D(solar.x, solar.y + geo.unit, solar.z)


def get_above_navel(geo: BodyGeometry):
    if not geo.valid:
        return None
    return _blend(geo.shoulder_mid, geo.hip_mid, 0.70)


def get_navel(geo: BodyGeometry):
    if not geo.valid:
        return None
    return _blend(geo.shoulder_mid, geo.hip_mid, 0.55)


def get_right_ribs(geo: BodyGeometry):
    if not geo.valid:
        return None
    return _blend(geo.rs, geo.rh, 0.32)


def get_left_ribs(geo: BodyGeometry):
    if not geo.valid:
        return None
    return _blend(geo.ls, geo.lh, 0.32)


def get_right_waist(geo: BodyGeometry):
    if not geo.valid:
        return None
    return _blend(geo.rs, geo.rh, 0.65)


def get_lower_left_abdomen(geo: BodyGeometry):
    if not geo.valid:
        return None
    navel = get_navel(geo)
    if geo.l_knee:
        groin = _blend(geo.lh, geo.l_knee, 0.20)
    else:
        groin = Point3D(geo.lh.x, geo.lh.y + geo.unit * 1.5, geo.lh.z)
    return _blend(navel, groin, 0.5)


POINT_GETTERS = {
    "ac_p1_neck": get_left_neck,
    "ac_p2_solar": get_solar_plexus,
    "ac_p3_mid_abdomen": get_mid_abdomen,
    "ac_p4_above_navel": get_above_navel,
    "ac_p5_navel_up": get_navel,
    "ac_p6_navel_down": get_navel,
    "ac_p7_navel_r_shoulder": get_navel,
    "ac_p8_navel_l_shoulder": get_navel,
    "ac_p9_navel_r_thigh": get_navel,
    "ac_p10_navel_l_thigh": get_navel,
    "ac_p11_right_ribs": get_right_ribs,
    "ac_p12_left_ribs": get_left_ribs,
    "ac_p13_right_waist": get_right_waist,
    "ac_p14_lower_left_abdomen": get_lower_left_abdomen,
}


# ─────────────────────────────────────────────────────────────────────────────
# TOUCH DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def _classify_direction(dx: float, dy: float) -> str:
    if abs(dx) < DIR_THRESHOLD and abs(dy) < DIR_THRESHOLD:
        return "none"

    diag = abs(dx) > DIR_THRESHOLD * 0.5 and abs(dy) > DIR_THRESHOLD * 0.5
    if diag:
        if dx > 0 and dy < 0:
            return "right_up"
        if dx < 0 and dy < 0:
            return "left_up"
        if dx > 0 and dy > 0:
            return "right_down"
        if dx < 0 and dy > 0:
            return "left_down"

    if abs(dy) >= abs(dx):
        return "up" if dy < 0 else "down"
    return "right" if dx > 0 else "left"


def _direction_matches(detected: str, required: str | None) -> bool:
    if not required:
        return True
    if detected == required:
        return True

    aliases = {
        "up": {"up", "left_up", "right_up"},
        "down": {"down", "left_down", "right_down"},
        "right_shoulder": {"right_up", "up", "right"},
        "left_shoulder": {"left_up", "up", "left"},
        "right_thigh": {"right_down", "down", "right"},
        "left_thigh": {"left_down", "down", "left"},
    }
    return detected in aliases.get(required, {required})


class TouchDetector:
    """Single-file version of the standalone touch detector."""

    def __init__(self):
        self.index_state = FingerState()
        self.thumb_state = FingerState()

    def reset(self):
        self.index_state.reset()
        self.thumb_state.reset()

    def _pick_state(self, required_finger: str):
        if required_finger == "thumb":
            return self.thumb_state
        return self.index_state

    def update(self, finger_pt: Point3D | None, target: Point3D, geo: BodyGeometry, phase_id: str, required_direction: str | None):
        if finger_pt is None or not geo.valid or target is None:
            return TouchResult(message="Show your right hand clearly to the camera.")

        state = self._pick_state("thumb" if phase_id in ("ac_p6_navel_down", "ac_p10_navel_l_thigh", "ac_p13_right_waist") else "index")
        state.update(finger_pt)
        pos = state.pos
        vel = state.velocity

        if pos is None:
            return TouchResult(message="Show your right hand clearly to the camera.")

        xy_touch = geo.unit * (4.0 if phase_id == "ac_p1_neck" else 2.5)
        if phase_id in (
            "ac_p5_navel_up",
            "ac_p6_navel_down",
            "ac_p7_navel_r_shoulder",
            "ac_p8_navel_l_shoulder",
            "ac_p9_navel_r_thigh",
            "ac_p10_navel_l_thigh",
        ):
            xy_touch = geo.unit * 2.0

        dist_xy = _dist(pos, target)
        xy_close = dist_xy <= xy_touch
        z_close = abs(pos.z - geo.body_z) <= Z_TOUCH_THRESHOLD

        approaching = True
        direction = "none"
        if vel is not None:
            direction = _classify_direction(vel[0], vel[1])
            dx_to = target.x - pos.x
            dy_to = target.y - pos.y
            mag = math.hypot(dx_to, dy_to) or 1e-9
            approach_score = (vel[0] * dx_to + vel[1] * dy_to) / mag
            approaching = approach_score >= -0.010

        direction_ok = _direction_matches(direction, required_direction)
        touched = xy_close and z_close and approaching and direction_ok

        xy_score = max(0.0, 1.0 - dist_xy / max(xy_touch * 1.5, 1e-6))
        z_score = max(0.0, 1.0 - abs(pos.z - geo.body_z) / (Z_TOUCH_THRESHOLD * 2.0))
        confidence = min(1.0, xy_score * 0.70 + z_score * 0.30)

        return TouchResult(
            touched=touched,
            xy_close=xy_close,
            z_close=z_close,
            approaching=approaching,
            distance_xy=dist_xy,
            direction=direction,
            confidence=confidence,
        )


# ─────────────────────────────────────────────────────────────────────────────
# CONTROLLER
# ─────────────────────────────────────────────────────────────────────────────

class WorkoutController(BaseController):
    """Acupressure controller in the same format as the other exercise files."""

    def __init__(self):
        super().__init__()
        self._detector = TouchDetector()
        self._hold = HoldTimer(TARGET_HOLD_SEC)
        self._frame_eval = FrameEval()

    def phases(self) -> list:
        return _PHASES

    def on_phase_change(self, phase: dict):
        self._detector.reset()
        self._hold.reset(TARGET_HOLD_SEC)
        self._frame_eval = FrameEval()

    @property
    def current_phase_name(self) -> str:
        p = self._get_phase(self._video_pos)
        return p["name"] if p else "Acupressure"

    # ─────────────────────────────────────────────────────────────────────
    # MAIN CHECKS
    # ─────────────────────────────────────────────────────────────────────

    def check_pose(self, lm, w, h, phase) -> tuple:
        pid = phase["id"]

        if pid == "ac_p0_intro":
            return (False, "Watch the instructor and prepare for the first point.")

        if pid == "ac_p15_rest":
            if self._is_relaxed_rest(lm):
                return (False, "Good — relax and breathe naturally.")
            return (True, "Relax both arms to your sides.")

        flat_ok, flat_msg = self._check_lying_flat(lm)
        if not flat_ok:
            self._hold.reset(TARGET_HOLD_SEC)
            return (True, flat_msg)

        geo = BodyGeometry(lm)
        if not geo.valid:
            self._hold.reset(TARGET_HOLD_SEC)
            return (True, "Keep your torso clearly visible in the frame.")

        target = POINT_GETTERS[pid](geo)
        if target is None:
            self._hold.reset(TARGET_HOLD_SEC)
            return (True, "Body landmarks are unclear — adjust your camera.")

        finger_name = phase.get("finger", "index")
        finger_pt = self._required_finger(lm, finger_name)
        touch = self._detector.update(
            finger_pt=finger_pt,
            target=target,
            geo=geo,
            phase_id=pid,
            required_direction=phase.get("direction"),
        )

        hold_elapsed = self._hold.update(touch.touched)
        self._frame_eval = FrameEval(phase_id=pid, touch=touch, hold_elapsed=hold_elapsed)

        if touch.touched:
            if hold_elapsed < HOLD_CONFIRM_SEC:
                return (False, f"Correct — keep steady for {HOLD_CONFIRM_SEC - hold_elapsed:.1f}s.")

            remaining = max(0.0, TARGET_HOLD_SEC - hold_elapsed)
            return (False, f"Correct — hold for {remaining:.0f}s more.")

        return (True, self._feedback_for_touch(phase, touch))

    def detect_rep(self, lm, w, h):
        phase = self._active_phase
        if not phase or phase.get("target", 0) == 0:
            return

        if self._frame_eval.phase_id != phase["id"]:
            return

        touch = self._frame_eval.touch
        hold_elapsed = self._frame_eval.hold_elapsed
        if not touch.touched or hold_elapsed < HOLD_CONFIRM_SEC:
            return

        self.rep_count = 1 if hold_elapsed >= TIME_STEP_SEC else 0

    # ─────────────────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────────────────

    def _required_finger(self, lm, finger_name: str):
        idx = R_THUMB_TIP if finger_name == "thumb" else R_INDEX_TIP
        if idx >= len(lm):
            return None
        vis = getattr(lm[idx], "visibility", 1.0)
        if vis < 0.40:
            return None
        return Point3D(lm[idx].x, lm[idx].y, lm[idx].z)

    def _check_lying_flat(self, lm) -> tuple:
        if not visible(lm, L_SHOULDER, R_SHOULDER, L_HIP, R_HIP):
            return (False, "Keep your shoulders and hips visible in the frame.")

        shoulder_y = (lm[L_SHOULDER].y + lm[R_SHOULDER].y) / 2.0
        hip_y = (lm[L_HIP].y + lm[R_HIP].y) / 2.0
        vertical_gap = abs(hip_y - shoulder_y)
        shoulder_z_gap = abs(lm[L_SHOULDER].z - lm[R_SHOULDER].z)
        hip_z_gap = abs(lm[L_HIP].z - lm[R_HIP].z)

        if shoulder_y < 0.35 and vertical_gap > 0.25:
            return (False, "Please lie flat on your back before starting acupressure.")
        if shoulder_z_gap > 0.45 or hip_z_gap > 0.45:
            return (False, "Roll your body flatter so both shoulders and hips align.")
        return (True, None)

    def _is_relaxed_rest(self, lm) -> bool:
        if not visible(lm, L_HIP, R_HIP, L_WRIST, R_WRIST):
            return False
        hip_y = (lm[L_HIP].y + lm[R_HIP].y) / 2.0
        return lm[L_WRIST].y > hip_y - 0.03 and lm[R_WRIST].y > hip_y - 0.03

    def _feedback_for_touch(self, phase: dict, touch: TouchResult) -> str:
        req = phase.get("direction")
        pid = phase["id"]

        if not touch.xy_close:
            return self._correction_msg(pid)
        if touch.xy_close and not touch.z_close:
            return "Getting close — press your finger slightly into the body."
        if req and not _direction_matches(touch.direction, req):
            return self._direction_hint(req)
        if not touch.approaching:
            return "Move the finger toward the point, not away from it."
        return self._correction_msg(pid)

    def _direction_hint(self, required: str) -> str:
        hints = {
            "up": "Pull upward toward your head.",
            "down": "Push downward toward your feet.",
            "right_shoulder": "Pull diagonally toward your right shoulder.",
            "left_shoulder": "Pull diagonally toward your left shoulder.",
            "right_thigh": "Pull diagonally toward your right thigh.",
            "left_thigh": "Push diagonally toward your left thigh.",
        }
        return hints.get(required, "Adjust the finger direction.")

    def _correction_msg(self, pid: str) -> str:
        msgs = {
            "ac_p1_neck": "Place your right index finger on the left side of your neck.",
            "ac_p2_solar": "Move your right index finger to the solar plexus.",
            "ac_p3_mid_abdomen": "Move one finger-width below the solar plexus.",
            "ac_p4_above_navel": "Move one finger-width above the navel.",
            "ac_p5_navel_up": "Touch the navel and start pulling upward.",
            "ac_p6_navel_down": "Touch the navel with the thumb and push downward.",
            "ac_p7_navel_r_shoulder": "Touch the navel and pull toward the right shoulder.",
            "ac_p8_navel_l_shoulder": "Touch the navel and pull toward the left shoulder.",
            "ac_p9_navel_r_thigh": "Touch the navel and pull toward the right thigh.",
            "ac_p10_navel_l_thigh": "Touch the navel with the thumb and push toward the left thigh.",
            "ac_p11_right_ribs": "Move below the right ribcage and press gently.",
            "ac_p12_left_ribs": "Move below the left ribcage and press gently.",
            "ac_p13_right_waist": "Place the right thumb on the right waist point.",
            "ac_p14_lower_left_abdomen": "Move to the lower left abdomen point.",
        }
        return msgs.get(pid, "Adjust your finger position.")
