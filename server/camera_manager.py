"""
=============================================================
  DashCam Monitor — Camera Manager
=============================================================
  Handles camera connection and frame reading.
  Supports USB, WiFi/IP cameras, and RTSP streams.
"""

import cv2
import time
import threading
import logging
from config import CAMERA_SOURCE, SNAPSHOT_WIDTH, SNAPSHOT_HEIGHT, SNAPSHOT_QUALITY

logger = logging.getLogger(__name__)


class CameraManager:
    def __init__(self):
        self.cap = None
        self.frame = None
        self.lock = threading.Lock()
        self.running = False
        self.connected = False
        self._thread = None

    def connect(self):
        """Connect to camera and start frame reading thread."""
        logger.info(f"Connecting to camera: {CAMERA_SOURCE}")
        self.cap = cv2.VideoCapture(CAMERA_SOURCE)

        if not self.cap.isOpened():
            logger.error("❌ Could not open camera! Check CAMERA_SOURCE in config.py")
            raise RuntimeError(
                f"Cannot open camera: {CAMERA_SOURCE}. "
                "Make sure your dashcam is connected."
            )

        # Set resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, SNAPSHOT_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, SNAPSHOT_HEIGHT)

        self.running = True
        self.connected = True
        self._thread = threading.Thread(target=self._read_frames, daemon=True)
        self._thread.start()
        logger.info("✅ Camera connected successfully!")

    def _read_frames(self):
        """Continuously read frames from camera in background thread."""
        consecutive_failures = 0
        MAX_FAILURES = 30

        while self.running:
            ret, frame = self.cap.read()
            if ret:
                with self.lock:
                    self.frame = frame
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                logger.warning(f"Frame read failed ({consecutive_failures}/{MAX_FAILURES})")
                if consecutive_failures >= MAX_FAILURES:
                    logger.error("Too many frame failures, attempting reconnect...")
                    self._reconnect()
                    consecutive_failures = 0
            time.sleep(0.033)  # ~30 FPS

    def _reconnect(self):
        """Attempt to reconnect to camera."""
        try:
            if self.cap:
                self.cap.release()
            time.sleep(2)
            self.cap = cv2.VideoCapture(CAMERA_SOURCE)
            if self.cap.isOpened():
                logger.info("✅ Camera reconnected!")
            else:
                logger.error("❌ Reconnect failed")
        except Exception as e:
            logger.error(f"Reconnect error: {e}")

    def get_frame(self):
        """Get the latest frame (thread-safe)."""
        with self.lock:
            return self.frame.copy() if self.frame is not None else None

    def capture_snapshot(self):
        """Capture current frame as JPEG bytes (base64-ready)."""
        frame = self.get_frame()
        if frame is None:
            return None

        # Resize for snapshot
        frame = cv2.resize(frame, (SNAPSHOT_WIDTH, SNAPSHOT_HEIGHT))

        # Encode as JPEG
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, SNAPSHOT_QUALITY]
        ret, buffer = cv2.imencode('.jpg', frame, encode_params)
        if ret:
            return buffer.tobytes()
        return None

    def is_connected(self):
        return self.connected and self.cap is not None and self.cap.isOpened()

    def disconnect(self):
        """Stop the camera and release resources."""
        self.running = False
        self.connected = False
        if self.cap:
            self.cap.release()
        logger.info("Camera disconnected.")
