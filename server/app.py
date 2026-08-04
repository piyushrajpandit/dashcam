"""
=============================================================
  DashCam Monitor — Flask + WebSocket Server
=============================================================
  Serves the Android web dashboard and broadcasts motion
  alerts in real-time via WebSockets.
"""

import os
import sys
import logging
import threading
import json
import base64
from datetime import datetime
from flask import Flask, send_from_directory, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS

from config import SERVER_HOST, SERVER_PORT
from camera_manager import CameraManager
from motion_detector import MotionDetector

# ── Logging Setup ────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# ── Flask App ────────────────────────────────────────────────
app = Flask(__name__, static_folder="../client")
app.config["SECRET_KEY"] = "dashcam-monitor-secret-2024"
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ── Global Components ────────────────────────────────────────
camera = CameraManager()
detector = None
connected_clients = 0


# ── Alert Broadcast ──────────────────────────────────────────
def on_motion_alert(alert):
    """Called by MotionDetector when motion is detected."""
    logger.info(f"📡 Broadcasting alert to {connected_clients} client(s)")
    socketio.emit("motion_alert", alert)


# ── WebSocket Events ─────────────────────────────────────────
@socketio.on("connect")
def handle_connect():
    global connected_clients
    connected_clients += 1
    logger.info(f"📱 Phone connected! Total clients: {connected_clients}")
    # Send current status on connect
    if detector:
        emit("status", detector.get_status())
    # Send recent alert history
    if detector and detector.alerts:
        emit("alert_history", detector.alerts[:10])


@socketio.on("disconnect")
def handle_disconnect():
    global connected_clients
    connected_clients = max(0, connected_clients - 1)
    logger.info(f"📱 Client disconnected. Total clients: {connected_clients}")


@socketio.on("ping")
def handle_ping():
    emit("pong", {"time": datetime.now().isoformat()})


# ── REST API ─────────────────────────────────────────────────
@app.route("/api/status")
def api_status():
    """Camera and detector status."""
    status = {
        "camera_connected": camera.is_connected(),
        "connected_clients": connected_clients,
        "server_time": datetime.now().isoformat(),
    }
    if detector:
        status.update(detector.get_status())
    return jsonify(status)


@app.route("/api/alerts")
def api_alerts():
    """Recent alert history (without images to save bandwidth)."""
    if not detector:
        return jsonify([])
    # Return alerts without base64 image data for list view
    alerts_meta = [
        {k: v for k, v in alert.items() if k != "image"}
        for alert in detector.alerts
    ]
    return jsonify(alerts_meta)


@app.route("/api/alerts/<int:alert_id>/image")
def api_alert_image(alert_id):
    """Get snapshot for a specific alert."""
    if not detector:
        return jsonify({"error": "Detector not running"}), 404
    for alert in detector.alerts:
        if alert["id"] == alert_id:
            return jsonify({"image": alert["image"]})
    return jsonify({"error": "Alert not found"}), 404


@app.route("/api/snapshot")
def api_snapshot():
    """Get a live snapshot from the camera."""
    snapshot = camera.capture_snapshot()
    if snapshot is None:
        return jsonify({"error": "Camera not available"}), 503
    image_b64 = base64.b64encode(snapshot).decode("utf-8")
    return jsonify({"image": f"data:image/jpeg;base64,{image_b64}"})


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    """Get or update motion detection settings."""
    import config
    if request.method == "POST":
        data = request.get_json()
        if "threshold" in data:
            config.MOTION_THRESHOLD = int(data["threshold"])
            if detector:
                detector.motion_threshold = config.MOTION_THRESHOLD
        if "cooldown" in data:
            config.ALERT_COOLDOWN_SECONDS = int(data["cooldown"])
        return jsonify({"success": True})

    return jsonify({
        "threshold": config.MOTION_THRESHOLD,
        "cooldown": config.ALERT_COOLDOWN_SECONDS,
        "min_contour_area": config.MIN_CONTOUR_AREA
    })


# ── Static File Serving (Android Web Dashboard) ──────────────
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(app.static_folder, path)


# ── Startup ──────────────────────────────────────────────────
def start_services():
    """Initialize camera and motion detector."""
    global detector

    print("\n" + "=" * 60)
    print("  🎥  DASHCAM MONITOR — Starting Up")
    print("=" * 60)

    # Connect camera
    try:
        camera.connect()
    except RuntimeError as e:
        print(f"\n❌ CAMERA ERROR: {e}")
        print("\n📋 Troubleshooting:")
        print("  1. Make sure dashcam is plugged in via USB")
        print("  2. Check CAMERA_SOURCE in server/config.py")
        print("  3. Try changing CAMERA_SOURCE = 1 or 2")
        sys.exit(1)

    # Start motion detector
    detector = MotionDetector(camera, on_motion_alert)
    detector.start()

    # Print access info
    import socket
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except:
        local_ip = "YOUR-PC-IP"

    print(f"\n✅ Camera connected!")
    print(f"✅ Motion detection active!")
    print(f"\n{'=' * 60}")
    print(f"  📱 OPEN THIS ON YOUR ANDROID PHONE:")
    print(f"     http://{local_ip}:{SERVER_PORT}")
    print(f"{'=' * 60}")
    print(f"\n  (Both devices must be on the same WiFi)")
    print(f"  Press Ctrl+C to stop\n")


if __name__ == "__main__":
    start_services()
    socketio.run(
        app,
        host=SERVER_HOST,
        port=SERVER_PORT,
        debug=False,
        allow_unsafe_werkzeug=True
    )
