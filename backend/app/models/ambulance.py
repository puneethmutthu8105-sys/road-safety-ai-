import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


class Ambulance(Base):
    __tablename__ = "ambulances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_no = Column(String(50), unique=True, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    status = Column(String(20), default="AVAILABLE")  # AVAILABLE, ENROUTE, BUSY, OFFLINE
    hospital_name = Column(String(200))
    hospital_lat = Column(Float)
    hospital_lng = Column(Float)
    contact_number = Column(String(20))
    is_simulated = Column(Boolean, default=True)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DispatchRecord(Base):
    __tablename__ = "dispatch_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    emergency_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    ambulance_id = Column(UUID(as_uuid=True), nullable=False)
    dispatched_at = Column(DateTime, default=datetime.utcnow)
    arrived_at = Column(DateTime)
    route_data = Column(JSONB, default=dict)  # GeoJSON route
    eta_minutes = Column(Integer)
    distance_km = Column(Float)
    status = Column(String(20), default="DISPATCHED")  # DISPATCHED, ARRIVED, CANCELLED
    notes = Column(Text)
