"""
Traffic Data Simulator — generates realistic simulated traffic data.
Used when live traffic feeds are unavailable.
"""
import random
import math
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any
from app.config import settings

ROAD_SEGMENTS = [
    {"id": "SEG001", "name": "MG Road", "lat": 12.9758, "lng": 77.6005, "speed_limit": 50},
    {"id": "SEG002", "name": "Outer Ring Road E", "lat": 12.9569, "lng": 77.6978, "speed_limit": 80},
    {"id": "SEG003", "name": "Hosur Road", "lat": 12.9201, "lng": 77.6230, "speed_limit": 60},
    {"id": "SEG004", "name": "Old Madras Road", "lat": 12.9975, "lng": 77.6543, "speed_limit": 60},
    {"id": "SEG005", "name": "Bannerghatta Road", "lat": 12.8965, "lng": 77.5976, "speed_limit": 50},
    {"id": "SEG006", "name": "Bellary Road", "lat": 13.0298, "lng": 77.5936, "speed_limit": 70},
    {"id": "SEG007", "name": "Tumkur Road", "lat": 13.0087, "lng": 77.5235, "speed_limit": 70},
    {"id": "SEG008", "name": "Mysore Road", "lat": 12.9531, "lng": 77.4927, "speed_limit": 60},
    {"id": "SEG009", "name": "Kanakapura Road", "lat": 12.8754, "lng": 77.5612, "speed_limit": 50},
    {"id": "SEG010", "name": "Hennur Road", "lat": 13.0376, "lng": 77.6412, "speed_limit": 60},
    {"id": "SEG011", "name": "Electronic City", "lat": 12.8398, "lng": 77.6786, "speed_limit": 80},
    {"id": "SEG012", "name": "Sarjapur Road", "lat": 12.9150, "lng": 77.7098, "speed_limit": 60},
    {"id": "SEG013", "name": "Koramangala", "lat": 12.9352, "lng": 77.6245, "speed_limit": 40},
    {"id": "SEG014", "name": "Indiranagar", "lat": 12.9784, "lng": 77.6408, "speed_limit": 40},
    {"id": "SEG015", "name": "Whitefield", "lat": 12.9698, "lng": 77.7499, "speed_limit": 60},
]


def _hour_factor(hour: int) -> float:
    """Rush hour multiplier for density."""
    if 7 <= hour <= 9 or 17 <= hour <= 20:
        return random.uniform(1.8, 2.5)
    elif 0 <= hour <= 5:
        return random.uniform(0.1, 0.3)
    return random.uniform(0.6, 1.2)


def _congestion_level(density: float, speed: float) -> str:
    if density > 80 or speed < 15:
        return "SEVERE"
    elif density > 50 or speed < 25:
        return "HIGH"
    elif density > 25 or speed < 40:
        return "MEDIUM"
    return "LOW"


def generate_traffic_snapshot() -> List[Dict[str, Any]]:
    """Generate a single traffic snapshot for all segments."""
    hour = datetime.utcnow().hour
    factor = _hour_factor(hour)
    records = []
    for seg in ROAD_SEGMENTS:
        base_density = random.uniform(15, 40) * factor
        base_speed = max(5, seg["speed_limit"] * random.uniform(0.3, 1.0) / (1 + base_density / 60))
        density = round(base_density + random.gauss(0, 5), 1)
        speed = round(base_speed + random.gauss(0, 3), 1)
        congestion = _congestion_level(density, speed)
        records.append({
            "segment_id": seg["id"],
            "road_name": seg["name"],
            "latitude": seg["lat"] + random.uniform(-0.002, 0.002),
            "longitude": seg["lng"] + random.uniform(-0.002, 0.002),
            "density": max(0, density),
            "speed_kmh": max(3, speed),
            "congestion_level": congestion,
            "is_simulated": True,
            "timestamp": datetime.utcnow().isoformat(),
        })
    return records


