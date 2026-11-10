"""
MCP Emergency Tool Server
Provides tools for querying and managing emergency records.
"""
import json
from datetime import datetime
from fastmcp import FastMCP

mcp = FastMCP("Emergency Tool Server")

# In-memory store (backed by DB in production via API calls)
_emergency_cache: list = []


@mcp.tool()
def log_emergency(lat: float, lng: float, description: str, severity: str, injuries: int = 0) -> str:
    """Log a new emergency report."""
    record = {
        "id": f"EMG-{int(datetime.utcnow().timestamp())}",
        "latitude": lat,
        "longitude": lng,
        "description": description,
        "severity": severity,
        "injuries_count": injuries,
        "status": "OPEN",
        "created_at": datetime.utcnow().isoformat(),
    }
    _emergency_cache.append(record)
    return json.dumps({"success": True, "record": record})


@mcp.tool()
def get_open_emergencies() -> str:
    """Get all currently open emergency reports."""
    open_emg = [e for e in _emergency_cache if e.get("status") == "OPEN"]
    return json.dumps({"open_emergencies": open_emg, "count": len(open_emg)})


@mcp.tool()
def update_emergency_status(emergency_id: str, status: str) -> str:
    """Update the status of an emergency report."""
    for emg in _emergency_cache:
        if emg["id"] == emergency_id:
            emg["status"] = status
            emg["updated_at"] = datetime.utcnow().isoformat()
            return json.dumps({"success": True, "updated": emg})
    return json.dumps({"success": False, "error": f"Emergency {emergency_id} not found"})


@mcp.tool()
def get_emergency_stats() -> str:
    """Get emergency statistics summary."""
    total = len(_emergency_cache)
    by_status = {}
    by_severity = {}
    for e in _emergency_cache:
        s = e.get("status", "UNKNOWN")
        sv = e.get("severity", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
        by_severity[sv] = by_severity.get(sv, 0) + 1
    return json.dumps({"total": total, "by_status": by_status, "by_severity": by_severity})


if __name__ == "__main__":
    mcp.run(transport="stdio")
