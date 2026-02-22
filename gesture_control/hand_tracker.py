"""
hand_tracker.py - MediaPipe Tasks API hand landmark detection wrapper
Compatible with mediapipe 0.10+
Supports up to 2 hands, provides all 21 landmark helpers.
"""

import cv2
import mediapipe as mp
import numpy as np
import math
import threading
import os

# New Tasks API
BaseOptions        = mp.tasks.BaseOptions
HandLandmarker     = mp.tasks.vision.HandLandmarker
HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
HandLandmarkerResult  = mp.tasks.vision.HandLandmarkerResult
VisionRunningMode  = mp.tasks.vision.RunningMode

# Model path (downloaded into assets/)
_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "assets", "hand_landmarker.task"
)


class HandTracker:
    """
    Wraps mediapipe HandLandmarker (Tasks API) and exposes
    the same helper interface used by gesture_recognizer.py.
    Works in LIVE_STREAM mode — non-blocking, async callbacks.
    """

    # MediaPipe landmark indices
    WRIST       = 0
    THUMB_CMC   = 1;  THUMB_MCP  = 2;  THUMB_IP   = 3;  THUMB_TIP   = 4
    INDEX_MCP   = 5;  INDEX_PIP  = 6;  INDEX_DIP  = 7;  INDEX_TIP   = 8
    MIDDLE_MCP  = 9;  MIDDLE_PIP = 10; MIDDLE_DIP = 11; MIDDLE_TIP  = 12
    RING_MCP    = 13; RING_PIP   = 14; RING_DIP   = 15; RING_TIP    = 16
    PINKY_MCP   = 17; PINKY_PIP  = 18; PINKY_DIP  = 19; PINKY_TIP   = 20

    FINGER_TIPS = [THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP]
    FINGER_PIPS = [THUMB_IP,  INDEX_PIP, MIDDLE_PIP, RING_PIP, PINKY_PIP]

    def __init__(self, max_hands=2, min_detection_confidence=0.75,
                 min_tracking_confidence=0.75):
        self._lock   = threading.Lock()
        self._result = None          # latest HandLandmarkerResult
        self._ts     = 0
        self.img_h   = 1
        self.img_w   = 1
        self._frame_counter = 0

        options = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=_MODEL_PATH),
            running_mode=VisionRunningMode.LIVE_STREAM,
            num_hands=max_hands,
            min_hand_detection_confidence=min_detection_confidence,
            min_hand_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
            result_callback=self._callback,
        )
        self._landmarker = HandLandmarker.create_from_options(options)
        self._draw_utils = _DrawUtils()

    def _callback(self, result: HandLandmarkerResult, output_image, timestamp_ms):
        with self._lock:
            self._result = result

    # ── Core detection ─────────────────────────────────────────────────────────
    def process(self, frame_bgr):
        """Submit a frame for async detection. Returns frame unchanged."""
        self.img_h, self.img_w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        self._frame_counter += 1
        ts_ms = self._frame_counter * 33   # ~30 FPS timestamps
        self._landmarker.detect_async(mp_image, ts_ms)
        return frame_bgr

    def draw_landmarks(self, frame):
        """Draw skeleton overlay on the frame."""
        with self._lock:
            result = self._result
        if result is None:
            return frame
        for hand_lms in result.hand_landmarks:
            self._draw_utils.draw_hand(frame, hand_lms, self.img_w, self.img_h)
        return frame

    def __del__(self):
        try:
            self._landmarker.close()
        except Exception:
            pass

    # ── Landmark access ────────────────────────────────────────────────────────
    def get_landmarks(self, hand_index=0):
        """Return list of (x_norm, y_norm, z_norm) for all 21 points or []."""
        with self._lock:
            result = self._result
        if result is None or not result.hand_landmarks:
            return []
        if hand_index >= len(result.hand_landmarks):
            return []
        lms = result.hand_landmarks[hand_index]
        return [(lm.x, lm.y, lm.z) for lm in lms]

    def get_pixel_pos(self, landmark_index, hand_index=0):
        """Return pixel (x, y) for a specific landmark."""
        lms = self.get_landmarks(hand_index)
        if not lms:
            return None
        x_n, y_n, _ = lms[landmark_index]
        return (int(x_n * self.img_w), int(y_n * self.img_h))

    def count_hands(self):
        with self._lock:
            result = self._result
        if result is None or not result.hand_landmarks:
            return 0
        return len(result.hand_landmarks)

    def get_handedness(self, hand_index=0):
        """Return 'Left' or 'Right'. Note: MediaPipe labels from the model's POV."""
        with self._lock:
            result = self._result
        if result is None or not result.handedness:
            return "Right"
        if hand_index >= len(result.handedness):
            return "Right"
        return result.handedness[hand_index][0].category_name

    # ── Finger helpers ─────────────────────────────────────────────────────────
    def fingers_up(self, hand_index=0):
        """
        Returns [thumb, index, middle, ring, pinky] — 1=extended, 0=folded.
        """
        lms = self.get_landmarks(hand_index)
        if not lms:
            return [0, 0, 0, 0, 0]

        hand_label = self.get_handedness(hand_index)
        up = []

        # Thumb: compare x (mirrored feed — left/right flipped)
        if hand_label == 'Left':   # appears on right side of mirrored image
            up.append(1 if lms[self.THUMB_TIP][0] < lms[self.THUMB_IP][0] else 0)
        else:
            up.append(1 if lms[self.THUMB_TIP][0] > lms[self.THUMB_IP][0] else 0)

        # Four fingers: tip y < pip y → extended
        for tip, pip in zip(self.FINGER_TIPS[1:], self.FINGER_PIPS[1:]):
            up.append(1 if lms[tip][1] < lms[pip][1] else 0)

        return up

    def get_distance(self, idx_a, idx_b, hand_index=0, normalised=True):
        lms = self.get_landmarks(hand_index)
        if not lms:
            return None
        ax, ay = lms[idx_a][0], lms[idx_a][1]
        bx, by = lms[idx_b][0], lms[idx_b][1]
        if normalised:
            return math.hypot(ax - bx, ay - by)
        return math.hypot(
            (ax - bx) * self.img_w,
            (ay - by) * self.img_h,
        )

    def get_angle(self, a_idx, b_idx, c_idx, hand_index=0):
        lms = self.get_landmarks(hand_index)
        if not lms:
            return None
        def vec(p, q):
            return np.array([q[0]-p[0], q[1]-p[1]])
        v1 = vec(lms[b_idx], lms[a_idx])
        v2 = vec(lms[b_idx], lms[c_idx])
        cos_a = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-8)
        return math.degrees(math.acos(np.clip(cos_a, -1, 1)))

    # ── Convenience wrappers ───────────────────────────────────────────────────
    def index_tip(self, hand_index=0):
        return self.get_pixel_pos(self.INDEX_TIP, hand_index)

    def thumb_tip(self, hand_index=0):
        return self.get_pixel_pos(self.THUMB_TIP, hand_index)

    def middle_tip(self, hand_index=0):
        return self.get_pixel_pos(self.MIDDLE_TIP, hand_index)

    def wrist(self, hand_index=0):
        return self.get_pixel_pos(self.WRIST, hand_index)

    def hand_center(self, hand_index=0):
        lms = self.get_landmarks(hand_index)
        if not lms:
            return None
        xs = [int(l[0]*self.img_w) for l in lms]
        ys = [int(l[1]*self.img_h) for l in lms]
        return (int(np.mean(xs)), int(np.mean(ys)))

    def palm_size(self, hand_index=0):
        return self.get_distance(
            self.WRIST, self.MIDDLE_MCP, hand_index, normalised=False)


