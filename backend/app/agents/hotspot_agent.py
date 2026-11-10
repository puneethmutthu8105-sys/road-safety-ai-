"""
Accident Hotspot Detection Agent
Identifies accident-prone locations using geospatial clustering.
"""
import logging
import uuid
import math
from datetime import datetime
from typing import Dict, Any, List, Tuple

from app.agents.llm_gateway import llm_generate
from app.agents.memory import AgentMemory
from app.observability.langfuse_client import TraceContext
from app.guardrails.input_validator import validate_input, sanitize_output

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Accident Hotspot Detection Agent for a road safety AI system.
Your role is to analyze historical accident data to identify accident-prone locations (hotspots).
For each hotspot provide:
1. Zone description and location context
2. Primary contributing factors
3. Severity classification (LOW/MEDIUM/HIGH/CRITICAL)
4. Recommended preventive measures (infrastructure, signage, enforcement)
5. Priority ranking for authority intervention

Be data-driven, location-specific, and actionable.
"""

memory = AgentMemory("hotspot_detection")


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in km between two GPS points."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _simple_cluster(accidents: List[Dict], radius_km: float = 0.5) -> List[Dict]:
    """
    Simple distance-based clustering (DBSCAN-like without sklearn dependency).
    Groups accidents within radius_km into clusters.
    """
    visited = set()
    clusters = []
    for i, acc in enumerate(accidents):
        if i in visited:
            continue
        cluster = [acc]
        visited.add(i)
        for j, other in enumerate(accidents):
            if j in visited:
                continue
            dist = _haversine_km(acc["latitude"], acc["longitude"], other["latitude"], other["longitude"])
            if dist <= radius_km:
                cluster.append(other)
                visited.add(j)
        if len(cluster) >= 2:
            clusters.append(cluster)
    return clusters


def _build_hotspots(clusters: List[List[Dict]]) -> List[Dict]:
    """Convert clusters to hotspot dicts."""
    hotspots = []
    severity_map = {"minor": 1, "moderate": 2, "severe": 3, "fatal": 4}
    for cluster in clusters:
        avg_lat = sum(a["latitude"] for a in cluster) / len(cluster)
        avg_lng = sum(a["longitude"] for a in cluster) / len(cluster)
        avg_sev = sum(severity_map.get(a.get("severity", "minor"), 1) for a in cluster) / len(cluster)
        hotspots.append({
            "latitude": round(avg_lat, 5),
            "longitude": round(avg_lng, 5),
            "accident_count": len(cluster),
            "avg_severity_score": round(avg_sev, 2),
            "radius_m": 500,
            "severity_label": "CRITICAL" if avg_sev >= 3.5 else "HIGH" if avg_sev >= 2.5 else "MEDIUM",
        })
    return sorted(hotspots, key=lambda x: (-x["accident_count"], -x["avg_severity_score"]))


async def detect_hotspots(accidents: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Detect accident hotspots from historical accident records.
    Returns hotspot list with heatmap-ready data.
    """
    run_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat()

    if len(accidents) < 2:
        return {
            "run_id": run_id, "agent": "hotspot_detection",
            "timestamp": timestamp, "hotspots": [], "heatmap_data": [],
            "analysis": "Insufficient accident data for hotspot detection.",
            "total_accidents_analyzed": len(accidents),
        }

    clusters = _simple_cluster(accidents, radius_km=0.5)
    hotspots = _build_hotspots(clusters)
    top_hotspots = hotspots[:10]

    # Heatmap data: [lat, lng, intensity]
    heatmap_data = [[h["latitude"], h["longitude"], min(h["accident_count"] / 10.0, 1.0)] for h in hotspots]

    past = memory.retrieve(f"hotspot accident cluster analysis {len(accidents)} accidents", n_results=2)
    past_text = "\n".join(past) if past else "No prior hotspot analysis."

    hotspot_lines = []
    for i, h in enumerate(top_hotspots, 1):
        hotspot_lines.append(
            f"  {i}. ({h['latitude']:.4f}, {h['longitude']:.4f}) — "
            f"{h['accident_count']} accidents, avg severity={h['avg_severity_score']:.2f}, level={h['severity_label']}"
        )

    prompt = f"""
Accident Hotspot Detection Analysis
Timestamp: {timestamp}
Total Accidents Analyzed: {len(accidents)}
Clusters Identified: {len(clusters)}
Top Hotspot Locations:
{chr(10).join(hotspot_lines)}

Historical Context:
{past_text}

For the top 3 highest-risk hotspots, provide detailed analysis including contributing factors,
risk classification, and specific prevention recommendations for traffic authorities.
"""

    is_valid, reason = validate_input(prompt)
    if not is_valid:
        return {"error": reason, "run_id": run_id}

    with TraceContext("hotspot_detection_agent", {"accidents": len(accidents), "clusters": len(clusters)}) as ctx:
        llm_resp = await llm_generate(prompt, SYSTEM_PROMPT, max_tokens=700, agent_name="hotspot_detection", run_id=run_id)
        latency = ctx.finish({"hotspots": len(top_hotspots)}, tokens=llm_resp.tokens_used,
                             cost=llm_resp.cost_usd, provider=llm_resp.provider)

    analysis = sanitize_output(llm_resp.content)

    memory.store(
        f"Hotspot analysis at {timestamp}: {len(accidents)} accidents, {len(clusters)} clusters, top hotspot at ({top_hotspots[0]['latitude'] if top_hotspots else 0:.3f},{top_hotspots[0]['longitude'] if top_hotspots else 0:.3f})",
        metadata={"timestamp": timestamp, "accident_count": len(accidents), "cluster_count": len(clusters)}
    )

    return {
        "run_id": run_id,
        "agent": "hotspot_detection",
        "timestamp": timestamp,
        "total_accidents_analyzed": len(accidents),
        "clusters_found": len(clusters),
        "hotspots": top_hotspots,
        "heatmap_data": heatmap_data,
        "analysis": analysis,
        "provider": llm_resp.provider,
        "tokens_used": llm_resp.tokens_used,
        "cost_usd": round(llm_resp.cost_usd, 6),
        "latency_ms": latency,
    }
