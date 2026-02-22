"""
main.py  —  Hand Gesture Computer Control
Real-time webcam loop: Detect → Recognize → Act

Controls:
  Q  -  Quit
  P  -  Pause / Resume gesture detection
  S  -  Open Settings dashboard
  C  -  Clear air canvas
  E  -  Toggle eraser (draw mode)
  N  -  Next color (draw mode)
  D  -  Toggle draw mode
  H  -  Toggle HUD
"""

import cv2
import numpy as np
import time
import sys

import config
from hand_tracker import HandTracker
from gesture_recognizer import GestureRecognizer, GestureRecognizer as GR
from action_controller import ActionController
from air_canvas import AirCanvas
import settings_ui


# ── Colour palette ─────────────────────────────────────────────────────────────
HUD_BG      = (20, 20, 35)
HUD_GREEN   = (0, 255, 128)
HUD_ORANGE  = (0, 165, 255)
HUD_RED     = (0, 80, 220)
HUD_GRAY    = (140, 140, 140)
HUD_WHITE   = (230, 230, 230)


def draw_hud(frame, gesture, action_ctrl, canvas, paused, show_hud, fps):
    """Render the HUD overlay on the camera frame."""
    if not show_hud:
        return frame

    h, w = frame.shape[:2]
    name = gesture["name"]
    conf = gesture.get("confidence", 0)

    # ── Semi-transparent side panel ────────────────────────────────────────────
    panel_w = 300
    overlay = frame.copy()
    cv2.rectangle(overlay, (w - panel_w, 0), (w, h), HUD_BG, -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

    x0 = w - panel_w + 12
    y  = 32

    # Title
    cv2.putText(frame, "GESTURE CONTROL", (x0, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.58, HUD_GREEN, 2)
    y += 22
    cv2.line(frame, (x0, y), (w - 12, y), HUD_GREEN, 1)
    y += 18

    # FPS
    fps_color = HUD_GREEN if fps >= 25 else HUD_ORANGE if fps >= 15 else HUD_RED
    cv2.putText(frame, f"FPS: {fps:.0f}", (x0, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, fps_color, 1)
    y += 22

    # Paused banner
    if paused:
        cv2.putText(frame, "⏸ PAUSED", (x0, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, HUD_ORANGE, 2)
        y += 28

    # Current gesture
    cv2.putText(frame, "Gesture:", (x0, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, HUD_GRAY, 1)
    y += 20
    g_color = HUD_GREEN if name != GR.NONE else HUD_GRAY
    display_name = name.replace("_", " ")
    cv2.putText(frame, display_name[:22], (x0, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.62, g_color, 2)
    y += 26

    # Confidence bar
    if name != GR.NONE:
        bar_len = int((panel_w - 24) * conf)
        cv2.rectangle(frame, (x0, y), (x0 + panel_w - 24, y + 8), (50, 50, 70), -1)
        cv2.rectangle(frame, (x0, y), (x0 + bar_len, y + 8), HUD_GREEN, -1)
        cv2.putText(frame, f"{conf*100:.0f}%", (x0 + bar_len + 4, y + 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, HUD_GRAY, 1)
    y += 20

    # Action status
    y += 6
    cv2.line(frame, (x0, y), (w - 12, y), (50, 50, 70), 1)
    y += 14
    cv2.putText(frame, "Action:", (x0, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, HUD_GRAY, 1)
    y += 20
    cv2.putText(frame, action_ctrl.status_text[:24], (x0, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.58, HUD_WHITE, 1)
    y += 28

    # Volume bar
    y += 4
    cv2.putText(frame, f"Vol: {action_ctrl.volume_level}%", (x0, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, HUD_GRAY, 1)
    y += 14
    vbar = int((panel_w - 24) * action_ctrl.volume_level / 100)
    cv2.rectangle(frame, (x0, y), (x0 + panel_w - 24, y + 7), (50, 50, 70), -1)
    cv2.rectangle(frame, (x0, y), (x0 + vbar, y + 7), (100, 200, 255), -1)
    y += 14

    # Brightness bar
    cv2.putText(frame, f"Bright: {action_ctrl.bright_level}%", (x0, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, HUD_GRAY, 1)
    y += 14
    bbar = int((panel_w - 24) * action_ctrl.bright_level / 100)
    cv2.rectangle(frame, (x0, y), (x0 + panel_w - 24, y + 7), (50, 50, 70), -1)
    cv2.rectangle(frame, (x0, y), (x0 + bbar, y + 7), (255, 200, 80), -1)
    y += 20

    # Hold progress (screenshot / lock)
    hold_g = [GR.SCREENSHOT, GR.LOCK_SCREEN, GR.DRAW_TOGGLE]
    if name in hold_g:
        prog = gesture.get("extras", {}).get("hold_progress",
               gesture.get("extras", {}).get("progress", 0))
        y += 6
        cv2.putText(frame, "Hold progress:", (x0, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, HUD_GRAY, 1)
        y += 14
        pbar = int((panel_w - 24) * prog)
        cv2.rectangle(frame, (x0, y), (x0 + panel_w - 24, y + 8), (50, 50, 70), -1)
        cv2.rectangle(frame, (x0, y), (x0 + pbar, y + 8), HUD_ORANGE, -1)
        y += 18

    # Draw mode indicator
    y += 6
    if canvas.is_active():
        cv2.putText(frame, "✏ DRAW MODE ON", (x0, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, HUD_ORANGE, 2)
        y += 22

    # Keys hint (bottom)
    hints = ["Q:Quit  P:Pause  S:Settings",
             "D:Draw  C:Clear  H:HUD"]
    y = h - 38
    for hint in hints:
        cv2.putText(frame, hint, (x0, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, HUD_GRAY, 1)
        y += 16

    return frame


def draw_finger_dot(frame, tip_px, gesture_name):
    """Draw a marker at the index fingertip."""
    if tip_px is None:
        return
    color = HUD_GREEN
    if gesture_name in (GR.LEFT_CLICK, GR.DOUBLE_CLICK):
        color = (0, 255, 255)
    elif gesture_name in (GR.RIGHT_CLICK,):
        color = HUD_ORANGE
    elif gesture_name == GR.DRAG:
        color = HUD_RED
    cv2.circle(frame, tip_px, 10, color, -1)
    cv2.circle(frame, tip_px, 12, HUD_WHITE, 2)


def main():
    print("=" * 55)
    print("  ✋  Hand Gesture Computer Control — Starting up  ")
    print("=" * 55)

    # ── Webcam ─────────────────────────────────────────────────────────────────
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Cannot open webcam. Exiting.")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  config.CAM_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAM_H)
    cap.set(cv2.CAP_PROP_FPS,          config.FRAME_RATE)

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[Camera] Resolution: {actual_w}×{actual_h}")

    # ── Core objects ───────────────────────────────────────────────────────────
    tracker     = HandTracker(max_hands=2)
    recognizer  = GestureRecognizer()
    controller  = ActionController(actual_w, actual_h)
    canvas      = AirCanvas(actual_w, actual_h)
    settings_launched = False

    # ── State ──────────────────────────────────────────────────────────────────
    paused   = False
    show_hud = True
    prev_time = time.time()
    fps       = 0

    # ── Window ─────────────────────────────────────────────────────────────────
    window_name = "✋ Gesture Control — Press Q to Quit"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, actual_w, actual_h)

    print("\nControls:")
    print("  Q — Quit   P — Pause   S — Settings")
    print("  D — Draw mode   C — Clear canvas")
    print("  E — Eraser   N — Next color   H — Toggle HUD\n")

    # ── Main loop ──────────────────────────────────────────────────────────────
    while True:
        ret, frame = cap.read()
        if not ret:
            print("[WARNING] Frame not received. Retrying…")
            continue

        # Mirror the frame
        frame = cv2.flip(frame, 1)

        # ── Hand detection ─────────────────────────────────────────────────────
        tracker.process(frame)

        gesture = {"name": GR.NONE, "confidence": 0,
                   "hand": None, "extras": {}}

        if not paused:
            gesture = recognizer.recognize(tracker)
            index_tip = tracker.index_tip(0)

            # ── Air canvas drawing ─────────────────────────────────────────────
            if canvas.is_active():
                if tracker.count_hands() > 0:
                    fingers = tracker.fingers_up(0)
                    # Only draw when index up, others folded
                    if fingers[1] == 1 and fingers[2] == 0:
                        if index_tip:
                            canvas.draw_point(*index_tip)
                    else:
                        canvas.lift_pen()
                else:
                    canvas.lift_pen()
                # Don't run mouse control in draw mode
                gesture = {"name": GR.NONE, "confidence": 1.0,
                           "hand": None, "extras": {}}
            else:
                # ── Toggle draw mode via gesture ──────────────────────────────
                if gesture["name"] == GR.DRAW_TOGGLE and config.ENABLE_AIR_CANVAS:
                    active = canvas.toggle()
                    controller.status_text = (
                        "✏ Draw Mode ON" if active else "✏ Draw Mode OFF")
                    gesture = {"name": GR.NONE, "confidence": 1.0,
                               "hand": None, "extras": {}}
                else:
                    # ── Execute action ────────────────────────────────────────
                    controller.execute(gesture, index_tip, tracker)

        # ── Draw landmarks ─────────────────────────────────────────────────────
        tracker.draw_landmarks(frame)
        if not paused:
            index_tip = tracker.index_tip(0)
            draw_finger_dot(frame, index_tip, gesture["name"])

        # ── Air canvas overlay ─────────────────────────────────────────────────
        if canvas.is_active():
            frame = canvas.overlay_on(frame)
            frame = canvas.draw_ui(frame)

        # ── FPS ────────────────────────────────────────────────────────────────
        now  = time.time()
        fps  = 0.9 * fps + 0.1 * (1.0 / max(now - prev_time, 1e-6))
        prev_time = now

        # ── HUD ───────────────────────────────────────────────────────────────
        frame = draw_hud(frame, gesture, controller, canvas, paused, show_hud, fps)

        # ── Paused overlay ────────────────────────────────────────────────────
        if paused:
            cv2.putText(frame, "PAUSED — Press P to resume",
                        (20, frame.shape[0] // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, HUD_ORANGE, 3)

        cv2.imshow(window_name, frame)

        # ── Key handling ──────────────────────────────────────────────────────
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            print("\n[Exit] Quitting…")
            break
        elif key == ord('p'):
            paused = not paused
            print(f"[Control] {'Paused' if paused else 'Resumed'}")
        elif key == ord('s'):
            if not settings_launched:
                settings_ui.launch_settings()
                settings_launched = True
                print("[Settings] Dashboard launched")
        elif key == ord('d'):
            active = canvas.toggle()
            controller.status_text = (
                "✏ Draw Mode ON" if active else "✏ Draw Mode OFF")
            print(f"[Draw] {'Enabled' if active else 'Disabled'}")
        elif key == ord('c'):
            canvas.clear()
            print("[Draw] Canvas cleared")
        elif key == ord('e'):
            canvas.toggle_eraser()
        elif key == ord('n'):
            canvas.next_color()
        elif key == ord('h'):
            show_hud = not show_hud
        elif key == ord('v'):
            # Save drawing to desktop
            path = canvas.save()
            print(f"[Draw] Saved: {path}")

    cap.release()
    cv2.destroyAllWindows()
    print("[Done] Gesture Control stopped.")


if __name__ == "__main__":
    main()
