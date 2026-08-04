/* ============================================================
   DashCam Monitor — Main App Logic
   WebSocket connection, alerts, notifications, sound
   ============================================================ */

// ── Configuration ──────────────────────────────────────────
const SERVER_URL = `${location.protocol}//${location.hostname}:5000`;

// ── State ──────────────────────────────────────────────────
let socket = null;
let isConnected = false;
let alertHistory = [];
let currentAlertForModal = null;
let soundEnabled = true;
let notifEnabled = true;
let deferredInstallPrompt = null;
let snapshotInterval = null;

// ── Audio Context (Web Audio API) ─────────────────────────
const AudioCtx = window.AudioContext || window.webkitAudioContext;
let audioCtx = null;

function ensureAudio() {
  if (!audioCtx) audioCtx = new AudioCtx();
  if (audioCtx.state === "suspended") audioCtx.resume();
}

function playAlertSound() {
  if (!soundEnabled) return;
  try {
    ensureAudio();
    const NOTES = [880, 0, 880, 0, 1320, 0, 1320];
    const DURATION = 0.1;
    NOTES.forEach((freq, i) => {
      if (freq === 0) return;
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.type = "square";
      osc.frequency.value = freq;
      const t = audioCtx.currentTime + i * DURATION;
      gain.gain.setValueAtTime(0.3, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + DURATION * 0.9);
      osc.start(t);
      osc.stop(t + DURATION);
    });
  } catch (e) {
    console.warn("Audio error:", e);
  }
}

// ── Toast Notifications ─────────────────────────────────── 
function showToast(message, type = "info", duration = 3500) {
  const container = document.getElementById("toastContainer");
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "scale(0.95)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 350);
  }, duration);
}

// ── Connection Status UI ────────────────────────────────────
function setConnectionStatus(state) {
  const pill = document.getElementById("connectionStatus");
  const dot = document.getElementById("statusDot");
  const txt = document.getElementById("statusText");
  pill.className = `status-pill ${state}`;
  const labels = {
    connected: "Connected",
    disconnected: "Disconnected",
    connecting: "Connecting…",
  };
  txt.textContent = labels[state] || state;
}

// ── WebSocket Connection ────────────────────────────────────
function connectSocket() {
  setConnectionStatus("connecting");

  socket = io(SERVER_URL, {
    transports: ["websocket", "polling"],
    reconnection: true,
    reconnectionDelay: 2000,
    reconnectionAttempts: Infinity,
    timeout: 8000,
  });

  socket.on("connect", () => {
    isConnected = true;
    setConnectionStatus("connected");
    showToast("✅ Connected to camera server", "success");
    startLiveSnapshot();
    pollStatus();
  });

  socket.on("disconnect", () => {
    isConnected = false;
    setConnectionStatus("disconnected");
    showToast("❌ Disconnected from server", "error");
    stopLiveSnapshot();
    document.getElementById("liveBadge").style.opacity = "0.3";
  });

  socket.on("connect_error", () => {
    setConnectionStatus("disconnected");
  });

  socket.on("motion_alert", (alert) => {
    handleMotionAlert(alert);
  });

  socket.on("alert_history", (alerts) => {
    alertHistory = alerts;
    renderAlertHistory();
  });

  socket.on("status", (status) => {
    updateStatusUI(status);
  });

  socket.on("pong", (data) => {
    // Heartbeat received
  });
}

// ── Motion Alert Handler ────────────────────────────────────
function handleMotionAlert(alert) {
  console.log("🚨 Motion alert received:", alert.timestamp);

  // Play sound
  playAlertSound();

  // Add to local history
  alertHistory.unshift(alert);
  if (alertHistory.length > 50) alertHistory.pop();
  renderAlertHistory();

  // Update stats
  document.getElementById("totalAlertsCount").textContent = alertHistory.length;
  document.getElementById("motionStatus").textContent = "MOTION!";
  document.getElementById("motionIcon").textContent = "🚨";
  document.getElementById("statMotion").classList.add("alert-state");

  // Show snapshot in camera view
  const img = document.getElementById("liveSnapshot");
  img.src = alert.image;
  img.classList.remove("hidden");
  document.getElementById("cameraPlaceholder").classList.add("hidden");
  const overlay = document.getElementById("motionOverlay");
  overlay.classList.remove("hidden");
  setTimeout(() => overlay.classList.add("hidden"), 4000);
  setTimeout(() => {
    document.getElementById("motionStatus").textContent = "CLEAR";
    document.getElementById("motionIcon").textContent = "😴";
    document.getElementById("statMotion").classList.remove("alert-state");
  }, 6000);

  // Show motion banner
  showMotionBanner(alert);

  // Browser / system notification
  if (notifEnabled && document.visibilityState !== "visible") {
    sendSystemNotification(alert);
  }

  // Send to Service Worker for background notification
  if ("serviceWorker" in navigator && navigator.serviceWorker.controller) {
    navigator.serviceWorker.controller.postMessage({
      type: "SHOW_NOTIFICATION",
      payload: {
        title: "🚨 Motion Detected!",
        body: `Camera detected movement at ${alert.timestamp}`,
        image: alert.image,
      },
    });
  }
}

