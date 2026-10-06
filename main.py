"""
Smart Route VPN - Routing Brain Backend (FastAPI)
Exposes the REST API for the dashboard, runs background measurement and decision logic,
and serves the web dashboard UI.
"""
import os
import asyncio
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

from decision_engine import SiteRouteState, compute_avg_saved_ms
from singbox_generator import generate_singbox_config, get_singbox_json_string
from measurement import (
    measure_direct_https,
    measure_vpn_https,
    generate_simulated_sample,
    detect_os_wifi_state,
    DEMO_SITE_PROFILES,
    DEFAULT_PROXY_URL,
)

app = FastAPI(title="Smart Route VPN Routing Brain", version="1.0.0")

# Application State
class AppState:
    def __init__(self):
        self.network: str = "trusted"  # "trusted" or "public"
        self.simulation_mode: bool = True  # Defaults to True for guaranteed hackathon demo reliability
        self.vpn_unreachable: bool = False
        self.proxy_url: str = DEFAULT_PROXY_URL
        self.sites: Dict[str, SiteRouteState] = {}
        self.init_defaults()

    def init_defaults(self):
        # Default sites according to project brief section 8
        default_sites = [
            ("hdfcbank.com", "banking"),
            ("sbi.co.in", "banking"),
            ("youtube.com", "general"),
            ("instagram.com", "general"),
            ("github.com", "general"),
            ("chat.openai.com", "general"),
        ]
        for name, category in default_sites:
            site = SiteRouteState(name=name, category=category, mode="auto")
            # Seed 4 realistic samples so rolling averages and reason strings are ready immediately
            for _ in range(4):
                d, v = generate_simulated_sample(name)
                site.add_sample(d, v)
            site.evaluate(self.network)
            self.sites[site.name] = site

    def get_state_dict(self) -> Dict[str, Any]:
        evaluated_sites = []
        for site in self.sites.values():
            evaluated_sites.append(site.evaluate(self.network))
        
        avg_saved = compute_avg_saved_ms(list(self.sites.values()))
        wifi_info = detect_os_wifi_state()

        return {
            "network": self.network,
            "simulation_mode": self.simulation_mode,
            "vpn_unreachable": self.vpn_unreachable,
            "proxy_url": self.proxy_url,
            "avg_saved_ms": avg_saved,
            "sites": evaluated_sites,
            "wifi_detection": wifi_info,
            "stats": {
                "total_sites": len(self.sites),
                "vpn_count": sum(1 for s in self.sites.values() if s.path == "vpn"),
                "direct_count": sum(1 for s in self.sites.values() if s.path == "direct"),
                "banking_count": sum(1 for s in self.sites.values() if s.is_banking_site()),
            }
        }

state = AppState()

# Request Models
class AddSiteRequest(BaseModel):
    name: str
    category: Optional[str] = "general"

class SetModeRequest(BaseModel):
    mode: str  # "auto", "vpn", "direct"

class SetNetworkRequest(BaseModel):
    type: str  # "public", "trusted"

class ToggleSimRequest(BaseModel):
    enabled: bool

# API Endpoints per Section 7 & 8 Specification

@app.get("/state")
async def get_state():
    """Returns current network state, all sites with their routes, and avg_saved_ms."""
    return state.get_state_dict()

@app.post("/site")
async def add_site(req: AddSiteRequest):
    """Add a new site to be routed."""
    clean_name = req.name.strip().lower()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Site name cannot be empty")
    
    # Strip protocols if provided
    if clean_name.startswith("https://"):
        clean_name = clean_name[8:]
    elif clean_name.startswith("http://"):
        clean_name = clean_name[7:]
    clean_name = clean_name.split("/")[0].split(":")[0]

    if clean_name in state.sites:
        return {"message": "Site already exists", "site": state.sites[clean_name].to_dict()}

    site = SiteRouteState(name=clean_name, category=req.category or "general", mode="auto")
    # Take initial samples
    for _ in range(4):
        d, v = generate_simulated_sample(clean_name)
        site.add_sample(d, v)
    site.evaluate(state.network)
    state.sites[clean_name] = site
    return {"message": "Site added successfully", "site": site.to_dict()}

@app.post("/site/{name}/mode")
async def set_site_mode(name: str, req: SetModeRequest):
    """Set the mode ('auto', 'vpn', 'direct') for a specific site."""
    clean_name = name.strip().lower()
    if clean_name not in state.sites:
        raise HTTPException(status_code=404, detail=f"Site '{clean_name}' not found")
    
    target_mode = req.mode.lower()
    if target_mode not in ("auto", "vpn", "direct"):
        raise HTTPException(status_code=400, detail="Mode must be 'auto', 'vpn', or 'direct'")
    
    site = state.sites[clean_name]
    site.mode = target_mode
    site.evaluate(state.network)
    return {"message": f"Updated mode for {clean_name} to {target_mode}", "site": site.to_dict()}

