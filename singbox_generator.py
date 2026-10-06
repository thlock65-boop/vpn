"""
Smart Route VPN - sing-box Configuration Generator
Produces valid sing-box JSON configuration matching the dashboard routing decisions,
with encrypted DNS (DoH), WireGuard outbound, direct outbound, and domain_suffix rules.
"""
import json
from typing import List, Dict, Any

DEFAULT_WG_CONFIG = {
    "server": "198.51.100.12",  # VPS WireGuard server IP
    "server_port": 51820,
    "local_address": ["10.8.0.2/32", "fd00::2/128"],
    "private_key": "aHVudGVyMmh1bnRlcjJodW50ZXIyaHVudGVyMmh1bnRlcjI=",
    "peer_public_key": "cHVibGljX2tleV9wbGFjZWhvbGRlcg1234567890123456=",
    "mtu": 1420
}

def generate_singbox_config(
    sites: List[Dict[str, Any]],
    network: str = "trusted",
    wg_settings: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Build a complete, syntactically valid sing-box configuration JSON.
    Routes domains based on active path (vpn -> wireguard-out, direct -> direct-out).
    Applies encrypted DNS over HTTPS (Cloudflare 1.1.1.1 / Quad9).
    """
    wg = wg_settings or DEFAULT_WG_CONFIG

    # Categorize domains by active path
    vpn_domains = []
    direct_domains = []

    for site in sites:
        name = site.get("name", "").strip().lower()
        if not name:
            continue
        path = site.get("path", "direct")
        if path == "vpn":
            vpn_domains.append(name)
        else:
            direct_domains.append(name)

    route_rules = []

    # DNS routing rule
    route_rules.append({
        "protocol": "dns",
        "outbound": "dns-out"
    })

    # Banking/UPI safety & explicit Direct domains
    if direct_domains:
        route_rules.append({
            "domain_suffix": direct_domains,
            "outbound": "direct-out"
        })

    # VPN domains (accelerated or public-wifi protected)
    if vpn_domains:
        route_rules.append({
            "domain_suffix": vpn_domains,
            "outbound": "wireguard-out"
        })

    # Default fallback
    # If on public Wi-Fi, default is wireguard-out for untrusted untracked domains
    # If on trusted network, default is direct-out
    final_outbound = "wireguard-out" if network == "public" else "direct-out"

    config = {
        "$schema": "https://raw.githubusercontent.com/SagerNet/sing-box/main/schemas/config.json",
        "log": {
            "level": "info",
            "timestamp": True
        },
        "dns": {
            "servers": [
                {
                    "tag": "doh-cloudflare",
                    "address": "https://1.1.1.1/dns-query",
                    "address_resolver": "local-dns",
                    "detour": "direct-out"
                },
                {
                    "tag": "doh-quad9",
                    "address": "https://9.9.9.9/dns-query",
                    "address_resolver": "local-dns",
                    "detour": "direct-out"
                },
                {
                    "tag": "local-dns",
                    "address": "local",
                    "detour": "direct-out"
                }
            ],
            "rules": [
                {
                    "outbound": "any",
                    "server": "doh-cloudflare"
                }
            ],
            "strategy": "prefer_ipv4"
        },
        "inbounds": [
            {
                "type": "mixed",
                "tag": "mixed-in",
                "listen": "127.0.0.1",
                "listen_port": 2080,
                "sniff": True,
                "sniff_override_destination": True
            },
            {
                "type": "tun",
                "tag": "tun-in",
                "interface_name": "tun0",
                "inet4_address": "172.19.0.1/30",
                "auto_route": True,
                "strict_route": False,
                "stack": "system",
                "sniff": True
            }
        ],
        "outbounds": [
            {
                "type": "direct",
                "tag": "direct-out"
            },
            {
                "type": "wireguard",
                "tag": "wireguard-out",
                "server": wg.get("server", "198.51.100.12"),
                "server_port": wg.get("server_port", 51820),
                "local_address": wg.get("local_address", ["10.8.0.2/32"]),
                "private_key": wg.get("private_key", "aHVudGVyMmh1bnRlcjJodW50ZXIyaHVudGVyMmh1bnRlcjI="),
                "peer_public_key": wg.get("peer_public_key", "cHVibGljX2tleV9wbGFjZWhvbGRlcg1234567890123456="),
                "mtu": wg.get("mtu", 1420)
            },
            {
                "type": "dns",
                "tag": "dns-out"
            },
            {
                "type": "block",
                "tag": "block-out"
            }
        ],
        "route": {
            "rules": route_rules,
            "final": final_outbound,
            "auto_detect_interface": True
        }
    }

    return config

def get_singbox_json_string(sites: List[Dict[str, Any]], network: str = "trusted", indent: int = 2) -> str:
    cfg = generate_singbox_config(sites, network)
    return json.dumps(cfg, indent=indent)