// ── Motion Banner ───────────────────────────────────────────
let bannerTimeout = null;

function showMotionBanner(alert) {
  const banner = document.getElementById("motionBanner");
  document.getElementById("bannerTime").textContent = alert.timestamp;
  banner.classList.remove("hidden");
  clearTimeout(bannerTimeout);
  bannerTimeout = setTimeout(() => banner.classList.add("hidden"), 8000);

  document.getElementById("bannerView").onclick = () => {
    banner.classList.add("hidden");
    openModal(alert);
  };
}

// ── System Notification ─────────────────────────────────────
async function sendSystemNotification(alert) {
  if (Notification.permission !== "granted") return;
  try {
    const notif = new Notification("🚨 DashCam — Motion Detected!", {
      body: `Movement detected at ${alert.timestamp}`,
      icon: "/icons/icon-192.png",
      tag: "motion-alert",
      renotify: true,
      vibrate: [200, 100, 200, 100, 400],
    });
    notif.onclick = () => {
      window.focus();
      notif.close();
      openModal(alert);
    };
  } catch (e) {
    console.warn("Notification error:", e);
  }
}

// ── Alert History Renderer ──────────────────────────────────
function renderAlertHistory() {
  const list = document.getElementById("alertsList");
  const empty = document.getElementById("emptyState");

  if (alertHistory.length === 0) {
    empty.classList.remove("hidden");
    const items = list.querySelectorAll(".alert-item");
    items.forEach((el) => el.remove());
    return;
  }

  empty.classList.add("hidden");

  // Re-render all items (keep DOM in sync)
  const items = list.querySelectorAll(".alert-item");
  items.forEach((el) => el.remove());

  alertHistory.forEach((alert) => {
    const item = document.createElement("div");
    item.className = "alert-item";
    item.dataset.alertId = alert.id;

    const thumbHtml = alert.image
      ? `<img class="alert-thumb" src="${alert.image}" alt="Motion snapshot" loading="lazy" />`
      : `<div class="alert-thumb-placeholder">📷</div>`;

    item.innerHTML = `
      ${thumbHtml}
      <div class="alert-body">
        <div class="alert-title">Motion Detected</div>
        <div class="alert-meta">${alert.timestamp}</div>
      </div>
      <span class="alert-badge">ALERT</span>
    `;

    item.addEventListener("click", () => openModal(alert));
    list.appendChild(item);
  });
}

// ── Modal ───────────────────────────────────────────────────
function openModal(alert) {
  currentAlertForModal = alert;
  document.getElementById("modalTitle").textContent = "Motion Alert";
  document.getElementById("modalImg").src = alert.image || "";
  document.getElementById("modalInfo").innerHTML = `
    <span>🕒 ${alert.timestamp}</span>
    <span>📐 Area: ${alert.motion_area?.toLocaleString() ?? "—"} px²</span>
  `;
  document.getElementById("modalBackdrop").classList.remove("hidden");
  document.body.style.overflow = "hidden";
}

function closeModal() {
  document.getElementById("modalBackdrop").classList.add("hidden");
  document.body.style.overflow = "";
}

// ── Live Snapshot Polling ───────────────────────────────────
function startLiveSnapshot() {
  stopLiveSnapshot();
  snapshotInterval = setInterval(fetchLiveSnapshot, 2000);
  document.getElementById("liveBadge").style.opacity = "1";
}

function stopLiveSnapshot() {
  if (snapshotInterval) {
    clearInterval(snapshotInterval);
    snapshotInterval = null;
  }
}

async function fetchLiveSnapshot() {
  if (!isConnected) return;
  try {
    const res = await fetch(`${SERVER_URL}/api/snapshot`);
    if (!res.ok) return;
    const data = await res.json();
    if (data.image) {
      const img = document.getElementById("liveSnapshot");
      img.src = data.image;
      img.classList.remove("hidden");
      document.getElementById("cameraPlaceholder").classList.add("hidden");
    }
  } catch (e) {
    // Server may be temporarily busy
  }
}

// ── Status Poll ─────────────────────────────────────────────
async function pollStatus() {
  try {
    const res = await fetch(`${SERVER_URL}/api/status`);
    const data = await res.json();
    updateStatusUI(data);
  } catch (e) {}
}

