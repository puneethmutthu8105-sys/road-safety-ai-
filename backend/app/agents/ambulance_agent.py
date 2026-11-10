"""
Ambulance Coordination Agent
Identifies available ambulances and recommends optimal dispatch.
"""
import logging
import uuid
import math
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.agents.llm_gateway import llm_generate
from app.agents.memory import AgentMemory
from app.observability.langfuse_client import TraceContext
from app.guardrails.input_validator import validate_input, sanitize_output

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Ambulance Coordination Agent for a road safety AI system.
Your role is to identify the most suitable ambulance(s) for dispatch to an emergency location.

Consider:
1. Distance from ambulance current location to emergency (prioritize proximity)
2. Current traffic conditions affecting route
3. Ambulance availability status
4. Hospital capacity and suitability for injury type
5. Estimated Time of Arrival (ETA)

Provide:
1. Primary ambulance recommendation (registration, hospital, ETA)
2. Backup ambulance recommendation
3. Recommended route (avoid congested segments)
4. Traffic advisories for emergency vehicle corridor
5. Hospital recommendation for patient transport

IMPORTANT: This is a SIMULATED ambulance fleet for demonstration. Clearly state this.
Real emergency dispatch must be coordinated through official emergency services.
"""

memory = AgentMemory("ambulance_coordination")


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _estimate_eta(distance_km: float, congestion: str) -> int:
    """Estimate ETA in minutes for emergency vehicle."""
    speed_map = {"LOW": 60, "MEDIUM": 45, "HIGH": 35, "SEVERE": 25}
    speed = speed_map.get(congestion, 50)
    return max(2, int((distance_km / speed) * 60))


def _rank_ambulances(ambulances: List[Dict], emergency_lat: float, emergency_lng: float, congestion: str) -> List[Dict]:
    """Sort available ambulances by distance."""
    available = [a for a in ambulances if a.get("status") == "AVAILABLE"]
    for amb in available:
        dist = _haversine_km(amb["latitude"], amb["longitude"], emergency_lat, emergency_lng)
        amb["_distance_km"] = round(dist, 2)
        amb["_eta_minutes"] = _estimate_eta(dist, congestion)
    return sorted(available, key=lambda x: x["_distance_km"])


async def coordinate_ambulance(
    emergency: Dict[str, Any],
    ambulances: List[Dict[str, Any]],
    traffic_context: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Find best ambulance(s) and generate dispatch recommendation.
    """
    run_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat()

    lat = emergency.get("latitude", 0)
    lng = emergency.get("longitude", 0)
    congestion = traffic_context.get("overall_congestion", "MEDIUM") if traffic_context else "MEDIUM"

    ranked = _rank_ambulances(ambulances, lat, lng, congestion)
    primary = ranked[0] if ranked else None
    backup = ranked[1] if len(ranked) > 1 else None

    # Past coordination memory
    past = memory.retrieve(f"ambulance dispatch emergency {congestion} congestion distance {primary['_distance_km'] if primary else 0:.1f} km", n_results=2)
    past_text = "\n".join(past) if past else "No prior coordination history."

    amb_lines = []
    for i, a in enumerate(ranked[:5], 1):
        amb_lines.append(
            f"  {i}. {a.get('registration_no','?')} — "
            f"distance={a['_distance_km']} km, ETA={a['_eta_minutes']} min, "
            f"hospital={a.get('hospital_name','?')}, simulated={a.get('is_simulated', True)}"
        )

    prompt = f"""
Ambulance Coordination Request
Emergency ID: {emergency.get('id', run_id)}
Timestamp: {timestamp}
Emergency Location: ({lat:.4f}, {lng:.4f})
Emergency Severity: {emergency.get('severity', 'MODERATE')}
Traffic Congestion: {congestion}

Available Ambulances (nearest first):
{chr(10).join(amb_lines) if amb_lines else '  No ambulances available.'}

Total Available Ambulances: {len(ranked)} of {len(ambulances)}

Historical Context:
{past_text}

[NOTE: This is a SIMULATED ambulance fleet. Real dispatch requires official emergency services.]

Provide ambulance dispatch recommendations with optimal routes and ETAs.
"""

    is_valid, reason = validate_input(prompt)
    if not is_valid:
        return {"error": reason, "run_id": run_id}

    with TraceContext("ambulance_coordination_agent", {"available": len(ranked), "lat": lat, "lng": lng}) as ctx:
        llm_resp = await llm_generate(prompt, SYSTEM_PROMPT, max_tokens=600, agent_name="ambulance_coordination", run_id=run_id)
        latency = ctx.finish({"primary_eta": primary["_eta_minutes"] if primary else None},
                             tokens=llm_resp.tokens_used, cost=llm_resp.cost_usd, provider=llm_resp.provider)

    recommendation = sanitize_output(llm_resp.content)

    if primary:
        memory.store(
            f"Ambulance dispatch: {primary.get('registration_no','?')} → emergency ({lat:.3f},{lng:.3f}), ETA={primary['_eta_minutes']}min, congestion={congestion}",
            metadata={"timestamp": timestamp, "lat": lat, "lng": lng, "eta": primary["_eta_minutes"]}
        )

    return {
        "run_id": run_id,
        "agent": "ambulance_coordination",
        "timestamp": timestamp,
        "emergency_id": str(emergency.get("id", "")),
        "location": {"lat": lat, "lng": lng},
        "available_ambulances": len(ranked),
        "total_ambulances": len(ambulances),
        "primary_ambulance": {
            "id": str(primary.get("id", "")),
            "registration_no": primary.get("registration_no"),
            "distance_km": primary["_distance_km"],
            "eta_minutes": primary["_eta_minutes"],
            "hospital": primary.get("hospital_name"),
            "is_simulated": primary.get("is_simulated", True),
        } if primary else None,
        "backup_ambulance": {
            "id": str(backup.get("id", "")),
            "registration_no": backup.get("registration_no"),
            "distance_km": backup["_distance_km"],
            "eta_minutes": backup["_eta_minutes"],
            "hospital": backup.get("hospital_name"),
            "is_simulated": backup.get("is_simulated", True),
        } if backup else None,
        "is_simulated_fleet": True,
        "recommendation": recommendation,
        "provider": llm_resp.provider,
        "tokens_used": llm_resp.tokens_used,
        "cost_usd": round(llm_resp.cost_usd, 6),
        "latency_ms": latency,
    }
