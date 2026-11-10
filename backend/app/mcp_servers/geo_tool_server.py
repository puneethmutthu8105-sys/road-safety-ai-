"""
MCP Geospatial Tool Server
Provides geospatial tools: nearest POIs, distance, bounding box queries.
"""
import json
import math
from fastmcp import FastMCP

mcp = FastMCP("Geospatial Tool Server")


def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


@mcp.tool()
def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> str:
    """Calculate straight-line distance between two GPS coordinates in km."""
    dist = _haversine_km(lat1, lng1, lat2, lng2)
    return json.dumps({"distance_km": round(dist, 3), "lat1": lat1, "lng1": lng1, "lat2": lat2, "lng2": lng2})


@mcp.tool()
def get_bounding_box(lat: float, lng: float, radius_km: float) -> str:
    """
    Calculate bounding box for a circular area given center and radius.
    Useful for spatial queries.
    """
    lat_delta = radius_km / 111.0
    lng_delta = radius_km / (111.0 * math.cos(math.radians(lat)))
    return json.dumps({
        "center": {"lat": lat, "lng": lng},
        "radius_km": radius_km,
        "bbox": {
            "min_lat": round(lat - lat_delta, 6),
            "max_lat": round(lat + lat_delta, 6),
            "min_lng": round(lng - lng_delta, 6),
            "max_lng": round(lng + lng_delta, 6),
        }
    })


@mcp.tool()
def find_nearest_points(target_lat: float, target_lng: float, points: list, max_results: int = 5) -> str:
    """
    Find the nearest points (list of {lat, lng, ...}) to a target location.
    Returns sorted list with distances.
    """
    distances = []
    for p in points:
        d = _haversine_km(target_lat, target_lng, p["lat"], p["lng"])
        distances.append({**p, "distance_km": round(d, 3)})
    distances.sort(key=lambda x: x["distance_km"])
    return json.dumps({"nearest": distances[:max_results], "total_searched": len(points)})


@mcp.tool()
def estimate_route_time(distance_km: float, congestion_level: str = "MEDIUM") -> str:
    """
    Estimate travel time for an emergency vehicle based on distance and traffic.
    """
    speed_map = {"LOW": 70, "MEDIUM": 55, "HIGH": 40, "SEVERE": 25}
    speed = speed_map.get(congestion_level.upper(), 55)
    eta_min = max(2, int((distance_km / speed) * 60))
    return json.dumps({
        "distance_km": distance_km,
        "congestion_level": congestion_level,
        "assumed_speed_kmh": speed,
        "eta_minutes": eta_min,
    })


if __name__ == "__main__":
    mcp.run(transport="stdio")
