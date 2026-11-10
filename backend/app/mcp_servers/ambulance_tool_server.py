"""
MCP Ambulance Registry Tool Server
Provides tools for ambulance lookup and dispatch tracking.
"""
import json
import math
from datetime import datetime
from fastmcp import FastMCP
from app.utils.data_simulator import generate_simulated_ambulances

mcp = FastMCP("Ambulance Registry Tool Server")

# Simulated fleet (loaded once)
_fleet = generate_simulated_ambulances(20)


def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


@mcp.tool()
def get_available_ambulances() -> str:
    """
    Get all available ambulances in the simulated fleet.
    NOTE: This is a SIMULATED fleet for demonstration purposes.
    """
    available = [a for a in _fleet if a["status"] == "AVAILABLE"]
    return json.dumps({
        "available_count": len(available),
        "total_fleet": len(_fleet),
        "ambulances": available,
        "is_simulated": True,
        "disclaimer": "SIMULATED data - not real ambulances"
    })


@mcp.tool()
def get_nearest_ambulances(lat: float, lng: float, count: int = 3) -> str:
    """
    Find the nearest available ambulances to a given location.
    NOTE: This is a SIMULATED fleet for demonstration purposes.
    """
    available = [a for a in _fleet if a["status"] == "AVAILABLE"]
    for amb in available:
        amb["_distance_km"] = round(_haversine_km(lat, lng, amb["latitude"], amb["longitude"]), 2)
    available.sort(key=lambda x: x["_distance_km"])
    nearest = available[:count]
    return json.dumps({
        "location": {"lat": lat, "lng": lng},
        "nearest_ambulances": nearest,
        "is_simulated": True,
        "disclaimer": "SIMULATED data - contact official emergency services for real dispatch"
    })


@mcp.tool()
def update_ambulance_status(ambulance_id: str, new_status: str) -> str:
    """Update an ambulance's availability status."""
    for amb in _fleet:
        if amb["id"] == ambulance_id:
            amb["status"] = new_status
            amb["last_updated"] = datetime.utcnow().isoformat()
            return json.dumps({"success": True, "ambulance": amb})
    return json.dumps({"success": False, "error": f"Ambulance {ambulance_id} not found"})


@mcp.tool()
def get_fleet_status() -> str:
    """Get overall fleet status summary."""
    status_count = {}
    for amb in _fleet:
        s = amb["status"]
        status_count[s] = status_count.get(s, 0) + 1
    return json.dumps({
        "total": len(_fleet),
        "by_status": status_count,
        "is_simulated": True
    })


if __name__ == "__main__":
    mcp.run(transport="stdio")
