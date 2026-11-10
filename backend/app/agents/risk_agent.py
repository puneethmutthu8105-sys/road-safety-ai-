"""
Accident Risk Prediction Agent
Predicts accident risk using historical data, weather, traffic, and road conditions.
"""
import logging
import uuid
import math
from datetime import datetime
from typing import Dict, Any, Optional

from app.agents.llm_gateway import llm_generate
from app.agents.memory import AgentMemory
from app.observability.langfuse_client import TraceContext
from app.guardrails.input_validator import validate_input, sanitize_output

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Accident Risk Prediction Agent for a road safety AI system.
Your role is to assess the probability and severity of road accidents based on:
- Current traffic conditions (density, speed, congestion)
- Weather conditions (rain, fog, wind, visibility)
- Road conditions (potholes, wet surface, construction)
- Time of day and historical accident patterns

Output a structured risk assessment with:
1. Risk Score (0-100, where 100 = highest risk)
2. Risk Level: LOW (0-25) / MEDIUM (26-50) / HIGH (51-75) / CRITICAL (76-100)
3. Primary risk factors (ranked)
4. Specific recommendations to reduce risk
5. Confidence level of prediction (0-1)

Be factual, precise, and safety-focused. Distinguish PREDICTED risks from CONFIRMED accidents clearly.
"""

memory = AgentMemory("risk_prediction")


def _compute_base_risk_score(traffic_data: Dict, weather_data: Dict, road_data: Dict) -> float:
    """Heuristic base risk score before LLM enhancement."""
    score = 0.0

    # Traffic factors
    congestion = traffic_data.get("overall_congestion", "LOW")
    avg_speed = traffic_data.get("avg_speed_kmh", 40)
    traffic_weight = {"LOW": 5, "MEDIUM": 15, "HIGH": 30, "SEVERE": 45}
    score += traffic_weight.get(congestion, 5)

    # Speed deviation from safe limit (40 km/h urban default)
    if avg_speed > 60:
        score += 10
    elif avg_speed > 80:
        score += 20

    # Weather factors
    condition = weather_data.get("condition", "clear").lower()
    visibility = weather_data.get("visibility_m", 10000)
    precipitation = weather_data.get("precipitation_mm", 0)

    weather_weight = {
        "clear": 0, "clouds": 2, "mist": 8, "fog": 20,
        "drizzle": 10, "rain": 15, "heavy rain": 25, "thunderstorm": 30, "snow": 25
    }
    for key, weight in weather_weight.items():
        if key in condition:
            score += weight
            break

    if visibility < 1000:
        score += 15
    elif visibility < 3000:
        score += 8

    if precipitation > 20:
        score += 10

    # Road condition factors
    road_severity = road_data.get("avg_severity_score", 0)
    score += min(road_severity * 2, 20)

    # Time of day risk (hour 0-23)
    hour = datetime.utcnow().hour
    if 22 <= hour or hour <= 5:
        score += 10  # night driving
    elif 7 <= hour <= 9 or 17 <= hour <= 20:
        score += 5   # rush hour

    return min(score, 100.0)


def _risk_level_from_score(score: float) -> str:
    if score >= 76:
        return "CRITICAL"
    elif score >= 51:
        return "HIGH"
    elif score >= 26:
        return "MEDIUM"
    return "LOW"


async def predict_risk(
    location: Dict[str, float],
    traffic_data: Dict[str, Any],
    weather_data: Dict[str, Any],
    road_data: Dict[str, Any],
    historical_context: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Predict accident risk for a given location.
    Returns risk score, level, factors, and recommendations.
    """
    run_id = str(uuid.uuid4())
    lat = location.get("lat", 0)
    lng = location.get("lng", 0)
    timestamp = datetime.utcnow().isoformat()

    base_score = _compute_base_risk_score(traffic_data, weather_data, road_data)

    # Retrieve similar historical scenarios from memory
    query = f"accident risk lat {lat:.3f} lng {lng:.3f} weather {weather_data.get('condition','clear')} traffic {traffic_data.get('overall_congestion','LOW')}"
    past_scenarios = memory.retrieve(query, n_results=3)
    past_context = "\n".join(past_scenarios) if past_scenarios else "No similar past scenarios."

    prompt = f"""
Location: ({lat:.4f}, {lng:.4f})
Timestamp: {timestamp}
Base Risk Score (Heuristic): {base_score:.1f}/100

Traffic Conditions:
- Overall Congestion: {traffic_data.get('overall_congestion', 'UNKNOWN')}
- Average Speed: {traffic_data.get('avg_speed_kmh', 'N/A')} km/h
- Average Density: {traffic_data.get('avg_density', 'N/A')} veh/km
- High Congestion Segments: {traffic_data.get('high_congestion_segments', [])}

Weather Conditions:
- Condition: {weather_data.get('condition', 'Unknown')}
- Temperature: {weather_data.get('temperature_c', 'N/A')}°C
- Visibility: {weather_data.get('visibility_m', 'N/A')} m
- Precipitation: {weather_data.get('precipitation_mm', 0)} mm
- Wind Speed: {weather_data.get('wind_speed_kmh', 'N/A')} km/h

Road Conditions:
- Hazard Types: {road_data.get('hazard_types', [])}
- Average Severity Score: {road_data.get('avg_severity_score', 0)}/10
- Recent Issues: {road_data.get('recent_issues', 'None')}

Historical Context:
{historical_context or past_context}

Based on all factors, provide your structured accident risk prediction.
Include: risk_score (0-100), risk_level, top_5_factors, recommendations (3-5 items), confidence (0-1).
"""

    is_valid, reason = validate_input(prompt)
    if not is_valid:
        return {"error": reason, "run_id": run_id}

    with TraceContext("risk_prediction_agent", {"lat": lat, "lng": lng, "base_score": base_score}) as ctx:
        llm_resp = await llm_generate(prompt, SYSTEM_PROMPT, max_tokens=700, agent_name="risk_prediction", run_id=run_id)
        latency = ctx.finish(
            {"risk_score": base_score},
            tokens=llm_resp.tokens_used,
            cost=llm_resp.cost_usd,
            provider=llm_resp.provider
        )

    analysis = sanitize_output(llm_resp.content)
    risk_level = _risk_level_from_score(base_score)

    # Store scenario in memory
    memory.store(
        f"Risk prediction at ({lat:.3f},{lng:.3f}): score={base_score:.1f}, level={risk_level}, weather={weather_data.get('condition','')}, congestion={traffic_data.get('overall_congestion','')}",
        metadata={"lat": lat, "lng": lng, "risk_score": base_score, "risk_level": risk_level, "timestamp": timestamp}
    )

    return {
        "run_id": run_id,
        "agent": "risk_prediction",
        "timestamp": timestamp,
        "location": {"lat": lat, "lng": lng},
        "risk_score": round(base_score, 2),
        "risk_level": risk_level,
        "is_predicted": True,  # always mark as predicted, not confirmed
        "analysis": analysis,
        "factors": {
            "traffic": traffic_data.get("overall_congestion", "LOW"),
            "weather": weather_data.get("condition", "clear"),
            "road_hazards": road_data.get("avg_severity_score", 0),
        },
        "provider": llm_resp.provider,
        "tokens_used": llm_resp.tokens_used,
        "cost_usd": round(llm_resp.cost_usd, 6),
        "latency_ms": latency,
    }
