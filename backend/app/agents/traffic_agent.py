"""
Traffic Data Analysis Agent
Analyzes traffic density, vehicle movement, speed, and congestion patterns.
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

SYSTEM_PROMPT = """You are the Traffic Data Analysis Agent for a road safety AI system.
Your role is to analyze traffic density, vehicle movement patterns, speed data, and congestion levels.
Provide structured, data-driven analysis. Always include:
1. Overall traffic condition assessment
2. Congested segments (if any)
3. Average speed and density summary
4. Risk factors related to traffic
5. Recommendations for traffic management
Be concise, precise, and use numerical data where available.
"""

memory = AgentMemory("traffic_analysis")


async def analyze_traffic(traffic_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze a list of traffic records and return an AI-generated analysis.
    traffic_data: list of dicts with keys: segment_id, density, speed_kmh, congestion_level, latitude, longitude
    """
    run_id = str(uuid.uuid4())
    if not traffic_data:
        return {"error": "No traffic data provided", "run_id": run_id}

    # Build prompt from data
    summary_lines = []
    high_congestion = []
    total_density = 0
    total_speed = 0
    for rec in traffic_data:
        total_density += rec.get("density", 0)
        total_speed += rec.get("speed_kmh", 0)
        line = (f"Segment {rec.get('segment_id','?')}: "
                f"density={rec.get('density',0):.1f} veh/km, "
                f"speed={rec.get('speed_kmh',0):.1f} km/h, "
                f"congestion={rec.get('congestion_level','?')}, "
                f"location=({rec.get('latitude',0):.4f},{rec.get('longitude',0):.4f})")
        summary_lines.append(line)
        if rec.get("congestion_level") in ("HIGH", "SEVERE"):
            high_congestion.append(rec.get("segment_id", "unknown"))

    avg_density = total_density / len(traffic_data)
    avg_speed = total_speed / len(traffic_data)
    timestamp = datetime.utcnow().isoformat()

    # Retrieve relevant memory
    past_context = memory.retrieve(f"traffic analysis congestion density {avg_density:.0f}", n_results=3)
    past_summary = "\n".join(past_context) if past_context else "No prior context."

    prompt = f"""
Current Traffic Data ({timestamp}):
{chr(10).join(summary_lines)}

Summary: {len(traffic_data)} segments analyzed.
Average density: {avg_density:.1f} veh/km
Average speed: {avg_speed:.1f} km/h
High congestion segments: {high_congestion if high_congestion else 'None'}

Past context from memory:
{past_summary}

Provide a comprehensive traffic analysis report including risk assessment, congestion hotspots, and recommendations.
"""

    is_valid, reason = validate_input(prompt)
    if not is_valid:
        return {"error": f"Input validation failed: {reason}", "run_id": run_id}

    with TraceContext("traffic_analysis_agent", {"segments": len(traffic_data)}) as ctx:
        llm_resp = await llm_generate(prompt, SYSTEM_PROMPT, max_tokens=600, agent_name="traffic_analysis", run_id=run_id)
        latency = ctx.finish(
            {"analysis": llm_resp.content[:200]},
            tokens=llm_resp.tokens_used,
            cost=llm_resp.cost_usd,
            provider=llm_resp.provider
        )

    analysis_text = sanitize_output(llm_resp.content)

    # Store in memory
    memory.store(
        f"Traffic analysis at {timestamp}: avg_density={avg_density:.1f}, avg_speed={avg_speed:.1f}, congestion_segments={len(high_congestion)}",
        metadata={"timestamp": timestamp, "avg_density": avg_density, "avg_speed": avg_speed}
    )

    # Compute overall congestion level
    congestion_levels = [r.get("congestion_level", "LOW") for r in traffic_data]
    if "SEVERE" in congestion_levels:
        overall = "SEVERE"
    elif congestion_levels.count("HIGH") > len(traffic_data) * 0.3:
        overall = "HIGH"
    elif congestion_levels.count("MEDIUM") > len(traffic_data) * 0.4:
        overall = "MEDIUM"
    else:
        overall = "LOW"

    return {
        "run_id": run_id,
        "agent": "traffic_analysis",
        "timestamp": timestamp,
        "segments_analyzed": len(traffic_data),
        "avg_density": round(avg_density, 2),
        "avg_speed_kmh": round(avg_speed, 2),
        "overall_congestion": overall,
        "high_congestion_segments": high_congestion,
        "analysis": analysis_text,
        "provider": llm_resp.provider,
        "tokens_used": llm_resp.tokens_used,
        "cost_usd": round(llm_resp.cost_usd, 6),
        "latency_ms": latency,
    }
