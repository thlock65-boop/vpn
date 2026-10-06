"""
Smart Route VPN - Decision Logic Engine
Implements the exact auto-routing algorithms, rolling window latency analytics,
and plain-language reasoning specified in the project brief.
"""
from typing import List, Dict, Any, Optional
import statistics

BANKING_DOMAINS = {
    "hdfcbank.com",
    "sbi.co.in",
    "icicibank.com",
    "axisbank.com",
    "paytm.com",
    "phonepe.com",
    "bhimupi.org.in",
    "cred.club",
    "zerodha.com",
    "groww.in",
}

class SiteRouteState:
    def __init__(
        self,
        name: str,
        category: str = "general",
        mode: str = "auto",
        direct_history: Optional[List[float]] = None,
        vpn_history: Optional[List[float]] = None,
    ):
        self.name = name.lower().strip()
        self.category = category
        if self.is_banking_site():
            self.category = "banking"
        self.mode = mode.lower()  # "auto", "vpn", "direct"
        # Rolling window of last 4 samples
        self.direct_history: List[float] = direct_history or []
        self.vpn_history: List[float] = vpn_history or []
        self.path: str = "direct"
        self.reason: str = ""
        self.direct_ms: float = 0.0
        self.vpn_ms: float = 0.0

    def is_banking_site(self) -> bool:
        if self.category == "banking":
            return True
        for b in BANKING_DOMAINS:
            if self.name == b or self.name.endswith("." + b):
                return True
        return False

    def add_sample(self, direct_val: float, vpn_val: float):
        """Append a new latency measurement sample and keep the last 4."""
        self.direct_history.append(round(direct_val, 1))
        self.vpn_history.append(round(vpn_val, 1))
        if len(self.direct_history) > 4:
            self.direct_history = self.direct_history[-4:]
        if len(self.vpn_history) > 4:
            self.vpn_history = self.vpn_history[-4:]

    @property
    def direct_avg(self) -> float:
        if not self.direct_history:
            return 0.0
        return round(statistics.mean(self.direct_history), 1)

    @property
    def vpn_avg(self) -> float:
        if not self.vpn_history:
            return 0.0
        return round(statistics.mean(self.vpn_history), 1)

    def evaluate(self, network: str) -> Dict[str, Any]:
        """
        Evaluate route path and plain language reason according to exact rules:
        D = direct average (last 4 samples)
        V = VPN average (last 4 samples)

        if mode == VPN: path = VPN
        if mode == DIRECT: path = DIRECT
        if mode == AUTO:
            if site is banking/UPI: path = DIRECT (+ encrypted DNS if public wifi)
            elif network is PUBLIC:
                if V > D * 1.5: path = DIRECT (VPN too slow)
                else: path = VPN (protection first)
            else: # trusted network
                if V < D * 0.9: path = VPN (at least 10% faster)
                else: path = DIRECT
        """
        D = self.direct_avg
        V = self.vpn_avg
        self.direct_ms = D
        self.vpn_ms = V
        is_banking = self.is_banking_site()

        if self.mode == "vpn":
            self.path = "vpn"
            self.reason = "Manual override: forced through VPN tunnel by user."
        elif self.mode == "direct":
            self.path = "direct"
            self.reason = "Manual override: forced direct connection by user."
        elif self.mode == "auto":
            if is_banking:
                self.path = "direct"
                if network == "public":
                    self.reason = "Banking & UPI safe rule: direct route to avoid VPN fraud blocking; encrypted DoH DNS active."
                else:
                    self.reason = "Banking & UPI safe rule: direct route prevents VPN blocks on trusted network."
            elif network == "public":
                # Public Wi-Fi: Protection first, unless VPN is severely crippled (> 1.5x D)
                if D > 0 and V > (D * 1.5):
                    slower_pct = round(((V - D) / D) * 100)
                    self.path = "direct"
                    self.reason = f"Public Wi-Fi: VPN is {slower_pct}% slower than direct (>50% penalty); safely routed direct."
                else:
                    self.path = "vpn"
                    if D > 0 and V <= D:
                        faster_pct = round(((D - V) / D) * 100) if D > 0 else 0
                        self.reason = f"Public Wi-Fi: protection-first tunnel active (VPN is also {faster_pct}% faster)."
                    else:
                        self.reason = "Public Wi-Fi: protection-first policy routed via encrypted WireGuard tunnel."
            else:
                # Trusted network (Home/Office): Speed first
                # Site moves to VPN only when VPN is at least 10% faster (V < D * 0.9)
                if D > 0 and V < (D * 0.9):
                    faster_pct = round(((D - V) / D) * 100)
                    saved = round(D - V, 1)
                    self.path = "vpn"
                    self.reason = f"VPN is {faster_pct}% faster on last 4 checks (saved ~{saved}ms per request)."
                else:
                    self.path = "direct"
                    if D > 0 and V > D:
                        slower_pct = round(((V - D) / D) * 100)
                        self.reason = f"Trusted network: Direct is faster (VPN has {slower_pct}% overhead)."
                    else:
                        self.reason = "Trusted network: Direct route chosen (VPN is within 10% margin, direct preferred)."

        return self.to_dict()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": "banking" if self.is_banking_site() else self.category,
            "mode": self.mode,
            "path": self.path,
            "direct_ms": self.direct_ms,
            "vpn_ms": self.vpn_ms,
            "reason": self.reason,
            "history_direct": self.direct_history,
            "history_vpn": self.vpn_history,
        }

def compute_avg_saved_ms(sites: List[SiteRouteState]) -> float:
    """
    Computes average ms saved per request versus always going direct.
    For each site:
      if path == 'vpn': saved = D - V (positive when faster, negative if VPN is slower)
      if path == 'direct': saved = 0 (since it is going direct)
    Average is across all configured sites.
    """
    if not sites:
        return 0.0
    saved_list = []
    for s in sites:
        if s.path == "vpn":
            saved_list.append(s.direct_avg - s.vpn_avg)
        else:
            saved_list.append(0.0)
    avg_saved = statistics.mean(saved_list)
    return round(avg_saved, 1)
