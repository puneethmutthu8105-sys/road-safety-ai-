"""Celery background tasks for traffic and hotspot processing."""
import asyncio
import logging
from app.tasks.celery_app import celery_app
from app.utils.data_simulator import generate_traffic_snapshot, generate_historical_accidents

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.traffic_tasks.refresh_traffic_snapshot")
def refresh_traffic_snapshot():
    """Refresh traffic data snapshot (periodic task)."""
    try:
        snapshot = generate_traffic_snapshot()
        logger.info(f"[Task] Traffic snapshot refreshed: {len(snapshot)} segments")
        return {"status": "ok", "segments": len(snapshot)}
    except Exception as e:
        logger.error(f"[Task] Traffic refresh failed: {e}")
        return {"status": "error", "error": str(e)}


@celery_app.task(name="app.tasks.traffic_tasks.compute_hotspots")
def compute_hotspots():
    """Compute accident hotspots from historical data (periodic task)."""
    try:
        accidents = generate_historical_accidents(200)

        async def _run():
            from app.agents.hotspot_agent import detect_hotspots
            return await detect_hotspots(accidents)

        result = asyncio.run(_run())
        logger.info(f"[Task] Hotspots computed: {result.get('clusters_found', 0)} clusters")
        return {"status": "ok", "clusters": result.get("clusters_found", 0)}
    except Exception as e:
        logger.error(f"[Task] Hotspot compute failed: {e}")
        return {"status": "error", "error": str(e)}
