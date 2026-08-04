"""
=============================================================
  DashCam Monitor — DEMO Server (no real camera needed)
=============================================================
  Simulates a camera feed and fires motion alerts every 10s
  so you can see the full UI working without a dashcam.
  
  Run: python3 demo_server.py
"""

import os
import sys
import base64
import logging
import threading
import time
import random
import math
from datetime import datetime
from flask import Flask, send_from_directory, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS

# ── Logging ───────────────────────────────────────────────── 
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# ── Flask App ─────────────────────────────────────────────── 
app = Flask(__name__, static_folder="../client")
app.config["SECRET_KEY"] = "dashcam-demo"
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

connected_clients = 0
alert_history = []
DEMO_MOTION_INTERVAL = 12   # seconds between simulated alerts
SERVER_PORT = 8080


# ── Generate Fake Camera Frame ────────────────────────────── 
def generate_demo_frame(width=640, height=480, motion=False):
    """Generate a synthetic camera frame using PIL."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io

        img = Image.new("RGB", (width, height), color=(15, 15, 30))
        draw = ImageDraw.Draw(img)

        # Sky gradient (top third)
        for y in range(height // 3):
            shade = int(15 + (y / (height // 3)) * 25)
            draw.line([(0, y), (width, y)], fill=(shade, shade, shade + 20))

        # Road (bottom third)
        road_top = height * 2 // 3
        draw.rectangle([0, road_top, width, height], fill=(55, 55, 55))

        # Perspective road lines
        draw.polygon(
            [(width // 2 - 20, road_top), (width // 2 + 20, road_top),
             (width // 2 + 80, height), (width // 2 - 80, height)],
            fill=(65, 65, 65)
        )

        # Lane markers (dashed)
        t = int(time.time() * 30) % 60
        for yy in range(road_top + (60 - t) % 60, height, 60):
            draw.rectangle([width // 2 - 4, yy, width // 2 + 4, yy + 30], fill=(200, 200, 150))

        # Scenery trees
        for i, tx in enumerate([80, 160, 480, 560]):
            ty = height // 3 + 20 + (i % 2) * 15
            draw.rectangle([tx - 6, ty, tx + 6, road_top], fill=(40, 80, 40))
            draw.ellipse([tx - 22, ty - 40, tx + 22, ty + 10], fill=(30, 100, 30))

        # Timestamp overlay
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        draw.rectangle([8, 8, len(ts) * 8 + 12, 26], fill=(0, 0, 0, 180))
        draw.text((10, 10), ts, fill=(200, 200, 200))
        draw.text((10, height - 22), "● REC  DEMO MODE", fill=(255, 80, 80))

        # Motion detection box
        if motion:
            draw.rectangle([180, 100, 380, 280], outline=(255, 50, 50), width=3)
            draw.rectangle([8, 38, 250, 58], fill=(200, 30, 30))
            draw.text((10, 40), "⚠ MOTION DETECTED", fill=(255, 255, 255))

            # Simulated moving object
            cx = 280
            cy = 190
            draw.ellipse([cx - 25, cy - 35, cx + 25, cy + 35], fill=(180, 100, 60))
            draw.ellipse([cx - 12, cy - 55, cx + 12, cy - 36], fill=(200, 160, 120))

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()

    except ImportError:
        # Fallback: return a minimal valid JPEG if PIL not available
        import struct, zlib
        # 1x1 dark blue pixel PNG
        data = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
            b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00'
            b'\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18'
            b'\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        return data


def frame_to_b64(motion=False):
    """Return base64-encoded image frame."""
    img_bytes = generate_demo_frame(motion=motion)
    mime = "jpeg" if img_bytes[:2] == b'\xff\xd8' else "png"
    return f"data:image/{mime};base64," + base64.b64encode(img_bytes).decode()



# ── Motion Simulation Thread ──────────────────────────────── 
def motion_simulation_loop():
    """Periodically fire fake motion alerts."""
    logger.info("🎬 Demo simulation started — motion every ~12 seconds")
    time.sleep(5)  # Wait for clients to connect first

    while True:
        time.sleep(DEMO_MOTION_INTERVAL)
        fire_demo_alert()


def fire_demo_alert():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    image_b64 = frame_to_b64(motion=True)

    alert = {
        "id": int(time.time() * 1000),
        "timestamp": ts,
        "unix_time": time.time(),
        "motion_area": random.randint(1500, 8000),
        "image": image_b64,
    }

    alert_history.insert(0, alert)
    if len(alert_history) > 20:
        alert_history.pop()

    logger.info(f"🚨 DEMO: Firing motion alert → {connected_clients} client(s)")
    socketio.emit("motion_alert", alert)


# ── WebSocket Events ──────────────────────────────────────── 
@socketio.on("connect")
def handle_connect():
    global connected_clients
    connected_clients += 1
    logger.info(f"📱 Client connected! Total: {connected_clients}")
    emit("status", {
        "motion_detected": False,
        "motion_area": 0,
        "threshold": 1500,
        "total_alerts": len(alert_history),
        "last_alert": alert_history[0]["timestamp"] if alert_history else None
    })
    if alert_history:
        emit("alert_history", alert_history[:10])


@socketio.on("disconnect")
def handle_disconnect():
    global connected_clients
    connected_clients = max(0, connected_clients - 1)
    logger.info(f"📱 Client disconnected. Total: {connected_clients}")


# ── REST API ──────────────────────────────────────────────── 
@app.route("/api/status")
def api_status():
    return jsonify({
        "camera_connected": True,
        "connected_clients": connected_clients,
        "server_time": datetime.now().isoformat(),
        "motion_detected": False,
        "total_alerts": len(alert_history),
        "mode": "DEMO"
    })


@app.route("/api/snapshot")
def api_snapshot():
    return jsonify({"image": frame_to_b64(motion=False)})


@app.route("/api/alerts")
def api_alerts():
    return jsonify([{k: v for k, v in a.items() if k != "image"} for a in alert_history])


@app.route("/api/alerts/<int:alert_id>/image")
def api_alert_image(alert_id):
    for a in alert_history:
        if a["id"] == alert_id:
            return jsonify({"image": a["image"]})
    return jsonify({"error": "Not found"}), 404


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    return jsonify({"threshold": 1500, "cooldown": 5, "min_contour_area": 500})


@app.route("/api/demo/fire")
def api_demo_fire():
    """Manually trigger a demo alert (for testing)."""
    fire_demo_alert()
    return jsonify({"success": True, "message": "Demo alert fired!"})


# ── Static Files ──────────────────────────────────────────── 
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(app.static_folder, path)


# ── Main ──────────────────────────────────────────────────── 
if __name__ == "__main__":
    import socket

    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except:
        local_ip = "localhost"

    print("\n" + "=" * 60)
    print("  🎬  DASHCAM MONITOR — DEMO MODE")
    print("=" * 60)
    print(f"\n  ✅ No camera needed — simulated feed active")
    print(f"  🚨 Auto motion alerts every ~{DEMO_MOTION_INTERVAL}s")
    print(f"\n{'=' * 60}")
    print(f"  📱 OPEN ON YOUR PHONE:")
    print(f"     http://{local_ip}:8080")
    print(f"\n  💻 OPEN IN THIS BROWSER:")
    print(f"     http://localhost:8080")
    print(f"{'=' * 60}")
    print(f"\n  Tip: Open http://localhost:8080/api/demo/fire to")
    print(f"  manually trigger a motion alert!\n")

    # Start simulation thread
    sim_thread = threading.Thread(target=motion_simulation_loop, daemon=True)
    sim_thread.start()

    socketio.run(
        app,
        host="0.0.0.0",
        port=SERVER_PORT,
        debug=False,
        allow_unsafe_werkzeug=True
    )
