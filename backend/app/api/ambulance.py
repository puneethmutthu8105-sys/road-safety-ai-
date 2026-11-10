"""Ambulance coordination API routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.models.ambulance import Ambulance, DispatchRecord
from app.auth.router import get_current_user, require_role
from app.utils.data_simulator import generate_simulated_ambulances
from app.agents.ambulance_agent import coordinate_ambulance
from app.utils.data_simulator import generate_traffic_snapshot
from app.agents.traffic_agent import analyze_traffic

router = APIRouter(prefix="/ambulance", tags=["ambulance"])


class CoordinateRequest(BaseModel):
    emergency_lat: float
    emergency_lng: float
    emergency_severity: str = "MODERATE"
    emergency_id: str = ""


@router.get("/fleet")
async def get_fleet(_user=Depends(get_current_user)):
    """Get simulated ambulance fleet status."""
    fleet = generate_simulated_ambulances(20)
    available = [a for a in fleet if a["status"] == "AVAILABLE"]
    return {
        "fleet": fleet,
        "total": len(fleet),
        "available": len(available),
        "is_simulated": True,
        "disclaimer": "SIMULATED fleet — not real ambulances"
    }


@router.post("/coordinate")
async def coordinate(payload: CoordinateRequest, _user=Depends(get_current_user)):
    """Run Ambulance Coordination Agent for an emergency."""
    fleet = generate_simulated_ambulances(20)
    traffic_data = generate_traffic_snapshot()
    traffic_summary = await analyze_traffic(traffic_data[:5])

    result = await coordinate_ambulance(
        emergency={
            "id": payload.emergency_id,
            "latitude": payload.emergency_lat,
            "longitude": payload.emergency_lng,
            "severity": payload.emergency_severity,
        },
        ambulances=fleet,
        traffic_context=traffic_summary,
    )
    return result
