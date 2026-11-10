"""Traffic API routes."""
from fastapi import APIRouter, Depends
from app.agents.traffic_agent import analyze_traffic
from app.utils.data_simulator import generate_traffic_snapshot
from app.auth.router import get_current_user

router = APIRouter(prefix="/traffic", tags=["traffic"])


@router.get("/snapshot")
async def get_traffic_snapshot(_user=Depends(get_current_user)):
    """Get current simulated traffic snapshot for all segments."""
    data = generate_traffic_snapshot()
    return {"status": "ok", "segments": data, "count": len(data)}


@router.post("/analyze")
async def analyze_traffic_route(_user=Depends(get_current_user)):
    """Run Traffic Analysis Agent on current traffic data."""
    data = generate_traffic_snapshot()
    result = await analyze_traffic(data)
    return result
