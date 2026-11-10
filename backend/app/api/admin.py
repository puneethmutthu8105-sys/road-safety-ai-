"""Admin dashboard API routes."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.database import get_db
from app.models.user import User
from app.models.accident import Accident
from app.models.emergency import EmergencyReport, Alert, AgentRun, HITLReview
from app.auth.router import require_role

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard")
async def admin_dashboard(db: AsyncSession = Depends(get_db),
                           _user=Depends(require_role("admin"))):
    """Full admin dashboard data."""
    user_count = await db.scalar(select(func.count(User.id)))
    accident_count = await db.scalar(select(func.count(Accident.id)))
    emergency_count = await db.scalar(select(func.count(EmergencyReport.id)))
    open_emergencies = await db.scalar(
        select(func.count(EmergencyReport.id)).where(EmergencyReport.status == "OPEN")
    )
    pending_hitl = await db.scalar(
        select(func.count(HITLReview.id)).where(HITLReview.decision == None)
    )
    agent_runs = await db.scalar(select(func.count(AgentRun.id)))
    total_cost = await db.scalar(select(func.sum(AgentRun.cost_usd))) or 0.0

    # Recent alerts
    alerts_result = await db.execute(
        select(Alert).order_by(desc(Alert.created_at)).limit(10)
    )
    alerts = alerts_result.scalars().all()

    return {
        "users": user_count or 0,
        "accidents": accident_count or 0,
        "emergencies": {"total": emergency_count or 0, "open": open_emergencies or 0},
        "hitl_pending": pending_hitl or 0,
        "agent_runs": agent_runs or 0,
        "total_ai_cost_usd": round(float(total_cost), 4),
        "recent_alerts": [
            {
                "id": str(a.id), "type": a.alert_type, "message": a.message,
                "risk_level": a.risk_level, "acknowledged": a.acknowledged,
                "created_at": a.created_at.isoformat(),
            }
            for a in alerts
        ],
    }


@router.get("/users")
async def list_users(db: AsyncSession = Depends(get_db),
                     _user=Depends(require_role("admin"))):
    result = await db.execute(select(User).order_by(desc(User.created_at)).limit(100))
    users = result.scalars().all()
    return {
        "users": [
            {"id": str(u.id), "name": u.name, "email": u.email,
             "role": u.role.value, "is_active": u.is_active,
             "created_at": u.created_at.isoformat()}
            for u in users
        ]
    }


@router.get("/agent-runs")
async def list_agent_runs(limit: int = 50, db: AsyncSession = Depends(get_db),
                           _user=Depends(require_role("admin"))):
    result = await db.execute(
        select(AgentRun).order_by(desc(AgentRun.created_at)).limit(limit)
    )
    runs = result.scalars().all()
    return {
        "runs": [
            {
                "id": str(r.id), "agent_name": r.agent_name, "success": r.success,
                "tokens_used": r.tokens_used, "cost_usd": r.cost_usd,
                "latency_ms": r.latency_ms, "created_at": r.created_at.isoformat(),
            }
            for r in runs
        ]
    }