def generate_historical_accidents(count: int = 200) -> List[Dict[str, Any]]:
    """Generate realistic historical accident dataset."""
    severities = ["minor", "moderate", "severe", "fatal"]
    severity_weights = [0.45, 0.35, 0.15, 0.05]
    weathers = ["clear", "rain", "fog", "mist", "cloudy"]
    road_types = ["urban", "highway", "rural", "intersection", "bridge"]

    accidents = []
    base_dt = datetime.utcnow() - timedelta(days=365)

    # Generate clustered accidents (hotspot simulation)
    hotspot_locs = [
        (12.9758, 77.6005), (12.9201, 77.6230), (12.8398, 77.6786),
        (12.9531, 77.4927), (12.9784, 77.6408),
    ]

    for i in range(count):
        # 60% near hotspots, 40% random
        if random.random() < 0.6 and hotspot_locs:
            base = random.choice(hotspot_locs)
            lat = base[0] + random.gauss(0, 0.005)
            lng = base[1] + random.gauss(0, 0.005)
        else:
            lat = settings.CITY_LAT + random.uniform(-0.15, 0.15)
            lng = settings.CITY_LNG + random.uniform(-0.15, 0.15)

        dt = base_dt + timedelta(
            days=random.randint(0, 364),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59)
        )
        severity = random.choices(severities, severity_weights)[0]
        vehicles = random.randint(1, 4) if severity in ("moderate", "severe", "fatal") else 1
        casualties = 0
        if severity == "minor":
            casualties = random.randint(0, 1)
        elif severity == "moderate":
            casualties = random.randint(0, 3)
        elif severity == "severe":
            casualties = random.randint(1, 5)
        elif severity == "fatal":
            casualties = random.randint(1, 8)

        accidents.append({
            "id": str(uuid.uuid4()),
            "latitude": round(lat, 5),
            "longitude": round(lng, 5),
            "severity": severity,
            "date_time": dt.isoformat(),
            "weather_condition": random.choice(weathers),
            "road_type": random.choice(road_types),
            "vehicle_count": vehicles,
            "casualties": casualties,
            "is_predicted": False,
            "source": "simulated_dataset",
        })
    return accidents


def generate_simulated_ambulances(count: int = 20) -> List[Dict[str, Any]]:
    """Generate simulated ambulance fleet."""
    hospitals = [
        ("Manipal Hospital", 12.9560, 77.6470),
        ("Apollo Hospital", 12.9601, 77.6447),
        ("Fortis Hospital", 12.9263, 77.6745),
        ("Sakra World Hospital", 12.9291, 77.7111),
        ("Narayana Health", 12.8404, 77.6785),
        ("St. John's Medical", 12.9497, 77.6226),
    ]
    statuses = ["AVAILABLE", "AVAILABLE", "AVAILABLE", "ENROUTE", "BUSY"]
    ambulances = []
    for i in range(count):
        hosp = random.choice(hospitals)
        # Ambulance within 5km of hospital
        lat = hosp[1] + random.uniform(-0.04, 0.04)
        lng = hosp[2] + random.uniform(-0.04, 0.04)
        ambulances.append({
            "id": str(uuid.uuid4()),
            "registration_no": f"KA01-AMB-{1000+i}",
            "latitude": round(lat, 5),
            "longitude": round(lng, 5),
            "status": random.choice(statuses),
            "hospital_name": hosp[0],
            "hospital_lat": hosp[1],
            "hospital_lng": hosp[2],
            "contact_number": f"+91-80-{random.randint(20000000, 29999999)}",
            "is_simulated": True,
        })
    return ambulances


def generate_road_conditions(count: int = 15) -> List[Dict[str, Any]]:
    """Generate simulated road condition reports."""
    condition_types = ["pothole", "wet_surface", "fog", "construction", "debris", "flooded"]
    conditions = []
    for i in range(count):
        lat = settings.CITY_LAT + random.uniform(-0.12, 0.12)
        lng = settings.CITY_LNG + random.uniform(-0.12, 0.12)
        conditions.append({
            "id": str(uuid.uuid4()),
            "latitude": round(lat, 5),
            "longitude": round(lng, 5),
            "condition_type": random.choice(condition_types),
            "severity_score": round(random.uniform(1, 10), 1),
            "verified": random.choice([True, False]),
            "reported_at": (datetime.utcnow() - timedelta(hours=random.randint(0, 72))).isoformat(),
        })
    return conditions