function updateStatusUI(data) {
  if (data.connected_clients !== undefined) {
    document.getElementById("clientsCount").textContent = data.connected_clients;
  }
  if (data.total_alerts !== undefined) {
    document.getElementById("totalAlertsCount").textContent = data.total_alerts;
  }
}

// ── Settings ────────────────────────────────────────────────
function initSettings() {
  const slider = document.getElementById("sensitivitySlider");
  const sliderVal = document.getElementById("sensitivityVal");
  const cooldown = document.getElementById("cooldownSlider");
  const cooldownVal = document.getElementById("cooldownVal");

  slider.addEventListener("input", () => {
    sliderVal.textContent = `Threshold: ${slider.value}`;
  });

  cooldown.addEventListener("input", () => {
    cooldownVal.textContent = `Cooldown: ${cooldown.value}s`;
  });

  document.getElementById("soundToggle").addEventListener("change", (e) => {
    soundEnabled = e.target.checked;
  });

  document.getElementById("notifToggle").addEventListener("change", (e) => {
    notifEnabled = e.target.checked;
  });

  document.getElementById("saveSettingsBtn").addEventListener("click", async () => {
    try {
      await fetch(`${SERVER_URL}/api/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          threshold: parseInt(slider.value),
          cooldown: parseInt(cooldown.value),
        }),
      });
      showToast("✅ Settings saved!", "success");
      closeSettings();
    } catch (e) {
      showToast("❌ Could not save settings", "error");
    }
  });

  // Notification permission
  document.getElementById("requestNotifBtn").addEventListener("click", async () => {
    const perm = await Notification.requestPermission();
    if (perm === "granted") {
      showToast("✅ Notifications enabled!", "success");
    } else {
      showToast("⚠️ Notifications denied in browser", "error");
    }
  });
}

function openSettings() {
  document.getElementById("settingsBackdrop").classList.remove("hidden");
  document.body.style.overflow = "hidden";
}

function closeSettings() {
  document.getElementById("settingsBackdrop").classList.add("hidden");
  document.body.style.overflow = "";
}

// ── PWA Install Prompt ──────────────────────────────────────
window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  deferredInstallPrompt = e;
  showToast("📲 Tip: Install as app from Settings!", "info", 5000);
});

document.getElementById("installBtn").addEventListener("click", async () => {
  if (deferredInstallPrompt) {
    deferredInstallPrompt.prompt();
    const { outcome } = await deferredInstallPrompt.userChoice;
    if (outcome === "accepted") showToast("✅ App installed!", "success");
    deferredInstallPrompt = null;
  } else {
    showToast(
      'Open browser menu → "Add to Home Screen" to install',
      "info",
      5000
    );
  }
});

// ── Service Worker Registration ─────────────────────────────
async function registerServiceWorker() {
  if ("serviceWorker" in navigator) {
    try {
      const reg = await navigator.serviceWorker.register("/sw.js");
      console.log("✅ Service Worker registered:", reg.scope);
    } catch (e) {
      console.warn("SW registration failed:", e);
    }
  }
}

// ── Event Listeners ─────────────────────────────────────────
document.getElementById("modalClose").addEventListener("click", closeModal);
document.getElementById("modalBackdrop").addEventListener("click", (e) => {
  if (e.target === e.currentTarget) closeModal();
});

document.getElementById("settingsBtn").addEventListener("click", openSettings);
document.getElementById("settingsClose").addEventListener("click", closeSettings);
document.getElementById("settingsBackdrop").addEventListener("click", (e) => {
  if (e.target === e.currentTarget) closeSettings();
});

document.getElementById("clearAlertsBtn").addEventListener("click", () => {
  alertHistory = [];
  renderAlertHistory();
  document.getElementById("totalAlertsCount").textContent = "0";
  showToast("Alert history cleared", "info");
});

document.getElementById("snapshotBtn").addEventListener("click", async () => {
  showToast("📸 Capturing snapshot…", "info", 1500);
  await fetchLiveSnapshot();
  showToast("✅ Snapshot updated!", "success", 2000);
});

// Unlock audio on first touch (required by mobile browsers)
document.addEventListener(
  "touchstart",
  () => {
    ensureAudio();
  },
  { once: true }
);
document.addEventListener(
  "click",
  () => {
    ensureAudio();
  },
  { once: true }
);

// ── Boot ────────────────────────────────────────────────────
(async function init() {
  await registerServiceWorker();
  initSettings();
  connectSocket();

  // Auto-request notification permission
  if ("Notification" in window && Notification.permission === "default") {
    setTimeout(async () => {
      const perm = await Notification.requestPermission();
      if (perm === "granted") {
        showToast("✅ Notifications enabled!", "success");
      }
    }, 2000);
  }

  console.log("🎥 DashCam Monitor initialized");
})();
