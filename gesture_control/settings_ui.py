"""
settings_ui.py
Tkinter-based settings dashboard.
Runs in a background thread so the main OpenCV loop is not blocked.
"""

import tkinter as tk
from tkinter import ttk, font
import threading
import config


class SettingsUI(threading.Thread):
    """
    Launches a Tkinter settings window in a separate thread.
    Changes are written live to config module globals.
    """

    def __init__(self):
        super().__init__(daemon=True)
        self.root = None
        self._vars = {}

    def run(self):
        self.root = tk.Tk()
        self.root.title("✋ Gesture Control — Settings")
        self.root.configure(bg="#1a1a2e")
        self.root.resizable(False, False)
        self._build_ui()
        self.root.mainloop()

    def _build_ui(self):
        r = self.root
        title_font = font.Font(family="Segoe UI", size=14, weight="bold")
        label_font = font.Font(family="Segoe UI", size=10)
        colors = {
            "bg":     "#1a1a2e",
            "panel":  "#16213e",
            "accent": "#0f3460",
            "green":  "#00ff88",
            "text":   "#e0e0e0",
        }

        # ── Header ─────────────────────────────────────────────────────────────
        hdr = tk.Frame(r, bg=colors["accent"], pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="✋ Gesture Control Settings",
                 font=title_font, fg=colors["green"],
                 bg=colors["accent"]).pack()

        # ── Notebook ───────────────────────────────────────────────────────────
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook",       background=colors["bg"])
        style.configure("TNotebook.Tab",   background=colors["accent"],
                        foreground=colors["text"], padding=[12, 4])
        style.map("TNotebook.Tab",
                  background=[("selected", colors["panel"])])

        nb = ttk.Notebook(r)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        # ── Tab 1: Feature Toggles ─────────────────────────────────────────────
        t1 = tk.Frame(nb, bg=colors["panel"])
        nb.add(t1, text="  Features  ")
        self._build_toggles(t1, colors, label_font)

        # ── Tab 2: Sensitivity ─────────────────────────────────────────────────
        t2 = tk.Frame(nb, bg=colors["panel"])
        nb.add(t2, text="  Sensitivity  ")
        self._build_sliders(t2, colors, label_font)

        # ── Tab 3: Gesture Info ────────────────────────────────────────────────
        t3 = tk.Frame(nb, bg=colors["panel"])
        nb.add(t3, text="  Gesture Guide  ")
        self._build_guide(t3, colors, label_font)

        # ── Footer ─────────────────────────────────────────────────────────────
        foot = tk.Frame(r, bg=colors["bg"], pady=6)
        foot.pack(fill="x")
        tk.Label(foot, text="Press 'Q' in camera window to quit | 'P' to pause",
                 font=label_font, fg="#888", bg=colors["bg"]).pack()

    def _build_toggles(self, parent, colors, lf):
        toggles = [
            ("Mouse Control",    "ENABLE_MOUSE"),
            ("Clicks",           "ENABLE_CLICKS"),
            ("Scroll",           "ENABLE_SCROLL"),
            ("Drag & Drop",      "ENABLE_DRAG"),
            ("Volume Control",   "ENABLE_VOLUME"),
            ("Brightness",       "ENABLE_BRIGHTNESS"),
            ("Media Controls",   "ENABLE_MEDIA"),
            ("Window Mgmt",      "ENABLE_WINDOW_MGMT"),
            ("Browser Control",  "ENABLE_BROWSER_CTRL"),
            ("System Keys",      "ENABLE_SYSTEM_KEYS"),
            ("Air Canvas",       "ENABLE_AIR_CANVAS"),
            ("Presentation Mode","ENABLE_PRESENTATION"),
        ]
        for i, (label, attr) in enumerate(toggles):
            var = tk.BooleanVar(value=getattr(config, attr))
            self._vars[attr] = var

            row = tk.Frame(parent, bg=colors["panel"])
            row.grid(row=i//2, column=i%2, sticky="w", padx=18, pady=4)

            cb = tk.Checkbutton(
                row, text=label, variable=var,
                command=lambda a=attr, v=var: self._toggle(a, v),
                bg=colors["panel"], fg=colors["text"],
                selectcolor=colors["accent"],
                activebackground=colors["panel"],
                font=lf, anchor="w"
            )
            cb.pack(side="left")

    def _build_sliders(self, parent, colors, lf):
        sliders = [
            ("Mouse Smoothing (0=snap, 0.9=slow)", "MOUSE_SMOOTHING",
             0.0, 0.95, 0.01),
            ("Mouse Speed",     "MOUSE_SPEED",     0.5, 5.0, 0.1),
            ("Scroll Speed",    "SCROLL_SPEED",    5,   50,  1),
            ("Click Cooldown",  "CLICK_COOLDOWN",  0.1, 1.0, 0.05),
            ("Pinch Threshold", "PINCH_THRESHOLD", 0.02, 0.15, 0.005),
            ("Swipe Threshold", "SWIPE_THRESHOLD", 0.10, 0.50, 0.01),
            ("Volume Sensitivity","VOL_SENSITIVITY", 50, 800, 10),
        ]
        for i, (label, attr, mn, mx, res) in enumerate(sliders):
            val = getattr(config, attr)
            var = tk.DoubleVar(value=val)
            self._vars[attr] = var

            tk.Label(parent, text=label, font=lf,
                     fg=colors["text"], bg=colors["panel"]).grid(
                row=i*2, column=0, sticky="w", padx=18, pady=(8, 0))

            val_label = tk.Label(parent, text=f"{val:.3g}",
                                 font=lf, fg=colors["green"],
                                 bg=colors["panel"], width=6)
            val_label.grid(row=i*2, column=1, sticky="e", padx=10)

            sl = tk.Scale(
                parent, variable=var, from_=mn, to=mx, resolution=res,
                orient="horizontal", length=260, showvalue=False,
                bg=colors["accent"], fg=colors["text"],
                troughcolor=colors["bg"], highlightthickness=0,
                command=lambda v, a=attr, vl=val_label: self._update_slider(a, v, vl)
            )
            sl.grid(row=i*2+1, column=0, columnspan=2, sticky="w",
                    padx=14, pady=(0, 4))

    def _build_guide(self, parent, colors, lf):
        gestures = [
            ("☝ Index finger",      "Move mouse cursor"),
            ("🤏 Pinch (thumb+idx)", "Left click"),
            ("🤏 Pinch (thumb+mid)", "Right click"),
            ("✌ 2 fingers move",    "Scroll"),
            ("👊 Fist + move",       "Drag & drop"),
            ("🤟 Pinch + hand up",   "Volume up"),
            ("🤟 Pinch + hand down", "Volume down"),
            ("✊ Fist hold 1.5s",    "Mute toggle"),
            ("3-finger pinch up",    "Brightness up"),
            ("3-finger pinch down",  "Brightness down"),
            ("👍 Thumb up",          "Play / Pause"),
            ("Rock hand swipe →",    "Next track"),
            ("Rock hand swipe ←",    "Prev track"),
            ("Open palm swipe →",    "Alt+Tab right"),
            ("Open palm swipe ←",    "Alt+Tab left"),
            ("Index swipe up",       "Maximize window"),
            ("Index swipe down",     "Minimize window"),
            ("2-finger swipe →",     "Next browser tab"),
            ("2-finger swipe ←",     "Prev browser tab"),
            ("3-finger swipe up",    "Task view"),
            ("5-finger swipe up",    "Show desktop"),
            ("3 fingers up tap",     "Paste (Ctrl+V)"),
            ("Index+Pinky up",       "Undo (Ctrl+Z)"),
            ("✌ V-hold 1s",          "Toggle draw mode"),
            ("🖐 Open palm hold 1.5s","Screenshot"),
            ("Two fists hold 2s",    "Lock screen"),
            ("Both hands spread",    "Zoom in"),
            ("Both hands pinch",     "Zoom out"),
        ]
        canvas = tk.Canvas(parent, bg=colors["panel"],
                           highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=colors["panel"])
        canvas.create_window((0, 0), window=inner, anchor="nw")

        headers = ["Gesture", "Action"]
        for col, h in enumerate(headers):
            tk.Label(inner, text=h, font=font.Font(family="Segoe UI", size=10,
                                                    weight="bold"),
                     fg=colors["green"], bg=colors["accent"],
                     padx=12, pady=4, width=22, anchor="w").grid(
                row=0, column=col, sticky="ew", padx=2, pady=2)

        for i, (g, a) in enumerate(gestures):
            bg = colors["panel"] if i % 2 == 0 else colors["accent"]
            tk.Label(inner, text=g, font=lf, fg=colors["text"],
                     bg=bg, padx=12, pady=3, width=22, anchor="w").grid(
                row=i+1, column=0, sticky="ew", padx=2, pady=1)
            tk.Label(inner, text=a, font=lf, fg=colors["green"],
                     bg=bg, padx=12, pady=3, width=22, anchor="w").grid(
                row=i+1, column=1, sticky="ew", padx=2, pady=1)

        inner.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))

    def _toggle(self, attr, var):
        setattr(config, attr, var.get())

    def _update_slider(self, attr, value, label):
        v = float(value)
        if attr in ("SCROLL_SPEED",):
            v = int(v)
        setattr(config, attr, v)
        label.config(text=f"{v:.3g}")


def launch_settings():
    """Launch settings UI in a background daemon thread."""
    ui = SettingsUI()
    ui.start()
    return ui
