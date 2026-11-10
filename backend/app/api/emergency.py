"""Emergency response API routes."""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models.emergency import EmergencyReport, Alert, HITLReview
from app.models.ambulance import Ambulance, DispatchRecord
from app.agents.orchestrator import orchestrator
from app.auth.router import get_current_user, require_role
from app.utils.data_simulator import generate_traffic_snapshot, generate_simulated_ambulances
from app.mcp_servers.weather_tool_server import _fetch_live_weather

router = APIRouter(prefix="/emergency", tags=["emergency"])


class EmergencyCreate(BaseModel):
    latitude: float
    longitude: float
    description: str
    severity: str = "moderate"
    injuries_count: int = 0
    vehicles_involved: int = 1


class HITLDecision(BaseModel):
    decision: str  # APPROVED, REJECTED, MODIFIED
    notes: Optional[str] = None


@router.post("/report", status_code=201)
async def create_emergency_report(
    payload: EmergencyCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Submit an emergency accident report and trigger AI response pipeline."""
    report_id = uuid.uuid4()
    report = EmergencyReport(
        id=report_id,
        reporter_id=user.id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        description=payload.description,
        severity=payload.severity,
        injuries_count=payload.injuries_count,
        vehicles_involved=payload.vehicles_involved,
        status="OPEN",
    )
    db.add(report)
    await db.flush()

    # Get context
    traffic_data = generate_traffic_snapshot()
    weather_data = _fetch_live_weather(payload.latitude, payload.longitude)
    ambulances = generate_simulated_ambulances(20)

    # Build traffic summary for agents
    from app.agents.traffic_agent import analyze_traffic
    traffic_summary = await analyze_traffic(traffic_data[:5])

    # Run emergency pipeline
    pipeline_result = await orchestrator.run_emergency_pipeline(
        report={
            "id": str(report_id),
            "latitude": payload.latitude,
            "longitude": payload.longitude,
            "description": payload.description,
            "severity": payload.severity,
            "injuries_count": payload.injuries_count,
            "vehicles_involved": payload.vehicles_involved,
        },
        ambulances=ambulances,
        traffic_context=traffic_summary,
        weather_context=weather_data,
    )

    # Update report with AI recommendation
    er_resp = pipeline_result.get("emergency_response", {})
    report.ai_recommendation = er_resp
    report.hitl_required = er_resp.get("hitl_required", False)

    # Create HITL review if needed
    if er_resp.get("hitl_required"):
        hitl = HITLReview(
            id=uuid.uuid4(),
            review_type="DISPATCH",
            context_data=pipeline_result,
        )
        db.add(hitl)

    await db.flush()

    return {
        "report_id": str(report_id),
        "status": "OPEN",
        "pipeline_result": pipeline_result,
    }


@router.get("/reports")
async def list_emergency_reports(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """List emergency reports, optionally filtered by status."""
    query = select(EmergencyReport).order_by(desc(EmergencyReport.created_at)).limit(50)
    if status:
        query = query.where(EmergencyReport.status == status.upper())
    result = await db.execute(query)
    reports = result.scalars().all()
    return {
        "reports": [
            {
                "id": str(r.id), "latitude": r.latitude, "longitude": r.longitude,
                "description": r.description, "severity": r.severity,
                "injuries_count": r.injuries_count, "status": r.status,
                "hitl_required": r.hitl_required, "hitl_reviewed": r.hitl_reviewed,
                "created_at": r.created_at.isoformat(),
            }
            for r in reports
        ]
    }


@router.get("/reports/{report_id}")
async def get_emergency_report(report_id: str, db: AsyncSession = Depends(get_db),
                                _user=Depends(get_current_user)):
    result = await db.execute(select(EmergencyReport).where(EmergencyReport.id == report_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "Report not found")
    return {
        "id": str(r.id), "latitude": r.latitude, "longitude": r.longitude,
        "description": r.description, "severity": r.severity,
        "injuries_count": r.injuries_count, "vehicles_involved": r.vehicles_involved,
        "status": r.status, "ai_recommendation": r.ai_recommendation,
        "hitl_required": r.hitl_required, "hitl_reviewed": r.hitl_reviewed,
        "created_at": r.created_at.isoformat(),
    }


@router.patch("/reports/{report_id}/status")
async def update_report_status(report_id: str, status: str,
                                db: AsyncSession = Depends(get_db),
                                _user=Depends(require_role("admin", "officer"))):
    result = await db.execute(select(EmergencyReport).where(EmergencyReport.id == report_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "Report not found")
    r.status = status.upper()
    await db.flush()
    return {"id": report_id, "status": r.status}


@router.get("/hitl-queue")
async def get_hitl_queue(db: AsyncSession = Depends(get_db),
                          _user=Depends(require_role("admin", "officer"))):
    """Get pending Human-in-the-Loop review items."""
    result = await db.execute(
        select(HITLReview).where(HITLReview.decision == None).order_by(HITLReview.created_at)
    )
    items = result.scalars().all()
    return {
        "pending_reviews": [
            {
                "id": str(i.id), "review_type": i.review_type,
                "context_data": i.context_data, "created_at": i.created_at.isoformat(),
            }
            for i in items
        ]
    }


@router.post("/hitl-queue/{review_id}/decide")
async def submit_hitl_decision(
    review_id: str,
    payload: HITLDecision,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("admin", "officer")),
):
    """Submit a HITL decision (approve/reject/modify)."""
    result = await db.execute(select(HITLReview).where(HITLReview.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(404, "Review not found")
    review.decision = payload.decision.upper()
    review.notes = payload.notes
    review.reviewer_id = user.id
    review.reviewed_at = datetime.utcnow()
    await db.flush()
    return {"id": review_id, "decision": review.decision, "status": "recorded"}


@router.get("/alerts")
async def get_alerts(db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    """Get recent risk alerts."""
    result = await db.execute(
        select(Alert).order_by(desc(Alert.created_at)).limit(30)
    )
    alerts = result.scalars().all()
    return {
        "alerts": [
            {
                "id": str(a.id), "alert_type": a.alert_type, "message": a.message,
                "latitude": a.latitude, "longitude": a.longitude,
                "risk_level": a.risk_level, "acknowledged": a.acknowledged,
                "created_at": a.created_at.isoformat(),
            }
            for a in alerts
        ]
    }
