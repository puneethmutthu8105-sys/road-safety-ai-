import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


class RoadCondition(Base):
    __tablename__ = "road_conditions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    condition_type = Column(String(50), nullable=False)  # pothole, wet, fog, construction, debris
    severity_score = Column(Float, default=0.0)  # 0–10
    description = Column(Text)
    road_name = Column(String(200))
    weather_data = Column(JSONB, default=dict)  # temp, precip, visibility, wind
    verified = Column(Boolean, default=False)
    reported_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