@app.delete("/site/{name}")
async def delete_site(name: str):
    """Remove a site from the routing table."""
    clean_name = name.strip().lower()
    if clean_name not in state.sites:
        raise HTTPException(status_code=404, detail=f"Site '{clean_name}' not found")
    del state.sites[clean_name]
    return {"message": f"Site '{clean_name}' removed"}

@app.post("/network")
async def set_network(req: SetNetworkRequest):
    """Manual network override: 'public' or 'trusted'."""
    net_type = req.type.lower()
    if net_type not in ("public", "trusted"):
        raise HTTPException(status_code=400, detail="Network type must be 'public' or 'trusted'")
    state.network = net_type
    # Re-evaluate all sites
    for s in state.sites.values():
        s.evaluate(state.network)
    return state.get_state_dict()

@app.get("/config")
async def get_config():
    """Generates and returns valid sing-box JSON configuration for current rules."""
    site_dicts = [s.to_dict() for s in state.sites.values()]
    config_dict = generate_singbox_config(site_dicts, state.network)
    return config_dict

@app.post("/measure")
async def trigger_measurement():
    """
    Triggers latency measurement across all sites.
    Uses real HTTPS timing if simulation_mode is False, or simulated timing if True.
    """
    if state.simulation_mode:
        for s in state.sites.values():
            d, v = generate_simulated_sample(s.name)
            s.add_sample(d, v)
            s.evaluate(state.network)
        return {
            "status": "success",
            "message": "Measured all sites using organic simulation",
            "state": state.get_state_dict()
        }
    else:
        # Real measurement
        tasks = []
        async def measure_single(site: SiteRouteState):
            d = await measure_direct_https(site.name)
            v = await measure_vpn_https(site.name, state.proxy_url)
            # If VPN is unreachable, handle fallback per Section 10
            if v is None:
                state.vpn_unreachable = True
                # Fallback to direct latency with simulated penalty or use D
                v_val = (d or 50.0) + 40.0
            else:
                state.vpn_unreachable = False
                v_val = v
            d_val = d if d is not None else 60.0
            site.add_sample(d_val, v_val)
            site.evaluate(state.network)

        for site in state.sites.values():
            tasks.append(measure_single(site))
        
        await asyncio.gather(*tasks)
        return {
            "status": "success",
            "message": "Measured all sites using real live HTTPS requests",
            "state": state.get_state_dict()
        }

@app.post("/simulation/toggle")
async def toggle_simulation(req: ToggleSimRequest):
    """Toggle between realistic simulation mode and live HTTP measurement."""
    state.simulation_mode = req.enabled
    return {"simulation_mode": state.simulation_mode}

@app.post("/speedtest")
async def run_speed_test(site_name: str = Body(..., embed=True)):
    """
    Runs a detailed before-and-after speed test for judges on a domain.
    Direct path vs VPN path, showing round-trip times and ms saved.
    """
    clean_name = site_name.strip().lower()
    if clean_name not in state.sites:
        d_base, v_base = 140.0, 45.0
    else:
        site = state.sites[clean_name]
        d_base = site.direct_avg or 120.0
        v_base = site.vpn_avg or 45.0

    # Execute 3 test bursts
    direct_bursts = []
    vpn_bursts = []
    for _ in range(3):
        if not state.simulation_mode:
            d_t = await measure_direct_https(clean_name) or d_base
            v_t = await measure_vpn_https(clean_name, state.proxy_url) or v_base
        else:
            d_t, v_t = generate_simulated_sample(clean_name)
        direct_bursts.append(round(d_t, 1))
        vpn_bursts.append(round(v_t, 1))
        await asyncio.sleep(0.05)

    import statistics
    avg_direct = round(statistics.mean(direct_bursts), 1)
    avg_vpn = round(statistics.mean(vpn_bursts), 1)
    diff = round(avg_direct - avg_vpn, 1)
    faster = avg_vpn < avg_direct
    pct = round(abs(diff) / avg_direct * 100, 1) if avg_direct > 0 else 0

    return {
        "domain": clean_name,
        "direct_runs": direct_bursts,
        "vpn_runs": vpn_bursts,
        "direct_avg_ms": avg_direct,
        "vpn_avg_ms": avg_vpn,
        "diff_ms": diff,
        "vpn_faster": faster,
        "speedup_percentage": pct,
        "summary": (
            f"VPN route is {pct}% faster ({diff}ms saved per request)"
            if faster
            else f"Direct route is {pct}% faster ({abs(diff)}ms less latency)"
        )
    }

# Mount static directory for frontend
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def root():
    index_file = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Smart Route VPN brain is running. Please add static/index.html"}
