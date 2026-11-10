"""Accidents and risk prediction API routes."""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models.accident import Accident, RiskPrediction, AccidentHotspot, AccidentSeverity
from app.agents.risk_agent import predict_risk
from app.agents.orchestrator import orchestrator
from app.auth.router import get_current_user
from app.utils.data_simulator import generate_traffic_snapshot, generate_road_conditions
from app.mcp_servers.weather_tool_server import _fetch_live_weather
from app.config import settings
import json

router = APIRouter(prefix="/accidents", tags=["accidents"])


class AccidentCreate(BaseModel):
    latitude: float
    longitude: float
    severity: AccidentSeverity
    date_time: Optional[str] = None
    weather_condition: Optional[str] = None
    road_type: Optional[str] = None
    vehicle_count: int = 1
    casualties: int = 0
    description: Optional[str] = None


class RiskRequest(BaseModel):
    latitude: float
    longitude: float


@router.post("/report", status_code=201)
async def report_accident(payload: AccidentCreate, db: AsyncSession = Depends(get_db),
                          user=Depends(get_current_user)):
    """Report a confirmed accident."""
    accident = Accident(
        id=uuid.uuid4(),
        latitude=payload.latitude,
        longitude=payload.longitude,
        severity=payload.severity,
        date_time=datetime.fromisoformat(payload.date_time) if payload.date_time else datetime.utcnow(),
        weather_condition=payload.weather_condition,
        road_type=payload.road_type,
        vehicle_count=payload.vehicle_count,
        casualties=payload.casualties,
        description=payload.description,
        is_predicted=False,
        source="manual",
        created_by=user.id,
    )
    db.add(accident)
    await db.flush()
    return {"id": str(accident.id), "status": "reported", "severity": payload.severity}


@router.get("/history")
async def get_accident_history(limit: int = 100, offset: int = 0,
                                db: AsyncSession = Depends(get_db),
                                _user=Depends(get_current_user)):
    """Get historical accident records."""
    result = await db.execute(
        select(Accident).order_by(desc(Accident.date_time)).offset(offset).limit(limit)
    )
    accidents = result.scalars().all()
    return {
        "accidents": [
            {
                "id": str(a.id), "latitude": a.latitude, "longitude": a.longitude,
                "severity": a.severity.value, "date_time": a.date_time.isoformat(),
                "weather_condition": a.weather_condition, "road_type": a.road_type,
                "vehicle_count": a.vehicle_count, "casualties": a.casualties,
                "is_predicted": a.is_predicted, "source": a.source,
            }
            for a in accidents
        ],
        "total": len(accidents),
        "offset": offset,
        "limit": limit,
    }


@router.post("/predict-risk")
async def predict_accident_risk(payload: RiskRequest, _user=Depends(get_current_user)):
    """Run Accident Risk Prediction Agent for a given location."""
    traffic_data = generate_traffic_snapshot()
    road_data = generate_road_conditions(10)
    weather_data = _fetch_live_weather(payload.latitude, payload.longitude)

    # Build traffic summary
    from app.agents.traffic_agent import analyze_traffic
    traffic_summary = await analyze_traffic(traffic_data[:5])

    road_summary = {
        "avg_severity_score": sum(r.get("severity_score", 0) for r in road_data) / max(len(road_data), 1),
        "hazard_types": list(set(r.get("condition_type", "") for r in road_data)),
        "recent_issues": f"{len(road_data)} road condition reports in area",
    }

    result = await predict_risk(
        location={"lat": payload.latitude, "lng": payload.longitude},
        traffic_data=traffic_summary,
        weather_data=weather_data,
        road_data=road_summary,
    )
    return result


@router.get("/hotspots")
async def get_hotspots(db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    """Get computed accident hotspots."""
    result = await db.execute(
        select(AccidentHotspot).order_by(desc(AccidentHotspot.accident_count)).limit(50)
    )
    hotspots = result.scalars().all()
    return {
        "hotspots": [
            {
                "id": str(h.id), "latitude": h.latitude, "longitude": h.longitude,
                "radius_m": h.radius_m, "accident_count": h.accident_count,
                "avg_severity_score": h.avg_severity_score, "zone_label": h.zone_label,
                "last_computed_at": h.last_computed_at.isoformat(),
            }
            for h in hotspots
        ]
    }


@router.post("/detect-hotspots")
async def detect_accident_hotspots(db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    """Run Hotspot Detection Agent on all accident records."""
    result = await db.execute(select(Accident).order_by(desc(Accident.date_time)).limit(500))
    accidents = result.scalars().all()
    accident_dicts = [
        {"id": str(a.id), "latitude": a.latitude, "longitude": a.longitude,
         "severity": a.severity.value, "date_time": a.date_time.isoformat()}
        for a in accidents
    ]
    from app.agents.hotspot_agent import detect_hotspots
    hotspot_result = await detect_hotspots(accident_dicts)

    # Persist computed hotspots
    if hotspot_result.get("hotspots"):
        for h in hotspot_result["hotspots"][:20]:
            hotspot = AccidentHotspot(
                id=uuid.uuid4(),
                latitude=h["latitude"],
                longitude=h["longitude"],
                radius_m=h.get("radius_m", 500),
                accident_count=h["accident_count"],
                avg_severity_score=h["avg_severity_score"],
                zone_label=h.get("severity_label", ""),
                last_computed_at=datetime.utcnow(),
            )
            db.add(hotspot)
        await db.flush()

    return hotspot_result
