"""
air_canvas.py
Transparent air drawing overlay.
Draws on a full-screen numpy canvas using index finger tip.
"""

import cv2
import numpy as np
import time
import os
import config
from hand_tracker import HandTracker


class AirCanvas:
    """
    Maintains a drawing canvas and renders it as an overlay in the HUD.
    Call `update()` each frame; the returned annotated frame contains drawing.
    """

    def __init__(self, width, height):
        self.w = width
        self.h = height
        self.canvas      = np.zeros((height, width, 3), dtype=np.uint8)
        self.color_idx   = 0
        self.brush_size  = config.CANVAS_BRUSH_SIZE
        self.eraser_size = config.CANVAS_ERASER_SIZE
        self._prev_point = None
        self._eraser_mode = False
        self._active     = False

    def activate(self, active: bool):
        self._active = active
        if not active:
            self._prev_point = None

    def is_active(self):
        return self._active

    def toggle(self):
        self._active = not self._active
        self._prev_point = None
        return self._active

    def draw_point(self, x, y):
        if not self._active:
            return
        pt = (x, y)
        color = (255, 255, 255) if self._eraser_mode else config.CANVAS_COLORS[self.color_idx]
        size  = self.eraser_size if self._eraser_mode else self.brush_size

        if self._prev_point:
            cv2.line(self.canvas, self._prev_point, pt, color, size)
        else:
            cv2.circle(self.canvas, pt, size // 2, color, -1)

        self._prev_point = pt

    def lift_pen(self):
        self._prev_point = None

    def erase_point(self, x, y):
        cv2.circle(self.canvas, (x, y), self.eraser_size, (0, 0, 0), -1)
        self._prev_point = None

    def clear(self):
        self.canvas[:] = 0
        self._prev_point = None

    def next_color(self):
        self.color_idx = (self.color_idx + 1) % len(config.CANVAS_COLORS)

    def toggle_eraser(self):
        self._eraser_mode = not self._eraser_mode

    def save(self):
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        fname   = time.strftime("drawing_%Y%m%d_%H%M%S.png")
        path    = os.path.join(desktop, fname)
        cv2.imwrite(path, self.canvas)
        return path

    def overlay_on(self, frame):
        """
        Blend canvas onto the camera frame.
        Drawing pixels overwrite camera feed.
        """
        mask  = cv2.cvtColor(self.canvas, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(mask, 1, 255, cv2.THRESH_BINARY)
        mask_inv = cv2.bitwise_not(mask)
        bg = cv2.bitwise_and(frame, frame, mask=mask_inv)
        fg = cv2.bitwise_and(self.canvas, self.canvas, mask=mask)
        return cv2.add(bg, fg)

    def draw_ui(self, frame):
        """Draw color palette and mode indicator in corner."""
        if not self._active:
            return frame

        x0, y0 = 10, 10
        swatch = 22
        gap    = 4
        for i, color in enumerate(config.CANVAS_COLORS):
            cx = x0 + i * (swatch + gap)
            cv2.rectangle(frame, (cx, y0), (cx+swatch, y0+swatch), color, -1)
            if i == self.color_idx and not self._eraser_mode:
                cv2.rectangle(frame, (cx-2, y0-2), (cx+swatch+2, y0+swatch+2),
                              (255,255,255), 2)

        # Eraser indicator
        ex = x0 + len(config.CANVAS_COLORS) * (swatch + gap) + 10
        er_color = (200, 200, 200)
        cv2.rectangle(frame, (ex, y0), (ex+swatch, y0+swatch), er_color, -1)
        if self._eraser_mode:
            cv2.rectangle(frame, (ex-2, y0-2),
                          (ex+swatch+2, y0+swatch+2), (255,255,255), 2)
        cv2.putText(frame, "E", (ex+5, y0+17), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (0,0,0), 2)

        # Mode label
        label = "✏ DRAW MODE"
        cv2.putText(frame, label, (10, y0 + swatch + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 128), 2)
        return frame
