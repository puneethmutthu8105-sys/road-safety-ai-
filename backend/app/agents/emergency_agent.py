"""
Emergency Response Agent
Analyzes accident reports and recommends suitable emergency response actions.
"""
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from app.agents.llm_gateway import llm_generate
from app.agents.memory import AgentMemory
from app.observability.langfuse_client import TraceContext
from app.guardrails.input_validator import validate_input, sanitize_output
from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Emergency Response Agent for a road safety AI system.
You analyze accident emergency reports and generate coordinated response recommendations.

For each emergency, provide:
1. Severity assessment (MINOR/MODERATE/SEVERE/CRITICAL)
2. Immediate response actions (ordered by priority)
3. Required emergency resources (ambulances, fire, police)
4. Estimated response time requirements
5. Traffic management recommendations around the accident site
6. Communication advisories for other road users
7. Whether human authority review is recommended

IMPORTANT: Your recommendations support emergency coordinators — final dispatch decisions
require Human-in-the-Loop approval for CRITICAL events. Always distinguish AI recommendations
from confirmed emergency actions.
"""

memory = AgentMemory("emergency_response")


def _assess_severity(report: Dict) -> str:
    injuries = report.get("injuries_count", 0)
    vehicles = report.get("vehicles_involved", 0)
    reported_severity = report.get("severity", "moderate").lower()

    if reported_severity == "fatal" or injuries >= 5:
        return "CRITICAL"
    elif reported_severity == "severe" or injuries >= 2 or vehicles >= 3:
        return "SEVERE"
    elif reported_severity == "moderate" or injuries >= 1 or vehicles >= 2:
        return "MODERATE"
    return "MINOR"


def _requires_hitl(severity: str, confidence: float) -> bool:
    """Critical events or low-confidence AI responses require human review."""
    if severity == "CRITICAL":
        return True
    if confidence < settings.HITL_CONFIDENCE_THRESHOLD:
        return True
    return False


async def generate_response(
    report: Dict[str, Any],
    traffic_context: Optional[Dict] = None,
    weather_context: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Generate emergency response recommendations for an accident report.
    """
    run_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat()

    lat = report.get("latitude", 0)
    lng = report.get("longitude", 0)
    severity = _assess_severity(report)

    # Retrieve similar past emergencies
    query = f"emergency response severity {severity} injuries {report.get('injuries_count',0)} accident"
    past = memory.retrieve(query, n_results=3)
    past_text = "\n".join(past) if past else "No similar past emergencies."

    prompt = f"""
Emergency Accident Report
Report ID: {report.get('id', run_id)}
Timestamp: {timestamp}
Location: ({lat:.4f}, {lng:.4f})
AI Severity Assessment: {severity}

Report Details:
- Description: {report.get('description', 'No description provided')}
- Reported Severity: {report.get('severity', 'Unknown')}
- Injuries Count: {report.get('injuries_count', 0)}
- Vehicles Involved: {report.get('vehicles_involved', 0)}

Traffic Context:
- Congestion Level: {traffic_context.get('overall_congestion', 'Unknown') if traffic_context else 'Not available'}
- Nearby Congested Segments: {traffic_context.get('high_congestion_segments', []) if traffic_context else []}

Weather Context:
- Condition: {weather_context.get('condition', 'Unknown') if weather_context else 'Not available'}
- Visibility: {weather_context.get('visibility_m', 'N/A') if weather_context else 'N/A'} m

Similar Past Emergencies:
{past_text}

Generate comprehensive emergency response recommendations. Include confidence score (0-1).
"""

    is_valid, reason = validate_input(prompt)
    if not is_valid:
        return {"error": reason, "run_id": run_id}

    with TraceContext("emergency_response_agent", {"severity": severity, "lat": lat, "lng": lng}) as ctx:
        llm_resp = await llm_generate(prompt, SYSTEM_PROMPT, max_tokens=800, agent_name="emergency_response", run_id=run_id)
        latency = ctx.finish({"severity": severity}, tokens=llm_resp.tokens_used,
                             cost=llm_resp.cost_usd, provider=llm_resp.provider)

    recommendation = sanitize_output(llm_resp.content)

    # Estimate confidence from response length and content richness
    confidence = min(0.95, max(0.5, len(recommendation) / 1000))
    hitl_required = _requires_hitl(severity, confidence)

    memory.store(
        f"Emergency response at ({lat:.3f},{lng:.3f}): severity={severity}, injuries={report.get('injuries_count',0)}, hitl={hitl_required}",
        metadata={"severity": severity, "lat": lat, "lng": lng, "timestamp": timestamp, "hitl": hitl_required}
    )

    # Determine resource requirements
    resources_needed = []
    if severity in ("MODERATE", "SEVERE", "CRITICAL"):
        resources_needed.append("ambulance")
    if severity in ("SEVERE", "CRITICAL"):
        resources_needed.extend(["police", "fire_brigade"])
    if severity == "CRITICAL":
        resources_needed.append("trauma_team")

    return {
        "run_id": run_id,
        "agent": "emergency_response",
        "timestamp": timestamp,
        "report_id": str(report.get("id", "")),
        "location": {"lat": lat, "lng": lng},
        "severity": severity,
        "resources_needed": resources_needed,
        "hitl_required": hitl_required,
        "confidence": round(confidence, 3),
        "recommendation": recommendation,
        "provider": llm_resp.provider,
        "tokens_used": llm_resp.tokens_used,
        "cost_usd": round(llm_resp.cost_usd, 6),
        "latency_ms": latency,
    }
