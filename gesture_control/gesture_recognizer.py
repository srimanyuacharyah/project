"""
gesture_recognizer.py
Classifies hand gestures from HandTracker landmark data.
Uses purely geometric rules — no ML training required.
"""

import time
import math
import config
from hand_tracker import HandTracker


class MotionTracker:
    """Tracks position history to detect swipe direction and speed."""

    def __init__(self, window=0.6):
        self.history = []   # list of (time, x_norm, y_norm)
        self.window = window

    def update(self, x, y):
        now = time.time()
        self.history.append((now, x, y))
        self.history = [(t, px, py) for t, px, py in self.history
                        if now - t < self.window]

    def get_delta(self):
        """Returns (dx, dy) over the tracking window."""
        if len(self.history) < 3:
            return 0.0, 0.0
        _, x0, y0 = self.history[0]
        _, x1, y1 = self.history[-1]
        return x1 - x0, y1 - y0

    def get_speed(self):
        """Returns movement speed (norm units/s)."""
        if len(self.history) < 2:
            return 0.0
        t0, x0, y0 = self.history[0]
        t1, x1, y1 = self.history[-1]
        dt = t1 - t0 or 0.001
        return math.hypot(x1 - x0, y1 - y0) / dt

    def reset(self):
        self.history.clear()


class HoldTimer:
    """Tracks how long a condition has been continuously True."""

    def __init__(self, threshold):
        self.threshold = threshold
        self._start = None

    def update(self, active: bool) -> bool:
        """Returns True when condition has been held >= threshold seconds."""
        if active:
            if self._start is None:
                self._start = time.time()
            return (time.time() - self._start) >= self.threshold
        else:
            self._start = None
            return False

    def progress(self) -> float:
        """0..1 progress toward hold threshold."""
        if self._start is None:
            return 0.0
        return min(1.0, (time.time() - self._start) / self.threshold)