class _DrawUtils:
    """Lightweight landmark + connection drawer (no mp.solutions dependency)."""

    CONNECTIONS = [
        # Thumb
        (0,1),(1,2),(2,3),(3,4),
        # Index
        (0,5),(5,6),(6,7),(7,8),
        # Middle
        (0,9),(9,10),(10,11),(11,12),
        # Ring
        (0,13),(13,14),(14,15),(15,16),
        # Pinky
        (0,17),(17,18),(18,19),(19,20),
        # Palm
        (5,9),(9,13),(13,17),
    ]
    LM_COLOR   = (0, 255, 128)
    CONN_COLOR = (255, 255, 255)
    TIP_COLOR  = (0, 200, 255)
    TIPS       = {4, 8, 12, 16, 20}

    def draw_hand(self, frame, landmarks, w, h):
        pts = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]
        # Connections
        for a, b in self.CONNECTIONS:
            cv2.line(frame, pts[a], pts[b], self.CONN_COLOR, 2, cv2.LINE_AA)
        # Landmarks
        for i, pt in enumerate(pts):
            color = self.TIP_COLOR if i in self.TIPS else self.LM_COLOR
            r = 7 if i in self.TIPS else 4
            cv2.circle(frame, pt, r, color, -1, cv2.LINE_AA)
            cv2.circle(frame, pt, r+1, (0,0,0), 1, cv2.LINE_AA)
