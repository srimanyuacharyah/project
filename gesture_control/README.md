# ✋ Hand Gesture Computer Control

Control your entire computer in **real-time** using only hand gestures — no extra hardware needed. Uses your webcam + Google MediaPipe AI.

---

## Requirements

- Python 3.9 – 3.11  
- A working webcam  
- Windows 10/11

---

## Setup & Run

```powershell
cd d:\sri\project\gesture_control

# Install dependencies
pip install -r requirements.txt

# Launch
python main.py
```

---

## Keyboard Controls (in camera window)

| Key | Action |
|-----|--------|
| `Q` | Quit |
| `P` | Pause / Resume |
| `S` | Open Settings Dashboard |
| `D` | Toggle Draw Mode |
| `C` | Clear Canvas |
| `E` | Toggle Eraser |
| `N` | Next Draw Color |
| `H` | Toggle HUD |
| `V` | Save drawing to Desktop |

---

## Full Gesture Reference

### 🖱 Mouse
| Gesture | Action |
|---------|--------|
| ☝ Index finger up | Move cursor |
| 🤏 Pinch (thumb + index) | Left click |
| 🤏 Fast double pinch | Double click |
| 🤏 Pinch (thumb + middle) | Right click |
| 🤏 Pinch (thumb + ring) | Middle click |
| 👊 Fist + move | Drag & drop |

### 🔊 Audio / Display
| Gesture | Action |
|---------|--------|
| Thumb+index up + move hand up | Volume ▲ |
| Thumb+index up + move hand down | Volume ▼ |
| ✊ Fist hold 1.5s | Mute toggle |
| Thumb+index+middle + move up | Brightness ▲ |
| Thumb+index+middle + move down | Brightness ▼ |

### 🎵 Media
| Gesture | Action |
|---------|--------|
| 👍 Thumb up | Play / Pause |
| Rock hand → swipe right | Next track |
| Rock hand → swipe left | Previous track |

### ✌ Scroll
| Gesture | Action |
|---------|--------|
| Index + middle up, move up | Scroll up |
| Index + middle up, move down | Scroll down |

### 🪟 Window Management
| Gesture | Action |
|---------|--------|
| 🖐 Open palm swipe → | Alt+Tab (right) |
| 🖐 Open palm swipe ← | Alt+Tab (left) |
| ☝ Index swipe up | Maximize |
| ☝ Index swipe down | Minimize |
| ✌ 2-finger swipe → | Snap right |
| ✌ 2-finger swipe ← | Snap left |
| 3 fingers swipe up | Task View |
| 5 fingers swipe up | Show Desktop |

### 🌐 Browser
| Gesture | Action |
|---------|--------|
| Index+middle swipe → | Next Tab |
| Index+middle swipe ← | Prev Tab |
| 3-finger tap | Paste (Ctrl+V) |
| Index+Pinky up | Undo (Ctrl+Z) |

### ⚡ System
| Gesture | Action |
|---------|--------|
| 🖐 Open palm hold 1.5s | Screenshot (saved to Desktop) |
| Two fists hold 2s | Lock screen |
| Both hands spread | Zoom in |
| Both hands pinch | Zoom out |

### 🎨 Air Drawing
| Gesture | Action |
|---------|--------|
| ✌ V-sign hold 1s | Toggle draw mode |
| Index up, others folded | Draw |
| Lift any other finger | Lift pen |
| E key | Toggle eraser |
| N key | Cycle color |
| C key | Clear canvas |

---

## Tuning

Edit `config.py` to adjust:
- `MOUSE_SMOOTHING` — cursor lag (0=instant, 0.9=very smooth)  
- `PINCH_THRESHOLD` — pinch sensitivity  
- `SWIPE_THRESHOLD` — swipe distance required  
- `ENABLE_*` flags — turn features on/off  

Or press **S** at runtime to open the graphical Settings Dashboard.

---

## Project Structure

```
gesture_control/
├── main.py               # Main loop & HUD
├── hand_tracker.py       # MediaPipe wrapper
├── gesture_recognizer.py # Gesture classification (25+ gestures)
├── action_controller.py  # OS-level actions
├── air_canvas.py         # Air drawing
├── settings_ui.py        # GUI settings dashboard
├── config.py             # All configuration
└── requirements.txt
```
