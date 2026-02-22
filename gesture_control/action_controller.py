"""
action_controller.py
Translates gesture names into OS-level computer control actions.
Mouse, keyboard, volume, brightness, media, window management, screenshots.
"""

import time
import math
import ctypes
import os
import threading

import pyautogui
import numpy as np

# Optional imports with graceful fallback
try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    import comtypes
    _PYCAW_OK = True
except Exception:
    _PYCAW_OK = False
    print("[ActionController] pycaw not available — volume control disabled")

try:
    import screen_brightness_control as sbc
    _SBC_OK = True
except Exception:
    _SBC_OK = False
    print("[ActionController] screen-brightness-control not available")

try:
    import keyboard as kb
    _KB_OK = True
except Exception:
    _KB_OK = False
    print("[ActionController] keyboard module not available")

import config
from gesture_recognizer import GestureRecognizer as GR


class SmoothMouse:
    """Low-pass filter for smooth cursor movement."""
    def __init__(self):
        self.x, self.y = pyautogui.position()

    def move_to(self, target_x, target_y):
        a = config.MOUSE_SMOOTHING
        self.x = self.x * a + target_x * (1 - a)
        self.y = self.y * a + target_y * (1 - a)
        pyautogui.moveTo(int(self.x), int(self.y), duration=0)


