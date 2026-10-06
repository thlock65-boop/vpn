"""
Smart Route VPN - Automated Test Suite
Verifies all Section 10 Acceptance Criteria and core business logic.
"""
# Standalone standard library tests
from decision_engine import SiteRouteState, compute_avg_saved_ms
from singbox_generator import generate_singbox_config

def test_banking_sites_stay_direct_always_in_auto():
    """Criterion: Banking sites stay direct in every Auto case and show note about encrypted DNS on public wifi."""
    # Test on trusted network
    site_hdfc = SiteRouteState("hdfcbank.com", category="banking", mode="auto")
    site_hdfc.add_sample(direct_val=40.0, vpn_val=20.0) # Even if VPN is 50% faster!
    res_trusted = site_hdfc.evaluate("trusted")
    assert res_trusted["path"] == "direct", "Banking site must stay direct on trusted network"
    assert "Banking" in res_trusted["reason"]

    # Test on public network
    res_public = site_hdfc.evaluate("public")
    assert res_public["path"] == "direct", "Banking site must stay direct on public network"
    assert "encrypted DoH DNS" in res_public["reason"] or "encrypted" in res_public["reason"]

def test_trusted_network_speed_first_rule():
    """Criterion: In Auto on a trusted network, a site moves to VPN only when VPN is at least 10% faster (V < D * 0.9)."""
    site = SiteRouteState("youtube.com", category="general", mode="auto")
    
    # VPN 60% faster (V = 40, D = 100) -> Should choose VPN
    site.add_sample(100.0, 40.0)
    res = site.evaluate("trusted")
    assert res["path"] == "vpn"
    assert "faster" in res["reason"]

    # VPN only 5% faster (V = 95, D = 100) -> Does not satisfy 10% faster -> Direct
    site2 = SiteRouteState("github.com", category="general", mode="auto")
    site2.add_sample(100.0, 95.0)
    res2 = site2.evaluate("trusted")
    assert res2["path"] == "direct"
    assert "Trusted network" in res2["reason"]

    # Direct is faster (V = 80, D = 40) -> Direct
    site3 = SiteRouteState("fastsite.com", category="general", mode="auto")
    site3.add_sample(40.0, 80.0)
    res3 = site3.evaluate("trusted")
    assert res3["path"] == "direct"

def test_public_network_protection_first_rule():
    """Criterion: Switching to public wifi moves non-banking Auto sites to VPN unless VPN is more than 50% slower (V > D * 1.5)."""
    site = SiteRouteState("github.com", category="general", mode="auto")
    
    # VPN is slightly slower (V = 60, D = 50) -> Within 50% overhead -> Should pick VPN for protection
    site.add_sample(50.0, 60.0)
    res_pub = site.evaluate("public")
    assert res_pub["path"] == "vpn"
    assert "protection-first" in res_pub["reason"]

    # VPN is drastically crippled (V = 160, D = 50 -> V > 50 * 1.5 = 75) -> Should fall back to Direct
    site_slow = SiteRouteState("heavy.com", category="general", mode="auto")
    site_slow.add_sample(50.0, 160.0)
    res_slow = site_slow.evaluate("public")
    assert res_slow["path"] == "direct"
    assert "slower than direct" in res_slow["reason"]

def test_manual_override_modes():
    """Criterion: Changing a site's mode changes its real route."""
    site = SiteRouteState("example.com", category="general", mode="vpn")
    site.add_sample(20.0, 200.0) # Even if direct is way faster
    res = site.evaluate("trusted")
    assert res["path"] == "vpn"
    assert "Manual override" in res["reason"]

    site.mode = "direct"
    res2 = site.evaluate("public") # Even on public wifi
    assert res2["path"] == "direct"
    assert "Manual override" in res2["reason"]

def test_rolling_window_of_4_samples():
    """Criterion: Keep a rolling window of the last 4 samples per path."""
    site = SiteRouteState("rolling.com", category="general", mode="auto")
    for i in range(10):
        site.add_sample(float(i * 10), float(i * 5))
    
    assert len(site.direct_history) == 4
    assert len(site.vpn_history) == 4
    assert site.direct_history == [60.0, 70.0, 80.0, 90.0]
    assert site.vpn_history == [30.0, 35.0, 40.0, 45.0]

def test_valid_singbox_config_generation():
    """Criterion: Generated config is valid sing-box JSON and matches dashboard rules."""
    sites = [
        {"name": "hdfcbank.com", "path": "direct"},
        {"name": "youtube.com", "path": "vpn"},
        {"name": "github.com", "path": "direct"}
    ]
    cfg = generate_singbox_config(sites, network="trusted")
    assert "dns" in cfg
    assert "inbounds" in cfg
    assert "outbounds" in cfg
    assert "route" in cfg
    
    # Check outbounds
    outbound_tags = [o["tag"] for o in cfg["outbounds"]]
    assert "wireguard-out" in outbound_tags
    assert "direct-out" in outbound_tags

    # Check route rules
    rules = cfg["route"]["rules"]
    direct_rule = next(r for r in rules if r.get("outbound") == "direct-out")
    vpn_rule = next(r for r in rules if r.get("outbound") == "wireguard-out")
    
    assert "hdfcbank.com" in direct_rule["domain_suffix"]
    assert "github.com" in direct_rule["domain_suffix"]
    assert "youtube.com" in vpn_rule["domain_suffix"]

if __name__ == "__main__":
    test_banking_sites_stay_direct_always_in_auto()
    test_trusted_network_speed_first_rule()
    test_public_network_protection_first_rule()
    test_manual_override_modes()
    test_rolling_window_of_4_samples()
    test_valid_singbox_config_generation()
    print("ALL TESTS PASSED SUCCESSFULLY!")
