"""
Smart Route VPN - Latency Measurement & Network Detection Engine
Performs real HTTPS timing, supports tunnel proxy testing, handles fallback when VPN is unreachable,
and provides simulated latency profiles for demo and presentation purposes.
"""
import asyncio
import time
import subprocess
import random
from typing import Tuple, Dict, Any, Optional
import httpx

# Preset realistic profiles for hackathon demo mode (matching section 11 demo plan)
DEMO_SITE_PROFILES = {
    # Banking: always direct
    "hdfcbank.com": {"direct_base": 38.0, "vpn_base": 65.0, "category": "banking"},
    "sbi.co.in": {"direct_base": 42.0, "vpn_base": 78.0, "category": "banking"},
    # Slow-direct site (e.g. ISP throttling / poor routing, VPN peering is much faster)
    "youtube.com": {"direct_base": 142.0, "vpn_base": 46.0, "category": "general"},
    # Normal sites where direct is faster
    "github.com": {"direct_base": 36.0, "vpn_base": 62.0, "category": "general"},
    "instagram.com": {"direct_base": 44.0, "vpn_base": 72.0, "category": "general"},
    # Within 10% margin
    "chat.openai.com": {"direct_base": 68.0, "vpn_base": 64.0, "category": "general"},
}

DEFAULT_PROXY_URL = "http://127.0.0.1:2080"

async def measure_direct_https(domain: str, timeout_sec: float = 3.5) -> Optional[float]:
    """Measure real direct HTTPS latency in milliseconds."""
    url = f"https://{domain}"
    try:
        async with httpx.AsyncClient(verify=False, timeout=timeout_sec, follow_redirects=True) as client:
            t0 = time.perf_counter()
            resp = await client.head(url)
            elapsed = (time.perf_counter() - t0) * 1000.0
            return round(elapsed, 1)
    except Exception:
        # Fallback to GET with short read
        try:
            async with httpx.AsyncClient(verify=False, timeout=timeout_sec, follow_redirects=True) as client:
                t0 = time.perf_counter()
                resp = await client.get(url, headers={"Range": "bytes=0-100"})
                elapsed = (time.perf_counter() - t0) * 1000.0
                return round(elapsed, 1)
        except Exception:
            return None

async def measure_vpn_https(domain: str, proxy_url: str = DEFAULT_PROXY_URL, timeout_sec: float = 3.5) -> Optional[float]:
    """Measure real HTTPS latency routed through the local VPN tunnel proxy port."""
    url = f"https://{domain}"
    try:
        proxies = {"http://": proxy_url, "https://": proxy_url}
        async with httpx.AsyncClient(proxies=proxies, verify=False, timeout=timeout_sec) as client:
            t0 = time.perf_counter()
            resp = await client.head(url)
            elapsed = (time.perf_counter() - t0) * 1000.0
            return round(elapsed, 1)
    except Exception:
        return None

def generate_simulated_sample(domain: str) -> Tuple[float, float]:
    """
    Generate realistic latency samples with organic jitter (+/- 8%).
    Ensures stable and reproducible demo behavior aligned with the project specification.
    """
    profile = DEMO_SITE_PROFILES.get(domain.lower(), {
        "direct_base": 55.0,
        "vpn_base": 75.0,
        "category": "general"
    })

    direct_base = profile["direct_base"]
    vpn_base = profile["vpn_base"]

    # Organic variance
    jitter_d = random.uniform(-0.06, 0.06) * direct_base
    jitter_v = random.uniform(-0.06, 0.06) * vpn_base

    d_val = max(12.0, round(direct_base + jitter_d, 1))
    v_val = max(15.0, round(vpn_base + jitter_v, 1))
    return d_val, v_val

def detect_os_wifi_state() -> Dict[str, Any]:
    """
    Query Windows OS Wi-Fi state using netsh wlan show interfaces.
    Detects connection status, SSID, and open/secured auth.
    """
    try:
        output = subprocess.check_output(
            ["netsh", "wlan", "show", "interfaces"],
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )
        state = "disconnected"
        ssid = ""
        auth = ""
        is_open = False

        for line in output.splitlines():
            line = line.strip()
            if line.startswith("State") and ":" in line:
                state = line.split(":", 1)[1].strip()
            elif line.startswith("SSID") and not line.startswith("BSSID") and ":" in line:
                ssid = line.split(":", 1)[1].strip()
            elif line.startswith("Authentication") and ":" in line:
                auth = line.split(":", 1)[1].strip()

        if auth.lower() in ("open", "none"):
            is_open = True
        elif "wpa" in auth.lower():
            is_open = False

        return {
            "available": True,
            "connected": (state.lower() == "connected"),
            "ssid": ssid or "Unknown Wi-Fi",
            "auth": auth or "Secured",
            "detected_as_public": is_open or ("free" in ssid.lower() or "cafe" in ssid.lower() or "public" in ssid.lower())
        }
    except Exception as e:
        return {
            "available": False,
            "connected": False,
            "ssid": "",
            "auth": "",
            "detected_as_public": False,
            "error": str(e)
        }
