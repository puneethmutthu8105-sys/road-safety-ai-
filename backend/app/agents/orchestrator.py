"""
Master Orchestrator Agent
Coordinates all specialized agents to handle complex multi-step tasks.
"""
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List

from app.agents.traffic_agent import analyze_traffic
from app.agents.risk_agent import predict_risk
from app.agents.road_condition_agent import monitor_road_conditions
from app.agents.hotspot_agent import detect_hotspots
from app.agents.emergency_agent import generate_response
from app.agents.ambulance_agent import coordinate_ambulance
from app.agents.memory import AgentMemory
from app.observability.langfuse_client import TraceContext

logger = logging.getLogger(__name__)

memory = AgentMemory("orchestrator")


class OrchestratorAgent:
    """
    Master orchestrator that decomposes tasks and routes to specialized agents.
    Supports three main workflows:
    1. full_analysis — traffic + weather + road conditions → risk prediction
    2. emergency_response — emergency report → response + ambulance dispatch
    3. hotspot_update — historical accidents → hotspot detection
    """

    async def run_full_analysis(
        self,
        traffic_records: List[Dict],
        weather_data: Dict,
        road_conditions: List[Dict],
        location: Dict[str, float],
    ) -> Dict[str, Any]:
        """Run traffic + road condition analysis and risk prediction pipeline."""
        orchestrator_run_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        results = {}

        logger.info(f"[Orchestrator] Starting full analysis run {orchestrator_run_id}")

        # Step 1: Traffic Analysis
        try:
            traffic_result = await analyze_traffic(traffic_records)
            results["traffic_analysis"] = traffic_result
        except Exception as e:
            logger.error(f"[Orchestrator] Traffic agent failed: {e}")
            results["traffic_analysis"] = {"error": str(e)}
            traffic_result = {}

        # Step 2: Road Condition Monitoring
        try:
            road_result = await monitor_road_conditions(road_conditions, weather_data)
            results["road_condition"] = road_result
        except Exception as e:
            logger.error(f"[Orchestrator] Road condition agent failed: {e}")
            results["road_condition"] = {"error": str(e)}
            road_result = {}

        # Step 3: Risk Prediction (using outputs from steps 1 & 2)
        try:
            risk_result = await predict_risk(
                location=location,
                traffic_data=traffic_result,
                weather_data=weather_data,
                road_data={
                    "avg_severity_score": road_result.get("avg_severity_score", 0),
                    "hazard_types": road_result.get("hazard_types", []),
                    "recent_issues": road_result.get("report", "")[:200],
                }
            )
            results["risk_prediction"] = risk_result
        except Exception as e:
            logger.error(f"[Orchestrator] Risk agent failed: {e}")
            results["risk_prediction"] = {"error": str(e)}

        results["orchestrator_run_id"] = orchestrator_run_id
        results["timestamp"] = timestamp
        results["workflow"] = "full_analysis"

        # Store orchestration summary
        risk_level = results.get("risk_prediction", {}).get("risk_level", "UNKNOWN")
        memory.store(
            f"Full analysis at {timestamp}: location=({location.get('lat',0):.3f},{location.get('lng',0):.3f}), risk_level={risk_level}",
            metadata={"run_id": orchestrator_run_id, "risk_level": risk_level, "timestamp": timestamp}
        )

        return results

    async def run_emergency_pipeline(
        self,
        report: Dict[str, Any],
        ambulances: List[Dict],
        traffic_context: Optional[Dict] = None,
        weather_context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Run emergency response + ambulance coordination pipeline."""
        orchestrator_run_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        results = {}

        logger.info(f"[Orchestrator] Emergency pipeline {orchestrator_run_id}")

        # Step 1: Emergency Response
        try:
            emergency_result = await generate_response(report, traffic_context, weather_context)
            results["emergency_response"] = emergency_result
        except Exception as e:
            logger.error(f"[Orchestrator] Emergency agent failed: {e}")
            results["emergency_response"] = {"error": str(e)}
            emergency_result = {}

        # Step 2: Ambulance Coordination
        if ambulances:
            try:
                ambulance_result = await coordinate_ambulance(report, ambulances, traffic_context)
                results["ambulance_coordination"] = ambulance_result
            except Exception as e:
                logger.error(f"[Orchestrator] Ambulance agent failed: {e}")
                results["ambulance_coordination"] = {"error": str(e)}

        results["orchestrator_run_id"] = orchestrator_run_id
        results["timestamp"] = timestamp
        results["workflow"] = "emergency_pipeline"
        results["hitl_required"] = emergency_result.get("hitl_required", False)
        results["severity"] = emergency_result.get("severity", "UNKNOWN")

        return results

    async def run_hotspot_detection(self, accidents: List[Dict]) -> Dict[str, Any]:
        """Run hotspot detection pipeline."""
        orchestrator_run_id = str(uuid.uuid4())
        try:
            result = await detect_hotspots(accidents)
            result["orchestrator_run_id"] = orchestrator_run_id
            result["workflow"] = "hotspot_detection"
            return result
        except Exception as e:
            logger.error(f"[Orchestrator] Hotspot agent failed: {e}")
            return {"error": str(e), "orchestrator_run_id": orchestrator_run_id}


# Singleton
orchestrator = OrchestratorAgent()
