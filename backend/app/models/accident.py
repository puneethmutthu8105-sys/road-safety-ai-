import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base
import enum


class AccidentSeverity(str, enum.Enum):
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"
    FATAL = "fatal"


class Accident(Base):
    __tablename__ = "accidents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    severity = Column(SAEnum(AccidentSeverity), nullable=False)
    date_time = Column(DateTime, nullable=False)
    weather_condition = Column(String(100))
    road_type = Column(String(100))
    vehicle_count = Column(Integer, default=0)
    casualties = Column(Integer, default=0)
    description = Column(Text)
    is_predicted = Column(Boolean, default=False)  # predicted vs confirmed
    source = Column(String(50), default="manual")  # manual, dataset, system
    created_by = Column(UUID(as_uuid=True), nullable=True)
    extra_data = Column(JSONB, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class RiskPrediction(Base):
    __tablename__ = "risk_predictions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    risk_score = Column(Float, nullable=False)  # 0–100
    risk_level = Column(String(20), nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    factors = Column(JSONB, default=dict)
    model_version = Column(String(50), default="v1")
    predicted_at = Column(DateTime, default=datetime.utcnow)


class AccidentHotspot(Base):
    __tablename__ = "hotspots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    radius_m = Column(Float, default=500.0)
    accident_count = Column(Integer, default=0)
    avg_severity_score = Column(Float, default=0.0)
    zone_label = Column(String(200))
    last_computed_at = Column(DateTime, default=datetime.utcnow)
