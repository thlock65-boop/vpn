# Smart Route VPN

> **Hackathon Track: Open Innovation (Real-World Problem)**  
> Measurement-driven per-domain auto-routing engine with untrusted public Wi-Fi protection and zero-disruption banking safety.

---

## 1. Problem Statement

Millions of people in India use shared, untrusted public Wi-Fi networks (cafes, railway stations, universities, co-working spaces) for everyday browsing, UPI payments, and banking.

1. **Untrusted Networks**: Anyone on the local network can snoop on plain DNS requests, launch captive portal downgrades, or attempt spoofing.
2. **All-or-Nothing VPN Dilemma**: Commercial VPNs route 100% of device traffic through the tunnel. This adds massive latency, and **breaks UPI & Indian banking apps** (HDFC, SBI, ICICI, Zerodha, Paytm) which immediately trigger fraud blocks on VPN IP ranges. Consequently, users turn their VPN completely off precisely when they are most exposed.
3. **Suboptimal Routing**: For some services (e.g. video streams or peering bottlenecks), the ISP path is throttled and a VPN is faster. For others, a VPN introduces unnecessary network hops. Users have had no intelligent way to route traffic on a per-domain basis.

---

## 2. Solution & Core Innovations

**Smart Route VPN** pairs a local rule-based proxy (`sing-box`) with an intelligent **Routing Brain** and **Real-Time Dashboard**:

- **Measurement-Driven Auto-Routing**: Constantly samples HTTPS round-trip latency through both Direct and VPN paths, storing a rolling window of the last 4 measurements per domain.
- **Banking & UPI Safe Rule**: Banking and financial domains always stay on the direct route to guarantee zero transaction failures, but automatically upgrade to encrypted DNS over HTTPS (DoH) on untrusted networks.
- **Public Wi-Fi Awareness**: Instantly shifts into *protection-first* mode on public or open Wi-Fi networks, funneling untrusted traffic into an encrypted WireGuard tunnel unless the VPN path is severely degraded (>50% penalty).
- **Trusted Network Speed-First Rule**: On home or office Wi-Fi, traffic routes via VPN *only* if the VPN is measured to be at least 10% faster ($V < D \times 0.9$).
- **Live Proof in Milliseconds**: Quantifies exact millisecond savings per request versus always going direct (`avg_saved_ms`).

---

## 3. Architecture

```text
[ Dashboard Web UI ] <==== REST API ====> [ Routing Brain (FastAPI) ] ===> [ sing-box Client ]
 (Teal=VPN, Amber=Direct)                  (Measures, Decides, Configures)    (domain_suffix rules)
                                                                                  |
                                                                        +---------+---------+
                                                                        |                   |
                                                                   Direct (ISP)      WireGuard Tunnel
                                                                        |                   |
                                                                    Internet          Cloud VPS
```

### Component Breakdown
| Component | Implementation | Role |
| :--- | :--- | :--- |
| **Routing Brain** | Python (FastAPI + httpx) | Calculates rolling averages ($D, V$), evaluates exact decision rules, generates plain-language reasons, updates `sing-box` configs. |
| **Domain Proxy** | `sing-box` (v1.8+) | Performs domain-suffix routing, mixed HTTP/SOCKS5 proxy, TUN virtual interface, and DNS-over-HTTPS (1.1.1.1 / Quad9). |
| **Tunnel** | WireGuard | High-performance, kernel-level encrypted tunnel to a cloud VPS. |
| **Dashboard** | Modern HTML5/CSS/JS | Visualizes live state, latency charts, real-time mode overrides, network toggle, and config export. |

---

## 4. Exact Decision Logic

For each tracked domain, a rolling window of the **last 4 samples** is maintained per path ($D = \text{direct average}$, $V = \text{VPN average}$):

```python
if mode == "vpn":
    path = "vpn"
elif mode == "direct":
    path = "direct"
elif mode == "auto":
    if site is banking/UPI:
        path = "direct"  # (+ encrypted DoH DNS if on public Wi-Fi)
    elif network == "public":
        if V > D * 1.5:
            path = "direct"  # VPN is too slow (>50% penalty)
        else:
            path = "vpn"     # Protection-first policy
    else: # Trusted network (Speed-first)
        if V < D * 0.9:
            path = "vpn"     # VPN is at least 10% faster
        else:
            path = "direct"  # Direct is optimal
```

