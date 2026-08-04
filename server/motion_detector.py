"""
=============================================================
  DashCam Monitor — Motion Detector
=============================================================
  Uses OpenCV background subtraction to detect motion.
  When motion is detected, captures a snapshot and triggers
  the alert callback.
"""

import cv2
import time
import threading
import logging
import base64
from datetime import datetime
from config import (
    MOTION_THRESHOLD,
    MIN_CONTOUR_AREA,
    ALERT_COOLDOWN_SECONDS,
    MAX_ALERTS_STORED
)

logger = logging.getLogger(__name__)


class MotionDetector:
    def __init__(self, camera_manager, alert_callback):
        """
        Args:
            camera_manager: CameraManager instance
            alert_callback: function(alert_dict) called when motion is detected
        """
        self.camera = camera_manager
        self.on_alert = alert_callback
        self.running = False
        self._thread = None

        # OpenCV background subtractor
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500,
            varThreshold=50,
            detectShadows=True
        )

        # Alert history
        self.alerts = []
        self.last_alert_time = 0

        # Motion state
        self.motion_detected = False
        self.current_motion_area = 0

    def start(self):
        """Start motion detection in background thread."""
        self.running = True
        self._thread = threading.Thread(target=self._detect_loop, daemon=True)
        self._thread.start()
        logger.info("✅ Motion detection started")

    def _detect_loop(self):
        """Main detection loop."""
        while self.running:
            frame = self.camera.get_frame()
            if frame is None:
                time.sleep(0.1)
                continue

            motion_area, processed = self._analyze_frame(frame)
            self.current_motion_area = motion_area

            if motion_area > MOTION_THRESHOLD:
                self.motion_detected = True
                now = time.time()
                # Cooldown check — avoid spamming alerts
                if now - self.last_alert_time >= ALERT_COOLDOWN_SECONDS:
                    self.last_alert_time = now
                    self._trigger_alert(frame, motion_area)
            else:
                self.motion_detected = False

            time.sleep(0.05)  # ~20 checks per second

    def _analyze_frame(self, frame):
        """
        Analyze a frame for motion.
        Returns: (total_motion_area, processed_mask)
        """
        # Apply background subtraction
        fg_mask = self.bg_subtractor.apply(frame)

        # Remove shadows (gray pixels → 0)
        _, fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)

        # Morphological cleanup to remove noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
        fg_mask = cv2.dilate(fg_mask, kernel, iterations=2)

        # Find motion contours
        contours, _ = cv2.findContours(
            fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # Sum up significant motion areas
        total_area = 0
        for contour in contours:
            area = cv2.contourArea(contour)
            if area >= MIN_CONTOUR_AREA:
                total_area += area

        return total_area, fg_mask

    def _trigger_alert(self, frame, motion_area):
        """Capture snapshot and trigger the alert callback."""
        logger.info(f"🚨 MOTION DETECTED! Area: {motion_area:.0f} px²")

        # Draw motion bounding box on snapshot
        annotated = frame.copy()
        fg_mask = self.bg_subtractor.apply(frame)
        _, fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(
            fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        for contour in contours:
            if cv2.contourArea(contour) >= MIN_CONTOUR_AREA:
                x, y, w, h = cv2.boundingRect(contour)
                cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 0, 255), 2)

        # Add timestamp overlay
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(
            annotated, f"MOTION DETECTED  {timestamp_str}",
            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2
        )

        # Encode snapshot as base64 JPEG
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, 85]
        ret, buffer = cv2.imencode('.jpg', annotated, encode_params)
        if not ret:
            logger.error("Failed to encode snapshot")
            return

        image_b64 = base64.b64encode(buffer.tobytes()).decode('utf-8')

        # Build alert object
        alert = {
            "id": int(time.time() * 1000),
            "timestamp": timestamp_str,
            "unix_time": time.time(),
            "motion_area": round(motion_area),
            "image": f"data:image/jpeg;base64,{image_b64}"
        }

        # Store in history (cap at MAX_ALERTS_STORED)
        self.alerts.insert(0, alert)
        if len(self.alerts) > MAX_ALERTS_STORED:
            self.alerts.pop()

        # Fire callback (sends to connected phones)
        try:
            self.on_alert(alert)
        except Exception as e:
            logger.error(f"Alert callback error: {e}")

    def get_status(self):
        """Return current detector status."""
        return {
            "motion_detected": self.motion_detected,
            "motion_area": self.current_motion_area,
            "threshold": MOTION_THRESHOLD,
            "total_alerts": len(self.alerts),
            "last_alert": self.alerts[0]["timestamp"] if self.alerts else None
        }

    def stop(self):
        self.running = False
        logger.info("Motion detector stopped")
