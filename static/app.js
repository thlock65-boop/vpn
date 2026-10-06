/**
 * Smart Route VPN - Dashboard Client Logic
 * Handles real-time state synchronization, user mode overrides, network switching,
 * config export, and judge walkthrough demonstrations.
 */

// Application State Cache
let currentAppState = {
  network: "trusted",
  simulation_mode: true,
  avg_saved_ms: 0.0,
  sites: [],
  stats: { total_sites: 0, vpn_count: 0, direct_count: 0, banking_count: 0 }
};

// DOM Elements
const avgSavedMetric = document.getElementById("avgSavedMetric");
const networkIndicator = document.getElementById("networkIndicator");
const networkText = document.getElementById("networkText");
const toggleNetworkBtn = document.getElementById("toggleNetworkBtn");
const networkBanner = document.getElementById("networkBanner");
const bannerTitle = document.getElementById("bannerTitle");
const bannerDescription = document.getElementById("bannerDescription");
const wifiSsid = document.getElementById("wifiSsid");
const themeToggleBtn = document.getElementById("themeToggleBtn");

const totalSitesCount = document.getElementById("totalSitesCount");
const vpnSitesCount = document.getElementById("vpnSitesCount");
const directSitesCount = document.getElementById("directSitesCount");
const bankSitesCount = document.getElementById("bankSitesCount");

const sitesTableBody = document.getElementById("sitesTableBody");
const addSiteBtn = document.getElementById("addSiteBtn");
const measureBtn = document.getElementById("measureBtn");
const measureSpinner = document.getElementById("measureSpinner");
const viewConfigBtn = document.getElementById("viewConfigBtn");
const judgeDemoBtn = document.getElementById("judgeDemoBtn");

const addSiteModal = document.getElementById("addSiteModal");
const addSiteForm = document.getElementById("addSiteForm");
const newSiteDomain = document.getElementById("newSiteDomain");
const newSiteCategory = document.getElementById("newSiteCategory");
const closeAddSiteModal = document.getElementById("closeAddSiteModal");
const cancelAddSiteBtn = document.getElementById("cancelAddSiteBtn");

const configModal = document.getElementById("configModal");
const configJsonCode = document.getElementById("configJsonCode");
const copyConfigBtn = document.getElementById("copyConfigBtn");
const closeConfigModal = document.getElementById("closeConfigModal");
const closeConfigModalBtn = document.getElementById("closeConfigModalBtn");

const judgeModal = document.getElementById("judgeModal");
const closeJudgeModal = document.getElementById("closeJudgeModal");
const closeJudgeModalBtn = document.getElementById("closeJudgeModalBtn");

const speedtestDomainSelect = document.getElementById("speedtestDomainSelect");
const runSpeedTestBtn = document.getElementById("runSpeedTestBtn");
const speedTestResult = document.getElementById("speedTestResult");

const simModeTag = document.getElementById("simModeTag");
const toggleSimBtn = document.getElementById("toggleSimBtn");
const toastContainer = document.getElementById("toastContainer");

// Toast Notification
function showToast(message, type = "info") {
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, 3500);
}

// Fetch State
async function fetchState() {
  try {
    const res = await fetch("/state");
    if (!res.ok) throw new Error("Failed to load state");
    const data = await res.json();
    currentAppState = data;
    renderUI();
  } catch (err) {
    console.error("State fetch error:", err);
  }
}

