"""Reports and analytics API routes."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.database import get_db
from app.models.accident import Accident, AccidentSeverity
from app.models.emergency import EmergencyReport, AgentRun
from app.auth.router import get_current_user

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/summary")
async def get_summary(db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    """Get system-wide analytics summary."""
    total_accidents = await db.scalar(select(func.count(Accident.id)))
    total_emergencies = await db.scalar(select(func.count(EmergencyReport.id)))
    open_emergencies = await db.scalar(
        select(func.count(EmergencyReport.id)).where(EmergencyReport.status == "OPEN")
    )
    fatal_count = await db.scalar(
        select(func.count(Accident.id)).where(Accident.severity == AccidentSeverity.FATAL)
    )
    severe_count = await db.scalar(
        select(func.count(Accident.id)).where(Accident.severity == AccidentSeverity.SEVERE)
    )
    total_agent_runs = await db.scalar(select(func.count(AgentRun.id)))
    total_tokens = await db.scalar(select(func.sum(AgentRun.tokens_used))) or 0
    total_cost = await db.scalar(select(func.sum(AgentRun.cost_usd))) or 0.0

    return {
        "accidents": {
            "total": total_accidents or 0,
            "fatal": fatal_count or 0,
            "severe": severe_count or 0,
        },
        "emergencies": {
            "total": total_emergencies or 0,
            "open": open_emergencies or 0,
        },
        "ai_agents": {
            "total_runs": total_agent_runs or 0,
            "total_tokens": total_tokens,
            "total_cost_usd": round(float(total_cost), 4),
        }
    }


@router.get("/severity-distribution")
async def get_severity_distribution(db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    """Get accident severity distribution for charts."""
    result = await db.execute(
        select(Accident.severity, func.count(Accident.id)).group_by(Accident.severity)
    )
    rows = result.all()
    return {"distribution": [{"severity": r[0].value, "count": r[1]} for r in rows]}


@router.get("/agent-performance")
async def get_agent_performance(db: AsyncSession = Depends(get_db),
                                 _user=Depends(get_current_user)):
    """Get per-agent performance metrics."""
    result = await db.execute(
        select(
            AgentRun.agent_name,
            func.count(AgentRun.id).label("runs"),
            func.avg(AgentRun.latency_ms).label("avg_latency"),
            func.sum(AgentRun.tokens_used).label("total_tokens"),
            func.sum(AgentRun.cost_usd).label("total_cost"),
        ).group_by(AgentRun.agent_name)
    )
    rows = result.all()
    return {
        "agents": [
            {
                "name": r[0], "runs": r[1],
                "avg_latency_ms": round(float(r[2] or 0), 1),
                "total_tokens": r[3] or 0,
                "total_cost_usd": round(float(r[4] or 0), 5),
            }
            for r in rows
        ]
    }
