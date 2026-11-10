import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


class TrafficRecord(Base):
    __tablename__ = "traffic_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    segment_id = Column(String(100), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    density = Column(Float, default=0.0)        # vehicles per km
    speed_kmh = Column(Float, default=0.0)
    congestion_level = Column(String(20), default="LOW")  # LOW, MEDIUM, HIGH, SEVERE
    road_name = Column(String(200))
    is_simulated = Column(Boolean, default=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    extra_data = Column(JSONB, default=dict)