// Render Dashboard
function renderUI() {
  const { network, avg_saved_ms, sites, stats, wifi_detection, simulation_mode } = currentAppState;

  // Header metric
  const sign = avg_saved_ms >= 0 ? "+" : "";
  avgSavedMetric.textContent = `${sign}${avg_saved_ms}`;

  // Network Switcher & Banner
  const isPublic = (network === "public");
  if (isPublic) {
    networkIndicator.parentElement.classList.add("public");
    networkText.textContent = "Public Wi-Fi";
    toggleNetworkBtn.textContent = "Switch to trusted";
    
    networkBanner.className = "network-banner public-banner";
    bannerTitle.textContent = "Operating on untrusted public Wi-Fi (Protection-first policy)";
    bannerDescription.textContent = "Non-banking sites automatically route through the encrypted WireGuard tunnel. Banking and UPI sites route direct with encrypted DoH DNS.";
    wifiSsid.textContent = "Wi-Fi: Untrusted / Open";
  } else {
    networkIndicator.parentElement.classList.remove("public");
    networkText.textContent = "Trusted network";
    toggleNetworkBtn.textContent = "Switch to public Wi-Fi";
    
    networkBanner.className = "network-banner trusted-banner";
    bannerTitle.textContent = "Operating on trusted network (Speed-first policy)";
    bannerDescription.textContent = "Sites route via VPN only when measured to be at least 10% faster than direct. Banking and UPI sites route direct.";
    wifiSsid.textContent = wifi_detection?.ssid ? `Wi-Fi: ${wifi_detection.ssid}` : "Wi-Fi: Secured";
  }

  // Stats
  totalSitesCount.textContent = stats?.total_sites || sites.length;
  vpnSitesCount.textContent = stats?.vpn_count || 0;
  directSitesCount.textContent = stats?.direct_count || 0;
  bankSitesCount.textContent = stats?.banking_count || 0;

  // Simulation tag
  if (simulation_mode) {
    simModeTag.textContent = "Simulation active (reliable demo)";
    toggleSimBtn.textContent = "Switch to real HTTP timing";
  } else {
    simModeTag.textContent = "Live HTTP measurement active";
    toggleSimBtn.textContent = "Switch to simulated demo mode";
  }

  // Render Table Rows
  renderSitesTable(sites);
}

// Render Sites Table
function renderSitesTable(sites) {
  sitesTableBody.innerHTML = "";

  sites.forEach(site => {
    const tr = document.createElement("tr");

    // Max scale for latency bars
    const maxVal = Math.max(site.direct_ms, site.vpn_ms, 120);
    const directPct = Math.min(100, Math.round((site.direct_ms / maxVal) * 100));
    const vpnPct = Math.min(100, Math.round((site.vpn_ms / maxVal) * 100));

    const isVpn = site.path === "vpn";
    const isBanking = site.category === "banking";

    tr.innerHTML = `
      <td>
        <div class="domain-cell">
          <span class="domain-name">${escapeHtml(site.name)}</span>
          <span class="category-badge ${isBanking ? 'banking' : ''}">
            ${isBanking ? '🛡️ Banking / UPI' : '🌐 Web Service'}
          </span>
        </div>
      </td>
      <td>
        <div class="route-badge ${isVpn ? 'vpn' : 'direct'}">
          ${isVpn ? '🔒 VPN Tunnel' : '⚡ Direct Path'}
        </div>
      </td>
      <td>
        <div class="latency-block">
          <div class="latency-values">
            <span class="val-item">
              <span class="val-label">Direct:</span>
              <span class="val-num direct-val">${site.direct_ms}ms</span>
            </span>
            <span class="val-item">
              <span class="val-label">VPN:</span>
              <span class="val-num vpn-val">${site.vpn_ms}ms</span>
            </span>
          </div>
          <div class="latency-bars">
            <div class="bar-track" title="Direct latency: ${site.direct_ms}ms">
              <div class="bar-fill direct" style="width: ${directPct}%"></div>
            </div>
            <div class="bar-track" title="VPN latency: ${site.vpn_ms}ms">
              <div class="bar-fill vpn" style="width: ${vpnPct}%"></div>
            </div>
          </div>
        </div>
      </td>
      <td>
        <p class="reason-text">${escapeHtml(site.reason)}</p>
      </td>
      <td>
        <div class="mode-group-cell">
          <div class="mode-toggle-group" role="group" aria-label="Routing mode for ${escapeHtml(site.name)}">
            <button class="mode-btn ${site.mode === 'auto' ? 'active mode-auto' : ''}" onclick="setSiteMode('${escapeHtml(site.name)}', 'auto')" title="Auto decision engine">Auto</button>
            <button class="mode-btn ${site.mode === 'vpn' ? 'active mode-vpn' : ''}" onclick="setSiteMode('${escapeHtml(site.name)}', 'vpn')" title="Force through VPN">VPN</button>
            <button class="mode-btn ${site.mode === 'direct' ? 'active mode-direct' : ''}" onclick="setSiteMode('${escapeHtml(site.name)}', 'direct')" title="Force Direct">Direct</button>
          </div>
          <button class="del-btn" onclick="deleteSite('${escapeHtml(site.name)}')" title="Remove domain" aria-label="Remove domain">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
          </button>
        </div>
      </td>
    `;
    sitesTableBody.appendChild(tr);
  });
}

