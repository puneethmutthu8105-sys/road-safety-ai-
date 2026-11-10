"""
MCP Traffic Tool Server
Provides traffic data tools for agents via MCP protocol.
"""
import json
import random
from datetime import datetime
from fastmcp import FastMCP
from app.utils.data_simulator import generate_traffic_snapshot, ROAD_SEGMENTS

mcp = FastMCP("Traffic Tool Server")


@mcp.tool()
def get_current_traffic(segment_ids: list[str] = None) -> str:
    """
    Get current traffic data for road segments.
    Returns density, speed, and congestion level per segment.
    """
    snapshot = generate_traffic_snapshot()
    if segment_ids:
        snapshot = [s for s in snapshot if s["segment_id"] in segment_ids]
    return json.dumps({
        "timestamp": datetime.utcnow().isoformat(),
        "source": "simulated",
        "segments": snapshot,
        "note": "SIMULATED traffic data for demonstration purposes"
    })


@mcp.tool()
def get_traffic_summary(lat: float, lng: float, radius_km: float = 3.0) -> str:
    """
    Get a traffic summary for the area around a given location.
    """
    import math
    snapshot = generate_traffic_snapshot()
    R = 6371

    def dist(s):
        dlat = math.radians(s["latitude"] - lat)
        dlon = math.radians(s["longitude"] - lng)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat)) * math.cos(math.radians(s["latitude"])) * math.sin(dlon/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    nearby = [s for s in snapshot if dist(s) <= radius_km]
    if not nearby:
        return json.dumps({"message": "No traffic data in radius", "radius_km": radius_km})

    avg_density = sum(s["density"] for s in nearby) / len(nearby)
    avg_speed = sum(s["speed_kmh"] for s in nearby) / len(nearby)
    levels = [s["congestion_level"] for s in nearby]
    overall = "SEVERE" if "SEVERE" in levels else "HIGH" if "HIGH" in levels else "MEDIUM" if "MEDIUM" in levels else "LOW"

    return json.dumps({
        "center": {"lat": lat, "lng": lng},
        "radius_km": radius_km,
        "segments_found": len(nearby),
        "avg_density": round(avg_density, 1),
        "avg_speed_kmh": round(avg_speed, 1),
        "overall_congestion": overall,
        "source": "simulated"
    })


@mcp.tool()
def get_road_segments() -> str:
    """List all monitored road segments."""
    return json.dumps({"segments": ROAD_SEGMENTS, "count": len(ROAD_SEGMENTS)})


if __name__ == "__main__":
    mcp.run(transport="stdio")
