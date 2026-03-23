"""
pose_tester.py — Standalone Pose Tester
Test any exercise phase without running the full video.
Shows live debug values ON SCREEN — no need to look at console.

Usage:
  python pose_tester.py --exercise leg --phase leg_p1_toe_rotation
  python pose_tester.py --exercise hand --phase p1_arms_up
  python pose_tester.py          ← interactive menu

Controls:
  Q     → quit
  R     → reset rep count
  D     → toggle debug overlay on/off
  SPACE → freeze frame
"""

import cv2
import time
import argparse
import mediapipe as mp

from core.camera             import Camera
from core.pose_engine        import PoseEngine
from core.exercise_registry  import ExerciseRegistry
from core.utils              import calculate_angle, dist, lm_px

# colours
G = (60, 220, 80);   R = (60, 60, 240)
Y = (0, 210, 255);   W = (240, 240, 240)
K = (0, 0, 0);       C = (220, 200, 0)
GR = (120, 120, 120)

FONT = cv2.FONT_HERSHEY_SIMPLEX


def txt(frame, text, x, y, color=W, scale=0.65, thick=1):
    cv2.putText(frame, text, (x, y), FONT, scale, color, thick, cv2.LINE_AA)


def draw_main_hud(frame, phase_name, message, is_error, rep_count, target, frozen):
    h, w, _ = frame.shape

    # top banner
    ov = frame.copy()
    cv2.rectangle(ov, (0,0), (w,54), (15,15,15), -1)
    cv2.addWeighted(ov, 0.78, frame, 0.22, 0, frame)
    cv2.line(frame, (0,54), (w,54), G, 2)
    ts = cv2.getTextSize(phase_name, FONT, 0.9, 2)[0]
    txt(frame, phase_name, (w-ts[0])//2, 36, W, 0.9, 2)
    txt(frame, "TESTING", w-110, 36, G, 0.65, 2)

    # rep counter
    col  = G if rep_count < target else C
    text = f"{rep_count} / {target}" if target > 0 else f"Reps: {rep_count}"
    txt(frame, text, 20, 105, col, 2.0, 4)
    txt(frame, "REPS", 24, 128, GR, 0.55, 1)

    # progress bar
    ts2 = cv2.getTextSize(text, FONT, 2.0, 4)[0]
    bx, by, bw, bh = 20, 136, ts2[0], 6
    cv2.rectangle(frame, (bx,by), (bx+bw,by+bh), (50,50,50), -1)
    if target > 0:
        fill = int(bw * min(rep_count, target) / target)
        cv2.rectangle(frame, (bx,by), (bx+fill,by+bh), col, -1)

    # coach message bar
    if message:
        ov2 = frame.copy()
        bg  = (0,50,0) if not is_error else (0,0,60)
        cv2.rectangle(ov2, (0,h-88), (w,h), bg, -1)
        cv2.addWeighted(ov2, 0.72, frame, 0.28, 0, frame)
        mc = G if not is_error else R
        cv2.line(frame, (0,h-88), (w,h-88), mc, 2)
        words, lines, line = message.split(), [], ""
        for word in words:
            test = (line+" "+word).strip()
            if cv2.getTextSize(test, FONT, 0.80, 2)[0][0] < w-40:
                line = test
            else:
                if line: lines.append(line)
                line = word
        if line: lines.append(line)
        y = h-88+(88-len(lines)*34)//2+26
        for ln in lines[:2]:
            ts3 = cv2.getTextSize(ln, FONT, 0.80, 2)[0]
            cv2.putText(frame, ln, ((w-ts3[0])//2, y), FONT, 0.80, mc, 2, cv2.LINE_AA)
            y += 34

    if frozen:
        txt(frame, "FROZEN — press SPACE", 20, h-100, Y, 0.6, 2)

    # controls bottom right
    for i, c in enumerate(["Q=quit","R=reset","D=debug","SPACE=freeze"]):
        txt(frame, c, w-155, h-88+12+i*20, GR, 0.48, 1)


def draw_debug_overlay(frame, lm, phase_id, w, h):
    """
    Show live landmark values ON SCREEN — right side panel.
    Adjusts debug values shown based on which phase is active.
    """
    if lm is None:
        return

    px, py = w - 300, 70
    ov = frame.copy()
    cv2.rectangle(ov, (px-10, 60), (w, 420), (10,10,10), -1)
    cv2.addWeighted(ov, 0.75, frame, 0.25, 0, frame)
    cv2.line(frame, (px-10, 60), (px-10, 420), (60,60,60), 1)

    txt(frame, "DEBUG", px, py, C, 0.65, 2); py += 28

    if "leg" in phase_id or "toe" in phase_id:
        # Foot rotation debug
        l_ax = lm[27].x; l_fx = lm[31].x
        r_ax = lm[28].x; r_fx = lm[32].x
        l_diff = l_fx - l_ax
        r_diff = r_fx - r_ax

        txt(frame, "FOOT ROTATION:", px, py, GR, 0.55, 1); py += 22

        # Left foot
        l_state = "INWARD" if l_diff < -0.025 else ("OUTWARD" if l_diff > 0.025 else "neutral")
        l_col   = G if l_state == "INWARD" else (Y if l_state == "OUTWARD" else GR)
        txt(frame, f"L foot: {l_diff:+.3f}  {l_state}", px, py, l_col, 0.55, 1); py += 20

        r_state = "INWARD" if r_diff > 0.025 else ("OUTWARD" if r_diff < -0.025 else "neutral")
        r_col   = G if r_state == "INWARD" else (Y if r_state == "OUTWARD" else GR)
        txt(frame, f"R foot: {r_diff:+.3f}  {r_state}", px, py, r_col, 0.55, 1); py += 28

        # Both feet combined
        both_in  = l_state == "INWARD"  and r_state == "INWARD"
        both_out = l_state == "OUTWARD" and r_state == "OUTWARD"
        combined = "INWARD" if both_in else ("OUTWARD" if both_out else "NEUTRAL")
        c_col    = G if both_in else (Y if both_out else GR)
        txt(frame, f"BOTH: {combined}", px, py, c_col, 0.65, 2); py += 28

        # Visibility
        txt(frame, "VISIBILITY:", px, py, GR, 0.55, 1); py += 20
        for idx, name in [(27,"L ankle"),(28,"R ankle"),(31,"L foot"),(32,"R foot")]:
            vis = lm[idx].visibility
            vc  = G if vis > 0.6 else (Y if vis > 0.35 else R)
            txt(frame, f"  {name}: {vis:.2f}", px, py, vc, 0.50, 1); py += 18

        py += 8
        # Knee angles
        lh = lm_px(lm,23,w,h); lk = lm_px(lm,25,w,h); la = lm_px(lm,27,w,h)
        rh = lm_px(lm,24,w,h); rk = lm_px(lm,26,w,h); ra = lm_px(lm,28,w,h)
        la_ = calculate_angle(lh,lk,la); ra_ = calculate_angle(rh,rk,ra)
        txt(frame, "KNEE ANGLES:", px, py, GR, 0.55, 1); py += 20
        lc = G if la_ > 155 else R
        rc = G if ra_ > 155 else R
        txt(frame, f"  Left:  {la_:.0f}deg", px, py, lc, 0.55, 1); py += 18
        txt(frame, f"  Right: {ra_:.0f}deg", px, py, rc, 0.55, 1)

    elif "arm" in phase_id or "hand" in phase_id or "rot" in phase_id:
        ls  = lm_px(lm,11,w,h); le = lm_px(lm,13,w,h); lwr = lm_px(lm,15,w,h)
        rs  = lm_px(lm,12,w,h); re = lm_px(lm,14,w,h); rwr = lm_px(lm,16,w,h)
        la  = calculate_angle(ls,le,lwr); ra = calculate_angle(rs,re,rwr)
        txt(frame, "ELBOW ANGLES:", px, py, GR, 0.55, 1); py += 20
        txt(frame, f"  Left:  {la:.0f}deg", px, py, G if la>150 else R, 0.55, 1); py += 18
        txt(frame, f"  Right: {ra:.0f}deg", px, py, G if ra>150 else R, 0.55, 1); py += 22
        txt(frame, "WRIST Y (norm):", px, py, GR, 0.55, 1); py += 20
        txt(frame, f"  L wrist: {lm[15].y:.3f}", px, py, W, 0.55, 1); py += 18
        txt(frame, f"  L shoulder: {lm[11].y:.3f}", px, py, W, 0.55, 1); py += 18
        above = lm[15].y < lm[11].y
        txt(frame, f"  Arm raised: {'YES' if above else 'NO'}", px, py,
            G if above else R, 0.55, 1)


def list_exercises(registry):
    print("\nAvailable exercises:")
    for key in registry.keys():
        ctrl = registry.get(key)
        for p in ctrl.phases():
            print(f"  {key}  →  {p['id']}  |  {p['name']}")
    print()


def pick_interactive(registry):
    list_exercises(registry)
    ex_key = input("Exercise key: ").strip()
    ctrl   = registry.get(ex_key)
    if not ctrl:
        print(f"Not found: {ex_key}"); return None, None, None
    phases = ctrl.phases()
    for i, p in enumerate(phases):
        print(f"  [{i}] {p['id']}  —  {p['name']}")
    idx = input("Phase number: ").strip()
    try:
        phase = phases[int(idx)]
    except (ValueError, IndexError):
        print("Invalid."); return None, None, None
    return ex_key, ctrl, phase


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exercise", "-e", default=None)
    parser.add_argument("--phase",    "-p", default=None)
    parser.add_argument("--camera",   "-c", type=int, default=0)
    args = parser.parse_args()

    registry = ExerciseRegistry()

    if args.exercise:
        controller = registry.get(args.exercise)
        if not controller:
            print(f"Not found: {args.exercise}"); list_exercises(registry); return
        phase = None
        for p in controller.phases():
            if args.phase is None or p["id"] == args.phase:
                phase = p
                if args.phase: break
        if not phase:
            print(f"Phase not found: {args.phase}"); return
    else:
        args.exercise, controller, phase = pick_interactive(registry)
        if not controller: return

    print(f"\nTesting: [{args.exercise}]  {phase['name']}")
    print(f"Phase id: {phase['id']}  |  Target: {phase.get('target',0)} reps")
    print("Controls: Q=quit  R=reset  D=debug overlay  SPACE=freeze\n")

    # Force ACTIVE state — bypass video timestamp system
    controller._active_phase = phase
    controller._coach_state  = "ACTIVE"
    controller._video_pos    = phase.get("active", phase["start"]) + 1.0
    controller._on_phase_change(phase)

    camera   = Camera(args.camera)
    detector = PoseEngine("pose_landmarker_heavy.task")

    frozen       = False
    frozen_frame = None
    show_debug   = True    # debug overlay ON by default

    while True:
        if not frozen:
            frame = camera.read()
        else:
            frame = frozen_frame.copy()

        h, w, _ = frame.shape

        # pose detection
        rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        detector.detect_async(mp_img, int(time.time() * 1000))

        user_lm = None
        if detector.latest_result and detector.latest_result.pose_landmarks:
            user_lm = detector.latest_result.pose_landmarks[0]

        # run exercise logic
        is_error = False
        message  = "Stand in frame so camera can see you"

        if user_lm:
            is_error, message = controller.check_pose(user_lm, None, w, h, phase)
            controller.detect_rep(user_lm, w, h)
            frame = detector.draw_skeleton(frame, not is_error)

        # main HUD
        draw_main_hud(frame, phase["name"], message or "",
                      is_error, controller.rep_count,
                      phase.get("target", 0), frozen)

        # debug overlay
        if show_debug and user_lm:
            draw_debug_overlay(frame, user_lm, phase["id"], w, h)

        cv2.imshow(f"Pose Tester — {phase['name']}", frame)

        key = cv2.waitKey(1) & 0xFF
        if   key == ord("q"): break
        elif key == ord("r"):
            controller.rep_count = 0
            controller._on_phase_change(phase)
            print("Reps reset.")
        elif key == ord("d"):
            show_debug = not show_debug
            print(f"Debug overlay: {'ON' if show_debug else 'OFF'}")
        elif key == ord(" "):
            frozen = not frozen
            if frozen:
                frozen_frame = frame.copy()
                print("Frozen.")
            else:
                print("Resumed.")

    camera.release()
    cv2.destroyAllWindows()
    print(f"Final reps: {controller.rep_count}")


if __name__ == "__main__":
    main()