// Helpers
function escapeHtml(str) {
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// Network Toggle Handler
toggleNetworkBtn.addEventListener("click", async () => {
  const nextType = currentAppState.network === "public" ? "trusted" : "public";
  try {
    const res = await fetch("/network", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type: nextType })
    });
    if (!res.ok) throw new Error("Failed to change network");
    currentAppState = await res.json();
    renderUI();
    showToast(`Switched to ${nextType === "public" ? "Public Wi-Fi (Protection-First)" : "Trusted Network (Speed-First)"}`, "success");
  } catch (err) {
    showToast("Error updating network: " + err.message, "warn");
  }
});

// Set Site Mode Handler
async function setSiteMode(name, mode) {
  try {
    const res = await fetch(`/site/${encodeURIComponent(name)}/mode`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode })
    });
    if (!res.ok) throw new Error("Failed to update site mode");
    await fetchState();
    showToast(`Updated ${name} mode to ${mode.toUpperCase()}`, "info");
  } catch (err) {
    showToast("Error: " + err.message, "warn");
  }
}

// Delete Site Handler
async function deleteSite(name) {
  if (!confirm(`Are you sure you want to remove ${name} from routing rules?`)) return;
  try {
    const res = await fetch(`/site/${encodeURIComponent(name)}`, {
      method: "DELETE"
    });
    if (!res.ok) throw new Error("Failed to delete site");
    await fetchState();
    showToast(`Removed ${name}`, "info");
  } catch (err) {
    showToast("Error: " + err.message, "warn");
  }
}

// Add Site Form Submission
addSiteForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const domain = newSiteDomain.value.trim();
  const category = newSiteCategory.value;
  if (!domain) return;

  try {
    const res = await fetch("/site", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: domain, category: category })
    });
    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.detail || "Failed to add site");
    }
    addSiteModal.style.display = "none";
    newSiteDomain.value = "";
    await fetchState();
    showToast(`Added ${domain}`, "success");
  } catch (err) {
    showToast("Error: " + err.message, "warn");
  }
});

// Latency Measurement Handler
measureBtn.addEventListener("click", async () => {
  measureSpinner.style.animation = "spin 0.8s linear infinite";
  try {
    const res = await fetch("/measure", { method: "POST" });
    if (!res.ok) throw new Error("Measurement failed");
    const data = await res.json();
    currentAppState = data.state;
    renderUI();
    showToast("Refreshed latency measurements across all paths", "success");
  } catch (err) {
    showToast("Measurement error: " + err.message, "warn");
  } finally {
    measureSpinner.style.animation = "";
  }
});

// View sing-box Config
viewConfigBtn.addEventListener("click", async () => {
  try {
    const res = await fetch("/config");
    if (!res.ok) throw new Error("Failed to generate sing-box configuration");
    const cfg = await res.json();
    configJsonCode.textContent = JSON.stringify(cfg, null, 2);
    configModal.style.display = "flex";
  } catch (err) {
    showToast("Config error: " + err.message, "warn");
  }
});

// Copy Config Button
copyConfigBtn.addEventListener("click", () => {
  navigator.clipboard.writeText(configJsonCode.textContent).then(() => {
    showToast("Copied sing-box configuration JSON to clipboard!", "success");
  }).catch(() => {
    showToast("Failed to copy to clipboard", "warn");
  });
});

// Speed Test Tool (Section 11)
runSpeedTestBtn.addEventListener("click", async () => {
  const domain = speedtestDomainSelect.value;
  runSpeedTestBtn.disabled = true;
  runSpeedTestBtn.textContent = "Testing...";
  speedTestResult.style.display = "block";
  speedTestResult.innerHTML = `<p style="color: var(--text-secondary);">Measuring 3 consecutive bursts through Direct and VPN tunnels for <strong>${domain}</strong>...</p>`;

  try {
    const res = await fetch("/speedtest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ site_name: domain })
    });
    if (!res.ok) throw new Error("Speed test failed");
    const data = await res.json();

    speedTestResult.innerHTML = `
      <div class="result-columns">
        <div class="res-col">
          <span class="res-label">Direct path avg</span>
          <span class="res-num" style="color: var(--amber-direct-light);">${data.direct_avg_ms} ms</span>
          <span style="font-size: 0.72rem; color: var(--text-muted); font-family: var(--font-mono);">${data.direct_runs.join(", ")} ms</span>
        </div>
        <div class="res-col">
          <span class="res-label">VPN tunnel avg</span>
          <span class="res-num" style="color: var(--teal-vpn-light);">${data.vpn_avg_ms} ms</span>
          <span style="font-size: 0.72rem; color: var(--text-muted); font-family: var(--font-mono);">${data.vpn_runs.join(", ")} ms</span>
        </div>
        <div class="res-col">
          <div class="res-summary">
            ${data.summary}
          </div>
        </div>
      </div>
    `;
  } catch (err) {
    speedTestResult.innerHTML = `<p style="color: var(--danger);">Speed test error: ${err.message}</p>`;
  } finally {
    runSpeedTestBtn.disabled = false;
    runSpeedTestBtn.textContent = "Run test burst";
  }
});

