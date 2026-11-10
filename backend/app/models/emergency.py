import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


class EmergencyReport(Base):
    __tablename__ = "emergency_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reporter_id = Column(UUID(as_uuid=True), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String(20), default="moderate")
    injuries_count = Column(Integer, default=0)
    vehicles_involved = Column(Integer, default=0)
    status = Column(String(30), default="OPEN")  # OPEN, DISPATCHED, RESOLVED, CANCELLED
    ai_recommendation = Column(JSONB, default=dict)
    hitl_required = Column(Boolean, default=False)
    hitl_reviewed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_type = Column(String(50), nullable=False)  # RISK, ACCIDENT, WEATHER, CONGESTION
    message = Column(Text, nullable=False)
    latitude = Column(Float)
    longitude = Column(Float)
    risk_level = Column(String(20), default="MEDIUM")
    acknowledged = Column(Boolean, default=False)
    target_role = Column(String(20), default="officer")
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_name = Column(String(100), nullable=False, index=True)
    run_id = Column(String(100), unique=True)
    input_data = Column(JSONB, default=dict)
    output_data = Column(JSONB, default=dict)
    tokens_used = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    latency_ms = Column(Integer, default=0)
    success = Column(Boolean, default=True)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class HITLReview(Base):
    __tablename__ = "hitl_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_run_id = Column(UUID(as_uuid=True), nullable=True)
    review_type = Column(String(50), nullable=False)  # DISPATCH, ALERT, RISK_ACTION
    context_data = Column(JSONB, default=dict)
    reviewer_id = Column(UUID(as_uuid=True), nullable=True)
    decision = Column(String(20))  # APPROVED, REJECTED, MODIFIED
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime)
