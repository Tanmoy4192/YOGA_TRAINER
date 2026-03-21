"""
core/pose_similarity.py
Cosine similarity — keypoints chosen per sub-exercise phase.
Similarity is ONLY called when ref frame has full body visible (checked in base_controller).
"""
import numpy as np

# ── Keypoints per exercise/phase ─────────────────────────────────────
KEYPOINTS_BY_EXERCISE = {
    # Hand sub-phases
    "hand_both_arms_up":     [11, 12, 13, 14, 15, 16, 19, 20, 21, 22],   # arms + index + thumb
    "hand_t_pose":           [11, 12, 13, 14, 15, 16],                    # full arms
    "hand_rotation_right":   [12, 14, 16, 18, 20, 22],                    # right arm + fingers
    "hand_rotation_left":    [11, 13, 15, 17, 19, 21],                    # left arm + fingers
    "hand_rotation_both":    [11, 12, 13, 14, 15, 16, 17, 18, 19, 20],   # both arms + fingers
    "hand_arm_swing":        [11, 12, 13, 14, 15, 16, 23, 24, 27, 28],   # arms + hips + ankles (foot pos)
    "hand_torso_rotate":     [11, 12, 23, 24, 27, 28, 31, 32],           # shoulders+hips+feet+toes
    "hand_knee_rotate":      [23, 24, 25, 26, 27, 28, 29, 30, 31, 32],   # full legs + feet

    # Generic hand fallback
    "hand":                  [11, 12, 13, 14, 15, 16],

    # Leg exercises
    "leg":                   [23, 24, 25, 26, 27, 28, 29, 30, 31, 32],

    # Other exercises (unchanged)
    "neuro":       [11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28],
    "eye":         [0, 7, 8, 11, 12],
    "kapalabhati": [11, 12, 23, 24],
    "makarasana":  [11, 12, 13, 14, 23, 24, 25, 26, 27, 28],
    "massage":     [11, 12, 13, 14, 15, 16],
    "acupressure": [13, 14, 15, 16],
    "relaxation":  [11, 12, 13, 14, 23, 24, 25, 26, 27, 28],
}

DEFAULT_KEYPOINTS = [11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]


def normalize_landmarks(landmarks, keypoints: list) -> np.ndarray:
    pts = np.array([[landmarks[i].x, landmarks[i].y] for i in keypoints])
    center = (pts[0] + pts[1]) / 2
    pts -= center
    scale = np.linalg.norm(pts[1] - pts[0]) or 1
    pts /= scale
    return pts.flatten()


def pose_similarity(user_lm, ref_lm, exercise_key: str = None) -> float:
    keypoints = KEYPOINTS_BY_EXERCISE.get(exercise_key, DEFAULT_KEYPOINTS)
    # only use keypoints that exist in both landmark sets
    max_idx = min(len(user_lm), len(ref_lm))
    keypoints = [k for k in keypoints if k < max_idx]
    if len(keypoints) < 2:
        return 1.0  # not enough points — don't penalise
    u = normalize_landmarks(user_lm, keypoints)
    r = normalize_landmarks(ref_lm,  keypoints)
    mag = np.linalg.norm(u) * np.linalg.norm(r)
    return float(np.dot(u, r) / mag) if mag else 0.0