// Judge Demo Walkthrough (Section 11 Script)
window.runJudgeStep = async function(step) {
  if (step === 1) {
    // Step 1: Start on Home network
    await fetch("/network", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type: "trusted" })
    });
    await fetch("/measure", { method: "POST" });
    await fetchState();
    showToast("Judge Step 1 Applied: On Home Network. Auto picks VPN for slow-direct (YouTube) & Direct for the rest.", "success");
    judgeModal.style.display = "none";
  } else if (step === 2) {
    // Step 2: Switch to Public Wi-Fi
    await fetch("/network", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type: "public" })
    });
    await fetch("/measure", { method: "POST" });
    await fetchState();
    showToast("Judge Step 2 Applied: Joined Public Wi-Fi! Protection active for normal sites; Banking stays safely on Direct + DoH DNS.", "success");
    judgeModal.style.display = "none";
  } else if (step === 3) {
    // Step 3: Run speed test
    judgeModal.style.display = "none";
    document.getElementById("speedTestSection").scrollIntoView({ behavior: "smooth" });
    speedtestDomainSelect.value = "youtube.com";
    runSpeedTestBtn.click();
    showToast("Judge Step 3 Applied: Running real before-and-after speed verification on YouTube.", "info");
  }
};

// Simulation Toggle
toggleSimBtn.addEventListener("click", async () => {
  const nextSim = !currentAppState.simulation_mode;
  try {
    const res = await fetch("/simulation/toggle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: nextSim })
    });
    if (!res.ok) throw new Error("Toggle simulation failed");
    await fetchState();
    showToast(`Simulation mode ${nextSim ? "Enabled" : "Disabled (Live HTTP timing)"}`, "info");
  } catch (err) {
    showToast("Error: " + err.message, "warn");
  }
});

// Modal Open/Close Controls
addSiteBtn.addEventListener("click", () => { addSiteModal.style.display = "flex"; newSiteDomain.focus(); });
closeAddSiteModal.addEventListener("click", () => { addSiteModal.style.display = "none"; });
cancelAddSiteBtn.addEventListener("click", () => { addSiteModal.style.display = "none"; });

closeConfigModal.addEventListener("click", () => { configModal.style.display = "none"; });
closeConfigModalBtn.addEventListener("click", () => { configModal.style.display = "none"; });

judgeDemoBtn.addEventListener("click", () => { judgeModal.style.display = "flex"; });
closeJudgeModal.addEventListener("click", () => { judgeModal.style.display = "none"; });
closeJudgeModalBtn.addEventListener("click", () => { judgeModal.style.display = "none"; });

// Close on backdrop click or ESC
window.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    addSiteModal.style.display = "none";
    configModal.style.display = "none";
    judgeModal.style.display = "none";
  }
});

// Theme Switcher
themeToggleBtn.addEventListener("click", () => {
  const currentTheme = document.documentElement.getAttribute("data-theme") || "dark";
  const newTheme = currentTheme === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", newTheme);
  localStorage.setItem("smart_route_theme", newTheme);
});

// Restore Theme
const savedTheme = localStorage.getItem("smart_route_theme");
if (savedTheme) {
  document.documentElement.setAttribute("data-theme", savedTheme);
}

// Add CSS keyframe for spinner
const styleSheet = document.createElement("style");
styleSheet.textContent = `@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`;
document.head.appendChild(styleSheet);

// Initial Load & periodic refresh
fetchState();
setInterval(fetchState, 5000);
