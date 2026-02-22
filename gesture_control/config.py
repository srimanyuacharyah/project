"""
config.py - Central configuration for Hand Gesture Control System
Modify values here to tune sensitivity, thresholds and enabled features.
"""

import pyautogui

# ─── Screen ────────────────────────────────────────────────────────────────────
SCREEN_W, SCREEN_H = pyautogui.size()
CAM_W, CAM_H = 1280, 720                  # Webcam capture resolution
FRAME_RATE = 30                            # Target FPS

# ─── Mouse ─────────────────────────────────────────────────────────────────────
MOUSE_SMOOTHING = 0.25                     # 0=snap, 1=no movement
MOUSE_SPEED = 2.5                          # Multiplier for cursor speed
CLICK_COOLDOWN = 0.4                       # Seconds between consecutive clicks
DRAG_THRESHOLD = 0.04                      # Normalised distance to start drag

# ─── Gesture Detection ─────────────────────────────────────────────────────────
PINCH_THRESHOLD = 0.06                     # Normalised dist for pinch detect
HOLD_SCREENSHOT = 1.5                      # Seconds to hold palm for screenshot
HOLD_LOCK = 2.0                            # Seconds to hold dual-fist for lock
HOLD_DRAW_TOGGLE = 1.0                     # Seconds to hold V for draw mode
SWIPE_THRESHOLD = 0.22                     # Normalised distance for swipe detect
SWIPE_SPEED_MIN = 0.4                      # Minimum speed (norm units/s) for swipe
SCROLL_SPEED = 15                          # Pixels per scroll tick

# ─── Volume / Brightness ───────────────────────────────────────────────────────
VOL_SENSITIVITY = 300                      # Hand travel pixels per 100% volume
BRIGHT_SENSITIVITY = 300                   # Hand travel pixels per 100% brightness
MIN_VOL_DIST  = 0.03                       # Min normalised hand move to act
MIN_BRIGHT_DIST = 0.03

# ─── Air Canvas ────────────────────────────────────────────────────────────────
CANVAS_COLORS = [
    (0, 0, 255),    # Red
    (0, 255, 0),    # Green
    (255, 0, 0),    # Blue
    (0, 255, 255),  # Yellow
    (255, 0, 255),  # Magenta
    (255, 255, 255),# White
]
CANVAS_BRUSH_SIZE = 5
CANVAS_ERASER_SIZE = 30

# ─── Feature Toggles ───────────────────────────────────────────────────────────
ENABLE_MOUSE          = True
ENABLE_CLICKS         = True
ENABLE_SCROLL         = True
ENABLE_DRAG           = True
ENABLE_VOLUME         = True
ENABLE_BRIGHTNESS     = True
ENABLE_MEDIA          = True
ENABLE_WINDOW_MGMT    = True
ENABLE_BROWSER_CTRL   = True
ENABLE_SYSTEM_KEYS    = True
ENABLE_AIR_CANVAS     = True
ENABLE_PRESENTATION   = False             # Enable for slideshow control

# ─── HUD ───────────────────────────────────────────────────────────────────────
HUD_FONT_SCALE = 0.7
HUD_THICKNESS  = 2
HUD_COLOR_ACTIVE   = (0, 255, 128)        # Bright green
HUD_COLOR_INACTIVE = (120, 120, 120)      # Gray
HUD_COLOR_WARNING  = (0, 120, 255)        # Orange