class GestureRecognizer:
    """
    Main gesture classifier.  Call `recognize(tracker)` each frame.
    Returns a dict: {name, confidence, hand, extras}
    """

    NONE = "NONE"

    # ── Gesture name constants ──────────────────────────────────────────────────
    MOUSE_MOVE         = "MOUSE_MOVE"
    LEFT_CLICK         = "LEFT_CLICK"
    RIGHT_CLICK        = "RIGHT_CLICK"
    MIDDLE_CLICK       = "MIDDLE_CLICK"
    DOUBLE_CLICK       = "DOUBLE_CLICK"
    DRAG               = "DRAG"
    SCROLL_UP          = "SCROLL_UP"
    SCROLL_DOWN        = "SCROLL_DOWN"
    SCROLL_LEFT        = "SCROLL_LEFT"
    SCROLL_RIGHT       = "SCROLL_RIGHT"
    VOLUME_UP          = "VOLUME_UP"
    VOLUME_DOWN        = "VOLUME_DOWN"
    MUTE_TOGGLE        = "MUTE_TOGGLE"
    BRIGHT_UP          = "BRIGHT_UP"
    BRIGHT_DOWN        = "BRIGHT_DOWN"
    MEDIA_PLAYPAUSE    = "MEDIA_PLAYPAUSE"
    MEDIA_NEXT         = "MEDIA_NEXT"
    MEDIA_PREV         = "MEDIA_PREV"
    MEDIA_STOP         = "MEDIA_STOP"
    WIN_MAXIMIZE       = "WIN_MAXIMIZE"
    WIN_MINIMIZE       = "WIN_MINIMIZE"
    WIN_CLOSE          = "WIN_CLOSE"
    WIN_SWITCHER       = "WIN_SWITCHER"   # Alt+Tab swipe
    WIN_SNAP_LEFT      = "WIN_SNAP_LEFT"
    WIN_SNAP_RIGHT     = "WIN_SNAP_RIGHT"
    SHOW_DESKTOP       = "SHOW_DESKTOP"
    TASK_VIEW          = "TASK_VIEW"
    BROWSER_NEXT_TAB   = "BROWSER_NEXT_TAB"
    BROWSER_PREV_TAB   = "BROWSER_PREV_TAB"
    BROWSER_NEW_TAB    = "BROWSER_NEW_TAB"
    BROWSER_CLOSE_TAB  = "BROWSER_CLOSE_TAB"
    BROWSER_REFRESH    = "BROWSER_REFRESH"
    KEY_COPY           = "KEY_COPY"
    KEY_PASTE          = "KEY_PASTE"
    KEY_UNDO           = "KEY_UNDO"
    KEY_SELECT_ALL     = "KEY_SELECT_ALL"
    LOCK_SCREEN        = "LOCK_SCREEN"
    SCREENSHOT         = "SCREENSHOT"
    DRAW_TOGGLE        = "DRAW_TOGGLE"
    SLIDE_NEXT         = "SLIDE_NEXT"
    SLIDE_PREV         = "SLIDE_PREV"
    ZOOM_IN            = "ZOOM_IN"
    ZOOM_OUT           = "ZOOM_OUT"

    def __init__(self):
        # Motion trackers per hand
        self._motion = [MotionTracker(), MotionTracker()]

        # Hold timers
        self._hold_screenshot  = HoldTimer(config.HOLD_SCREENSHOT)
        self._hold_lock        = HoldTimer(config.HOLD_LOCK)
        self._hold_draw        = HoldTimer(config.HOLD_DRAW_TOGGLE)
        self._hold_mute        = HoldTimer(1.5)

        # Cooldowns
        self._last_click_time  = 0
        self._last_scroll_time = 0
        self._last_swipe_time  = 0
        self._last_media_time  = 0
        self._last_tab_time    = 0

        # State
        self._prev_pinch_y     = None    # for volume/brightness
        self._drag_active      = False
        self._double_click_pending = False
        self._last_pinch_time  = 0

    # ── Helpers ────────────────────────────────────────────────────────────────
    @staticmethod
    def _now():
        return time.time()

    def _cd(self, attr, seconds):
        """Return True if cooldown has elapsed, reset timer."""
        if self._now() - getattr(self, attr) >= seconds:
            setattr(self, attr, self._now())
            return True
        return False

    def _fingers(self, tracker, hi=0):
        return tracker.fingers_up(hi)

    def _pinch(self, tracker, tip_a, tip_b, hi=0):
        d = tracker.get_distance(tip_a, tip_b, hi)
        return d is not None and d < config.PINCH_THRESHOLD

    # ── Main recognizer ────────────────────────────────────────────────────────
    def recognize(self, tracker: HandTracker) -> dict:
        """
        Runs all gesture checks in priority order.
        Returns highest-priority detected gesture dict.
        """
        n = tracker.count_hands()
        if n == 0:
            self._prev_pinch_y = None
            self._drag_active = False
            return {"name": self.NONE, "confidence": 1.0, "hand": None, "extras": {}}

        result = self._check_gestures(tracker, n)
        return result

    def _check_gestures(self, tracker, n_hands):
        HT = HandTracker
        fingers0 = self._fingers(tracker, 0)
        all_up0  = sum(fingers0)

        # Update motion for primary hand
        lms0 = tracker.get_landmarks(0)
        if lms0:
            cx, cy = lms0[HT.INDEX_TIP][0], lms0[HT.INDEX_TIP][1]
            self._motion[0].update(cx, cy)

        # ── DUAL HAND gestures (priority 0) ────────────────────────────────────
        if n_hands == 2:
            res = self._dual_hand(tracker, fingers0)
            if res:
                return res

        # ── HOLD gestures (priority 1) ─────────────────────────────────────────
        # Screenshot: open palm (all 5 fingers up)
        if config.ENABLE_SYSTEM_KEYS and all_up0 == 5 and fingers0[0] == 1:
            held = self._hold_screenshot.update(True)
            if held:
                return self._result(self.SCREENSHOT, 1.0, "primary",
                                    {"progress": 1.0})
            return self._result(self.MOUSE_MOVE, 0.6, "primary",
                                {"hold_progress": self._hold_screenshot.progress(),
                                 "hint": "Hold palm for screenshot"})
        else:
            self._hold_screenshot.update(False)

        # Mute: fist held
        if config.ENABLE_VOLUME and all_up0 == 0:
            held = self._hold_mute.update(True)
            if held:
                return self._result(self.MUTE_TOGGLE, 1.0, "primary", {})
        else:
            self._hold_mute.update(False)

        # Draw toggle: V (index+middle up, rest down) held
        if (config.ENABLE_AIR_CANVAS
                and fingers0 == [0, 1, 1, 0, 0]):
            held = self._hold_draw.update(True)
            if held:
                return self._result(self.DRAW_TOGGLE, 1.0, "primary", {})
            extras = {"hint": "Hold V to toggle drawing",
                      "hold_progress": self._hold_draw.progress()}
            # Fall through to SCROLL check below too, but show hint
        else:
            self._hold_draw.update(False)

        # ── SWIPE gestures (priority 2) ────────────────────────────────────────
        swipe = self._check_swipe(tracker, fingers0, all_up0)
        if swipe:
            return swipe

        # ── VOLUME / BRIGHTNESS via three-finger pinch+move ────────────────────
        vol_bright = self._check_vol_bright(tracker, fingers0)
        if vol_bright:
            return vol_bright

        # ── CLICKS ─────────────────────────────────────────────────────────────
        click_res = self._check_clicks(tracker, fingers0, all_up0)
        if click_res:
            return click_res

        # ── SCROLL ─────────────────────────────────────────────────────────────
        scroll_res = self._check_scroll(tracker, fingers0, all_up0)
        if scroll_res:
            return scroll_res

        # ── DRAG ───────────────────────────────────────────────────────────────
        if config.ENABLE_DRAG and all_up0 == 0:
            self._drag_active = True
            return self._result(self.DRAG, 0.9, "primary", {})
        else:
            if self._drag_active:
                self._drag_active = False

        # ── MEDIA ──────────────────────────────────────────────────────────────
        media_res = self._check_media(tracker, fingers0, all_up0)
        if media_res:
            return media_res

        # ── SYSTEM KEYS ────────────────────────────────────────────────────────
        sys_res = self._check_system_keys(fingers0, all_up0)
        if sys_res:
            return sys_res

        # ── MOUSE MOVE (default) ───────────────────────────────────────────────
        if config.ENABLE_MOUSE and fingers0[1] == 1 and all_up0 <= 2:
            return self._result(self.MOUSE_MOVE, 0.9, "primary", {})

        return self._result(self.NONE, 1.0, None, {})

    def _dual_hand(self, tracker, fingers0):
        HT = HandTracker
        fingers1 = self._fingers(tracker, 1)
        all1 = sum(fingers1)
        all0 = sum(fingers0)

        # Lock screen: both fists held
        if all0 == 0 and all1 == 0 and config.ENABLE_SYSTEM_KEYS:
            held = self._hold_lock.update(True)
            if held:
                return self._result(self.LOCK_SCREEN, 1.0, "both",
                                    {"hold_progress": 1.0})
            return self._result(self.NONE, 0.5, "both",
                                {"hint": "Hold both fists to lock",
                                 "hold_progress": self._hold_lock.progress()})
        else:
            self._hold_lock.update(False)

        # Zoom: both hands with all fingers — track wrist distance
        if all0 >= 4 and all1 >= 4:
            w0 = tracker.get_landmarks(0)[HT.WRIST]
            w1 = tracker.get_landmarks(1)[HT.WRIST]
            dist = math.hypot(w0[0]-w1[0], w0[1]-w1[1])
            dx, _ = self._motion[0].get_delta()
            if abs(dx) > config.SWIPE_THRESHOLD * 0.5:
                gesture = self.ZOOM_IN if dx > 0 else self.ZOOM_OUT
                return self._result(gesture, 0.85, "both",
                                    {"dist": dist})

        return None

    def _check_swipe(self, tracker, fingers0, all_up0):
        dx, dy = self._motion[0].get_delta()
        speed  = self._motion[0].get_speed()

        if speed < config.SWIPE_SPEED_MIN:
            return None

        swipe_edge = config.SWIPE_THRESHOLD

        if not self._cd("_last_swipe_time", 0.7):
            return None

        # Open palm swipe → Window switcher / app switch
        if config.ENABLE_WINDOW_MGMT and all_up0 >= 4:
            if dx > swipe_edge:
                self._motion[0].reset()
                return self._result(self.WIN_SWITCHER, 0.9, "primary",
                                    {"dir": "right"})
            if dx < -swipe_edge:
                self._motion[0].reset()
                return self._result(self.WIN_SWITCHER, 0.9, "primary",
                                    {"dir": "left"})
            # Swipe up → maximize, down → minimize
            if dy < -swipe_edge and fingers0[1] == 1:
                self._motion[0].reset()
                return self._result(self.WIN_MAXIMIZE, 0.85, "primary", {})
            if dy > swipe_edge and fingers0[1] == 1:
                self._motion[0].reset()
                return self._result(self.WIN_MINIMIZE, 0.85, "primary", {})

        # Crossed fingers (index+middle up, rest folded) → Browser tab
        if config.ENABLE_BROWSER_CTRL and fingers0 == [0, 1, 1, 0, 0]:
            if dx > swipe_edge:
                self._motion[0].reset()
                return self._result(self.BROWSER_NEXT_TAB, 0.85, "primary", {})
            if dx < -swipe_edge:
                self._motion[0].reset()
                return self._result(self.BROWSER_PREV_TAB, 0.85, "primary", {})

        # Index only swipe up/down → window snap
        if config.ENABLE_WINDOW_MGMT and fingers0[1] == 1 and all_up0 == 1:
            if dx > swipe_edge:
                self._motion[0].reset()
                return self._result(self.WIN_SNAP_RIGHT, 0.8, "primary", {})
            if dx < -swipe_edge:
                self._motion[0].reset()
                return self._result(self.WIN_SNAP_LEFT, 0.8, "primary", {})

        # Media swipe (index+pinky up = rock hand)
        if (config.ENABLE_MEDIA
                and fingers0[0] == 1 and fingers0[1] == 0
                and fingers0[4] == 1):
            if dx > swipe_edge:
                self._motion[0].reset()
                return self._result(self.MEDIA_NEXT, 0.85, "primary", {})
            if dx < -swipe_edge:
                self._motion[0].reset()
                return self._result(self.MEDIA_PREV, 0.85, "primary", {})

        # 3 fingers up swipe up → Task view
        if (config.ENABLE_WINDOW_MGMT
                and sum(fingers0[1:4]) == 3
                and dy < -swipe_edge):
            self._motion[0].reset()
            return self._result(self.TASK_VIEW, 0.8, "primary", {})

        # 5 fingers spread swipe up → Show desktop
        if (config.ENABLE_WINDOW_MGMT and all_up0 == 5
                and dy < -swipe_edge):
            self._motion[0].reset()
            return self._result(self.SHOW_DESKTOP, 0.8, "primary", {})

        # Presentation mode swipes (index only)
        if (config.ENABLE_PRESENTATION and fingers0[1] == 1 and all_up0 == 1):
            if dx > swipe_edge:
                self._motion[0].reset()
                return self._result(self.SLIDE_NEXT, 0.85, "primary", {})
            if dx < -swipe_edge:
                self._motion[0].reset()
                return self._result(self.SLIDE_PREV, 0.85, "primary", {})

        return None

    def _check_vol_bright(self, tracker, fingers0):
        HT = HandTracker
        # Volume: pinch (index+thumb) with middle up
        vol_mode    = (fingers0[0]==1 and fingers0[1]==1 and fingers0[2]==0
                       and fingers0[3]==0)
        bright_mode = (fingers0[0]==1 and fingers0[1]==1 and fingers0[2]==1
                       and fingers0[3]==0 and fingers0[4]==0)

        lms = tracker.get_landmarks(0)
        if not lms:
            return None

        cur_y = lms[HT.WRIST][1]

        if vol_mode and config.ENABLE_VOLUME:
            if self._prev_pinch_y is not None:
                dy = self._prev_pinch_y - cur_y
                if abs(dy) > config.MIN_VOL_DIST:
                    self._prev_pinch_y = cur_y
                    return self._result(
                        self.VOLUME_UP if dy > 0 else self.VOLUME_DOWN,
                        0.85, "primary", {"delta": dy})
            self._prev_pinch_y = cur_y
            return None

        if bright_mode and config.ENABLE_BRIGHTNESS:
            if self._prev_pinch_y is not None:
                dy = self._prev_pinch_y - cur_y
                if abs(dy) > config.MIN_BRIGHT_DIST:
                    self._prev_pinch_y = cur_y
                    return self._result(
                        self.BRIGHT_UP if dy > 0 else self.BRIGHT_DOWN,
                        0.85, "primary", {"delta": dy})
            self._prev_pinch_y = cur_y
            return None

        if not vol_mode and not bright_mode:
            self._prev_pinch_y = None
        return None

    def _check_clicks(self, tracker, fingers0, all_up0):
        HT = HandTracker
        if not config.ENABLE_CLICKS:
            return None

        # Left click: index+thumb pinch
        if self._pinch(tracker, HT.INDEX_TIP, HT.THUMB_TIP, 0):
            now = self._now()
            dt  = now - self._last_pinch_time
            self._last_pinch_time = now
            if self._cd("_last_click_time", config.CLICK_COOLDOWN * 0.5):
                if dt < 0.35:
                    return self._result(self.DOUBLE_CLICK, 1.0, "primary", {})
                return self._result(self.LEFT_CLICK, 1.0, "primary", {})

        # Right click: middle+thumb pinch
        if self._pinch(tracker, HT.MIDDLE_TIP, HT.THUMB_TIP, 0):
            if self._cd("_last_click_time", config.CLICK_COOLDOWN):
                return self._result(self.RIGHT_CLICK, 1.0, "primary", {})

        # Middle click: ring+thumb pinch
        if self._pinch(tracker, HT.RING_TIP, HT.THUMB_TIP, 0):
            if self._cd("_last_click_time", config.CLICK_COOLDOWN):
                return self._result(self.MIDDLE_CLICK, 1.0, "primary", {})

        return None

    def _check_scroll(self, tracker, fingers0, all_up0):
        if not config.ENABLE_SCROLL:
            return None
        # Two fingers up (index+middle), thumb folded
        if fingers0[1] == 1 and fingers0[2] == 1 and fingers0[0] == 0:
            _, dy = self._motion[0].get_delta()
            speed = self._motion[0].get_speed()
            if speed > 0.15 and abs(dy) > 0.04:
                if self._cd("_last_scroll_time", 0.08):
                    if dy < 0:
                        return self._result(self.SCROLL_UP, 0.9, "primary",
                                            {"speed": speed})
                    else:
                        return self._result(self.SCROLL_DOWN, 0.9, "primary",
                                            {"speed": speed})
        return None

    def _check_media(self, tracker, fingers0, all_up0):
        if not config.ENABLE_MEDIA:
            return None
        if not self._cd("_last_media_time", 0.8):
            return None

        # Thumbs up: thumb up only
        if fingers0[0] == 1 and all_up0 == 1:
            return self._result(self.MEDIA_PLAYPAUSE, 0.85, "primary", {})

        # Open palm + thumb: stop
        if all_up0 == 5:
            return None  # handled by screenshot hold above

        return None

    def _check_system_keys(self, fingers0, all_up0):
        if not config.ENABLE_SYSTEM_KEYS:
            return None

        # Copy: V sign (index+middle up), tap (no hold)
        if fingers0 == [0, 1, 1, 0, 0]:
            return None   # handled by draw toggle hold

        # Paste: index+middle+ring up
        if fingers0 == [0, 1, 1, 1, 0]:
            if self._cd("_last_swipe_time", 0.8):
                return self._result(self.KEY_PASTE, 0.8, "primary", {})

        # Undo: pinky+index up (hang loose without thumb)
        if fingers0 == [0, 1, 0, 0, 1]:
            if self._cd("_last_swipe_time", 0.8):
                return self._result(self.KEY_UNDO, 0.8, "primary", {})

        # Select All: all fingers up (5)
        if all_up0 == 5:
            return None  # handled by screenshot

        return None

    @staticmethod
    def _result(name, confidence, hand, extras):
        return {"name": name, "confidence": confidence,
                "hand": hand, "extras": extras}

    def hold_progress(self, gesture_name):
        """Return 0..1 progress for hold gestures (for HUD bar)."""
        if gesture_name == GestureRecognizer.SCREENSHOT:
            return self._hold_screenshot.progress()
        if gesture_name == GestureRecognizer.LOCK_SCREEN:
            return self._hold_lock.progress()
        if gesture_name == GestureRecognizer.DRAW_TOGGLE:
            return self._hold_draw.progress()
        return 0.0
