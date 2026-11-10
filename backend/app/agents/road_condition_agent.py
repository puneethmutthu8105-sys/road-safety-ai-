"""
Road Condition Monitoring Agent
Analyzes road conditions: potholes, visibility, weather, and accident factors.
"""
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List

from app.agents.llm_gateway import llm_generate
from app.agents.memory import AgentMemory
from app.observability.langfuse_client import TraceContext
from app.guardrails.input_validator import validate_input, sanitize_output

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Road Condition Monitoring Agent for a road safety AI system.
Analyze the provided road condition data including:
- Physical road hazards (potholes, debris, construction zones)
- Weather-related road conditions (wet surface, ice, fog, reduced visibility)
- Infrastructure condition ratings

Produce a structured report with:
1. Overall road safety rating (0-10, where 10 = safest)
2. Critical hazards requiring immediate attention
3. Weather-related risk assessment
4. Recommended speed limits for current conditions
5. Advisories for drivers and emergency vehicles
"""

memory = AgentMemory("road_condition")


async def monitor_road_conditions(conditions: List[Dict[str, Any]], weather: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze a list of road condition records plus current weather.
    Returns comprehensive road condition report.
    """
    run_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat()

    if not conditions:
        conditions = []

    # Aggregate
    critical_hazards = [c for c in conditions if c.get("severity_score", 0) >= 7]
    avg_severity = (sum(c.get("severity_score", 0) for c in conditions) / len(conditions)) if conditions else 0
    hazard_types = list(set(c.get("condition_type", "") for c in conditions))
    safety_rating = max(0, 10 - avg_severity)

    # Past context
    query = f"road condition hazard {hazard_types} weather {weather.get('condition','clear')}"
    past = memory.retrieve(query, n_results=3)
    past_text = "\n".join(past) if past else "No prior road condition data."

    condition_lines = []
    for c in conditions[:15]:  # limit to 15
        condition_lines.append(
            f"  - {c.get('condition_type','unknown')} at ({c.get('latitude',0):.4f},{c.get('longitude',0):.4f}): "
            f"severity={c.get('severity_score',0):.1f}/10, verified={c.get('verified', False)}"
        )

    prompt = f"""
Road Condition Monitoring Report
Timestamp: {timestamp}

Road Hazards Detected: {len(conditions)} records
{chr(10).join(condition_lines) if condition_lines else '  No active hazards.'}

Hazard Types Present: {hazard_types}
Critical Hazards (severity ≥ 7): {len(critical_hazards)}
Average Severity Score: {avg_severity:.2f}/10
Current Safety Rating: {safety_rating:.1f}/10

Current Weather:
- Condition: {weather.get('condition', 'Unknown')}
- Temperature: {weather.get('temperature_c', 'N/A')}°C
- Precipitation: {weather.get('precipitation_mm', 0)} mm/h
- Wind Speed: {weather.get('wind_speed_kmh', 0)} km/h
- Visibility: {weather.get('visibility_m', 10000)} m
- Humidity: {weather.get('humidity_pct', 'N/A')}%

Historical Context:
{past_text}

Provide a comprehensive road condition assessment, safety rating, and driver advisories.
"""

    is_valid, reason = validate_input(prompt)
    if not is_valid:
        return {"error": reason, "run_id": run_id}

    with TraceContext("road_condition_agent", {"conditions_count": len(conditions)}) as ctx:
        llm_resp = await llm_generate(prompt, SYSTEM_PROMPT, max_tokens=600, agent_name="road_condition", run_id=run_id)
        latency = ctx.finish({"safety_rating": safety_rating}, tokens=llm_resp.tokens_used,
                             cost=llm_resp.cost_usd, provider=llm_resp.provider)

    report = sanitize_output(llm_resp.content)

    memory.store(
        f"Road conditions at {timestamp}: safety_rating={safety_rating:.1f}, hazards={len(conditions)}, critical={len(critical_hazards)}, weather={weather.get('condition','')}",
        metadata={"timestamp": timestamp, "safety_rating": safety_rating, "critical_count": len(critical_hazards)}
    )

    return {
        "run_id": run_id,
        "agent": "road_condition",
        "timestamp": timestamp,
        "conditions_analyzed": len(conditions),
        "critical_hazards_count": len(critical_hazards),
        "hazard_types": hazard_types,
        "avg_severity_score": round(avg_severity, 2),
        "safety_rating": round(safety_rating, 2),
        "weather_condition": weather.get("condition", "unknown"),
        "report": report,
        "provider": llm_resp.provider,
        "tokens_used": llm_resp.tokens_used,
        "cost_usd": round(llm_resp.cost_usd, 6),
        "latency_ms": latency,
    }
