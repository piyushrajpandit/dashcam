
# ── Camera Settings ─────────────────────────────────────────
# USB camera index (0 = Mac built-in camera / first USB camera)
CAMERA_SOURCE = 0

# If using WiFi/IP camera, replace CAMERA_SOURCE with URL:
# CAMERA_SOURCE = "rtsp://192.168.1.100:554/stream"
# CAMERA_SOURCE = "http://192.168.1.100:8080/video"

# ── Motion Detection Settings ───────────────────────────────
# Sensitivity: lower = more sensitive (detects smaller movements)
MOTION_THRESHOLD = 1500
ALERT_COOLDOWN_SECONDS = 5
MIN_CONTOUR_AREA = 500

# ── Server Settings ─────────────────────────────────────────
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8080   # Port 5000 is blocked by AirPlay on Mac

# Max alert snapshots to keep in memory
MAX_ALERTS_STORED = 50

# ── Snapshot Settings ────────────────────────────────────────
SNAPSHOT_QUALITY = 85
SNAPSHOT_WIDTH = 640
SNAPSHOT_HEIGHT = 480