---

## 5. Quick Start & Running the Prototype

### Prerequisites
- Python 3.10+
- Installed packages: `fastapi`, `uvicorn`, `httpx`, `pydantic`

### Launch the Application
Navigate to the project directory and run:

```bash
cd C:\Users\Utkarsh\.gemini\antigravity\scratch\smart-route-vpn
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Open your browser at:  
👉 **`http://127.0.0.1:8000`**

### Running the Test Suite
Verify all acceptance criteria and mathematical edge cases:

```bash
python test_smart_route.py
```

---

## 6. Setting Up WireGuard VPS & sing-box (Production Tunnel)

### Step 1: Deploy WireGuard on Cloud VPS
On an Ubuntu 22.04 / 24.04 VPS (DigitalOcean, AWS, Oracle Cloud, Linode):

```bash
# 1. Install WireGuard
curl -O https://raw.githubusercontent.com/angristan/wireguard-install/master/wireguard-install.sh
chmod +x wireguard-install.sh
./wireguard-install.sh

# Follow prompts to set endpoint IP and generate client configuration (e.g. client.conf)
```

### Step 2: Extract Keys into `singbox_generator.py`
In `client.conf`, locate:
- `PrivateKey`: Put into `private_key`
- `Address`: Put into `local_address`
- `PublicKey`: Put into `peer_public_key`
- `Endpoint`: Put into `server` and `server_port`

### Step 3: Run sing-box Client
Download `sing-box` for Windows or Linux from [github.com/SagerNet/sing-box/releases](https://github.com/SagerNet/sing-box/releases).

```bash
# Generate current config from dashboard, click "Export sing-box config", save as config.json
sing-box run -c config.json
```

---

## 7. Judge Demo Walkthrough (Section 11)

An interactive **Judge Demo Mode** button is embedded in the top toolbar. It steps through the exact demo plan:

1. **Step 1: Start on Home Network**
   - Click **"Judge Demo Mode"** &rarr; **"Apply Step 1 (Home Network)"**.
   - Review the dashboard:
     - Notice `youtube.com` (ISP-throttled simulation) routes to **Teal (VPN)** because it is >10% faster.
     - Notice `github.com` and `instagram.com` route to **Amber (Direct)** because Direct is faster on home Wi-Fi.
     - Header shows positive saved milliseconds (`+15.8 ms/req`).
2. **Step 2: Press 'Join Public Wi-Fi'**
   - Click **"Apply Step 2 (Public Wi-Fi)"** or toggle the top network switch.
   - Watch the instant policy shift:
     - All general domains switch to **Teal (VPN Tunnel)** for untrusted Wi-Fi protection.
     - Crucially, **`hdfcbank.com` and `sbi.co.in` stay on Amber (Direct)** with an explicit badge: *"Banking & UPI safe rule: direct route to avoid VPN fraud blocking; encrypted DoH DNS active."*
3. **Step 3: Run Live Speed Test Burst**
   - Click **"Apply Step 3 (Run Speed Test)"** or trigger the Speed Verification tool on `youtube.com`.
   - The test runs 3 consecutive bursts through both paths, computing exact averages and displaying:
     - *`VPN route is 67.0% faster (94.2ms saved per request)`*
4. **Step 4: The Final Pitch**
   - *"People turn VPNs off in India because they are slow and break banking. Smart Route VPN fixes that: banking always works, public Wi-Fi is protected, and speeds are verified with real numbers."*

---

## 8. Acceptance Criteria Verification Checklist

- [x] **Real route updates**: Changing a site's mode in the dashboard changes its real route within a few seconds.
- [x] **Trusted 10% threshold**: In Auto on trusted network, moves to VPN only when $V < D \times 0.9$.
- [x] **Public Wi-Fi protection & 50% cutoff**: Switching to public Wi-Fi moves non-banking Auto sites to VPN unless $V > D \times 1.5$.
- [x] **Banking immunity**: Banking sites stay direct in every Auto scenario and show encrypted DNS notice on public Wi-Fi.
- [x] **Plain-language reasons**: Every site row articulates the exact reasoning, both latencies, and current path.
- [x] **Valid sing-box config**: Config output conforms to valid sing-box format with `domain_suffix` matching.
- [x] **Graceful VPN fallback**: App continues running and provides transparent fallback when VPN server is unreachable.