class VolumeController:
    """Windows Core Audio volume control via pycaw."""

    def __init__(self):
        self._volume = None
        self._muted  = False
        if _PYCAW_OK:
            try:
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(
                    IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                self._volume = interface.QueryInterface(IAudioEndpointVolume)
            except Exception as e:
                print(f"[Volume] Init failed: {e}")

    def get(self):
        """Return volume 0..100."""
        if self._volume:
            scalar = self._volume.GetMasterVolumeLevelScalar()
            return int(scalar * 100)
        return 50

    def set(self, level: int):
        """Set volume 0..100."""
        level = max(0, min(100, level))
        if self._volume:
            self._volume.SetMasterVolumeLevelScalar(level / 100.0, None)

    def change(self, delta: int):
        self.set(self.get() + delta)

    def toggle_mute(self):
        if self._volume:
            self._muted = not self._muted
            self._volume.SetMute(int(self._muted), None)
        return self._muted

    def is_muted(self):
        return self._muted


class BrightnessController:
    """Screen brightness control via screen-brightness-control."""

    def get(self):
        if _SBC_OK:
            try:
                v = sbc.get_brightness(display=0)
                return v[0] if isinstance(v, list) else v
            except Exception:
                pass
        return 50

    def set(self, level: int):
        if _SBC_OK:
            try:
                sbc.set_brightness(max(0, min(100, level)), display=0)
            except Exception:
                pass

    def change(self, delta: int):
        self.set(self.get() + delta)


class ActionController:
    """
    Central controller: receives a gesture dict and performs the
    corresponding OS action.
    """

    def __init__(self, cam_w, cam_h):
        self.cam_w   = cam_w
        self.cam_h   = cam_h
        self.screen_w, self.screen_h = pyautogui.size()

        pyautogui.FAILSAFE    = False
        pyautogui.PAUSE       = 0

        self.smooth_mouse  = SmoothMouse()
        self.volume_ctrl   = VolumeController()
        self.bright_ctrl   = BrightnessController()

        # State
        self._dragging      = False
        self._last_action   = ""
        self._last_act_time = 0
        self._screenshot_pending = False

        # Status display info
        self.status_text    = "Ready"
        self.volume_level   = self.volume_ctrl.get()
        self.bright_level   = self.bright_ctrl.get()

    # ── Main dispatch ──────────────────────────────────────────────────────────
    def execute(self, gesture: dict, index_tip_pixel, tracker=None):
        """
        gesture  : dict from GestureRecognizer.recognize()
        index_tip_pixel : (px, py) of index fingertip in camera coords
        tracker  : HandTracker instance (for landmark access)
        """
        name = gesture["name"]
        ext  = gesture.get("extras", {})

        if name == GR.NONE:
            if self._dragging:
                pyautogui.mouseUp()
                self._dragging = False
            self.status_text = "Idle"
            return

        # ── Mouse move ────────────────────────────────────────────────────────
        if name == GR.MOUSE_MOVE and index_tip_pixel:
            tx, ty = self._cam_to_screen(*index_tip_pixel)
            self.smooth_mouse.move_to(tx, ty)
            self.status_text = "Mouse Move"
            return

        # ── Clicks ────────────────────────────────────────────────────────────
        if name == GR.LEFT_CLICK:
            pyautogui.click()
            self.status_text = "Left Click"
        elif name == GR.DOUBLE_CLICK:
            pyautogui.doubleClick()
            self.status_text = "Double Click"
        elif name == GR.RIGHT_CLICK:
            pyautogui.rightClick()
            self.status_text = "Right Click"
        elif name == GR.MIDDLE_CLICK:
            pyautogui.middleClick()
            self.status_text = "Middle Click"

        # ── Drag ─────────────────────────────────────────────────────────────
        elif name == GR.DRAG:
            if index_tip_pixel:
                tx, ty = self._cam_to_screen(*index_tip_pixel)
                if not self._dragging:
                    pyautogui.mouseDown()
                    self._dragging = True
                self.smooth_mouse.move_to(tx, ty)
                self.status_text = "Drag"

        # ── Scroll ───────────────────────────────────────────────────────────
        elif name == GR.SCROLL_UP:
            spd = ext.get("speed", 1)
            pyautogui.scroll(int(config.SCROLL_SPEED * min(spd * 3, 3)))
            self.status_text = "Scroll ↑"
        elif name == GR.SCROLL_DOWN:
            spd = ext.get("speed", 1)
            pyautogui.scroll(-int(config.SCROLL_SPEED * min(spd * 3, 3)))
            self.status_text = "Scroll ↓"
        elif name == GR.SCROLL_LEFT:
            pyautogui.hscroll(-config.SCROLL_SPEED)
            self.status_text = "Scroll ←"
        elif name == GR.SCROLL_RIGHT:
            pyautogui.hscroll(config.SCROLL_SPEED)
            self.status_text = "Scroll →"

        # ── Volume ────────────────────────────────────────────────────────────
        elif name == GR.VOLUME_UP:
            delta = ext.get("delta", 0)
            step  = max(1, int(abs(delta) * config.VOL_SENSITIVITY))
            self.volume_ctrl.change(step)
            self.volume_level = self.volume_ctrl.get()
            self.status_text  = f"Volume ▲ {self.volume_level}%"
        elif name == GR.VOLUME_DOWN:
            delta = ext.get("delta", 0)
            step  = max(1, int(abs(delta) * config.VOL_SENSITIVITY))
            self.volume_ctrl.change(-step)
            self.volume_level = self.volume_ctrl.get()
            self.status_text  = f"Volume ▼ {self.volume_level}%"
        elif name == GR.MUTE_TOGGLE:
            muted = self.volume_ctrl.toggle_mute()
            self.status_text = "🔇 Muted" if muted else "🔊 Unmuted"

        # ── Brightness ────────────────────────────────────────────────────────
        elif name == GR.BRIGHT_UP:
            delta = ext.get("delta", 0)
            step  = max(1, int(abs(delta) * config.BRIGHT_SENSITIVITY))
            self.bright_ctrl.change(step)
            self.bright_level = self.bright_ctrl.get()
            self.status_text  = f"Brightness ▲ {self.bright_level}%"
        elif name == GR.BRIGHT_DOWN:
            delta = ext.get("delta", 0)
            step  = max(1, int(abs(delta) * config.BRIGHT_SENSITIVITY))
            self.bright_ctrl.change(-step)
            self.bright_level = self.bright_ctrl.get()
            self.status_text  = f"Brightness ▼ {self.bright_level}%"

        # ── Media ─────────────────────────────────────────────────────────────
        elif name == GR.MEDIA_PLAYPAUSE:
            pyautogui.press("playpause")
            self.status_text = "▶/⏸ Play/Pause"
        elif name == GR.MEDIA_NEXT:
            pyautogui.press("nexttrack")
            self.status_text = "⏭ Next Track"
        elif name == GR.MEDIA_PREV:
            pyautogui.press("prevtrack")
            self.status_text = "⏮ Prev Track"
        elif name == GR.MEDIA_STOP:
            pyautogui.press("stop")
            self.status_text = "⏹ Stop"

        # ── Window management ─────────────────────────────────────────────────
        elif name == GR.WIN_SWITCHER:
            d = ext.get("dir", "right")
            pyautogui.hotkey("alt", "tab") if d == "right" else pyautogui.hotkey("alt", "shift", "tab")
            self.status_text = "Alt+Tab →" if d == "right" else "Alt+Tab ←"
        elif name == GR.WIN_MAXIMIZE:
            pyautogui.hotkey("win", "up")
            self.status_text = "⬜ Maximize"
        elif name == GR.WIN_MINIMIZE:
            pyautogui.hotkey("win", "down")
            self.status_text = "⬇ Minimize"
        elif name == GR.WIN_SNAP_LEFT:
            pyautogui.hotkey("win", "left")
            self.status_text = "⬅ Snap Left"
        elif name == GR.WIN_SNAP_RIGHT:
            pyautogui.hotkey("win", "right")
            self.status_text = "➡ Snap Right"
        elif name == GR.WIN_CLOSE:
            pyautogui.hotkey("alt", "f4")
            self.status_text = "✕ Close Window"
        elif name == GR.SHOW_DESKTOP:
            pyautogui.hotkey("win", "d")
            self.status_text = "🖥 Show Desktop"
        elif name == GR.TASK_VIEW:
            pyautogui.hotkey("win", "tab")
            self.status_text = "📋 Task View"

        # ── Browser ───────────────────────────────────────────────────────────
        elif name == GR.BROWSER_NEXT_TAB:
            pyautogui.hotkey("ctrl", "tab")
            self.status_text = "🌐 Next Tab"
        elif name == GR.BROWSER_PREV_TAB:
            pyautogui.hotkey("ctrl", "shift", "tab")
            self.status_text = "🌐 Prev Tab"
        elif name == GR.BROWSER_NEW_TAB:
            pyautogui.hotkey("ctrl", "t")
            self.status_text = "🌐 New Tab"
        elif name == GR.BROWSER_CLOSE_TAB:
            pyautogui.hotkey("ctrl", "w")
            self.status_text = "🌐 Close Tab"
        elif name == GR.BROWSER_REFRESH:
            pyautogui.press("f5")
            self.status_text = "🔄 Refresh"

        # ── System shortcuts ──────────────────────────────────────────────────
        elif name == GR.KEY_COPY:
            pyautogui.hotkey("ctrl", "c")
            self.status_text = "📋 Copy"
        elif name == GR.KEY_PASTE:
            pyautogui.hotkey("ctrl", "v")
            self.status_text = "📋 Paste"
        elif name == GR.KEY_UNDO:
            pyautogui.hotkey("ctrl", "z")
            self.status_text = "↩ Undo"
        elif name == GR.KEY_SELECT_ALL:
            pyautogui.hotkey("ctrl", "a")
            self.status_text = "☑ Select All"

        # ── Screenshot ────────────────────────────────────────────────────────
        elif name == GR.SCREENSHOT:
            self._take_screenshot()

        # ── Lock screen ───────────────────────────────────────────────────────
        elif name == GR.LOCK_SCREEN:
            self.status_text = "🔒 Locking..."
            ctypes.windll.user32.LockWorkStation()

        # ── Zoom ──────────────────────────────────────────────────────────────
        elif name == GR.ZOOM_IN:
            pyautogui.hotkey("ctrl", "equal")
            self.status_text = "🔍 Zoom In"
        elif name == GR.ZOOM_OUT:
            pyautogui.hotkey("ctrl", "minus")
            self.status_text = "🔎 Zoom Out"

        # ── Presentation ──────────────────────────────────────────────────────
        elif name == GR.SLIDE_NEXT:
            pyautogui.press("right")
            self.status_text = "▶ Next Slide"
        elif name == GR.SLIDE_PREV:
            pyautogui.press("left")
            self.status_text = "◀ Prev Slide"

        # ── Draw toggle (handled by main.py) ──────────────────────────────────
        elif name == GR.DRAW_TOGGLE:
            self.status_text = "✏ Draw Mode Toggle"
        elif name == GR.MUTE_TOGGLE:
            pass  # already handled above

    # ── Helpers ────────────────────────────────────────────────────────────────
    def _cam_to_screen(self, px, py):
        """Convert camera pixel coords to screen coords with scaling."""
        # Flip x (mirror mode)
        px = self.cam_w - px
        sx = int(np.interp(px, [0, self.cam_w], [0, self.screen_w]))
        sy = int(np.interp(py, [0, self.cam_h], [0, self.screen_h]))
        return sx, sy

    def _take_screenshot(self):
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        fname   = time.strftime("screenshot_%Y%m%d_%H%M%S.png")
        path    = os.path.join(desktop, fname)
        img     = pyautogui.screenshot()
        img.save(path)
        self.status_text = f"📸 Saved: {fname}"
        print(f"[Screenshot] Saved to {path}")
