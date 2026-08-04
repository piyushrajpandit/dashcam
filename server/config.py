"""
=============================================================
  DashCam Monitor — Configuration
=============================================================
  Edit these settings to match your setup.
"""

# ── Camera Settings ─────────────────────────────────────────
# USB camera index (0 = first USB camera, 1 = second, etc.)
CAMERA_SOURCE = 0

# If using WiFi/IP camera, replace CAMERA_SOURCE with URL:
# CAMERA_SOURCE = "rtsp://192.168.1.100:554/stream"
# CAMERA_SOURCE = "http://192.168.1.100:8080/video"

# ── Motion Detection Settings ───────────────────────────────
# Sensitivity: lower = more sensitive (detects smaller movements)
# Recommended range: 500 - 5000
MOTION_THRESHOLD = 1500

# Minimum seconds between alerts (avoid spam)
ALERT_COOLDOWN_SECONDS = 5

# Minimum contour area to count as motion (pixels)
MIN_CONTOUR_AREA = 500

# ── Server Settings ─────────────────────────────────────────
SERVER_HOST = "0.0.0.0"   # Listen on all network interfaces
SERVER_PORT = 5000

# Max alert snapshots to keep in memory
MAX_ALERTS_STORED = 50

# ── Snapshot Settings ────────────────────────────────────────
SNAPSHOT_QUALITY = 85      # JPEG quality (1-100)
SNAPSHOT_WIDTH = 640       # Resize captured snapshot width
SNAPSHOT_HEIGHT = 480      # Resize captured snapshot height
