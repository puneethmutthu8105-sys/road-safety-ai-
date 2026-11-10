"""
Road Safety AI — FastAPI Application Entry Point
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import init_db
from app.auth.router import router as auth_router
from app.api.traffic import router as traffic_router
from app.api.accidents import router as accident_router
from app.api.emergency import router as emergency_router
from app.api.ambulance import router as ambulance_router
from app.api.reports import router as reports_router
from app.api.admin import router as admin_router
from app.websocket.alerts import ws_alert_endpoint


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    await init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-Powered Road Accident Prediction & Emergency Response System",
    lifespan=lifespan,
)

# CORS — allow frontend dev server and any Render/production domain
import os as _os
_allowed_origins = ["http://localhost:5173", "http://localhost:3000"]
_frontend_url = _os.environ.get("FRONTEND_URL", "")
if _frontend_url:
    _allowed_origins.append(_frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_origin_regex=r"https://.*\.onrender\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router,      prefix="/api/v1")
app.include_router(traffic_router,   prefix="/api/v1")
app.include_router(accident_router,  prefix="/api/v1")
app.include_router(emergency_router, prefix="/api/v1")
app.include_router(ambulance_router, prefix="/api/v1")
app.include_router(reports_router,   prefix="/api/v1")
app.include_router(admin_router,     prefix="/api/v1")


# WebSocket
@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    await ws_alert_endpoint(websocket)


@app.get("/", tags=["health"])
async def root():
    return {"name": settings.APP_NAME, "version": settings.APP_VERSION, "status": "running"}


@app.get("/health", tags=["health"])
async def health():
    return {"status": "healthy", "version": settings.APP_VERSION}


@app.get("/api/v1/road-conditions", tags=["road-conditions"])
async def get_road_conditions():
    """Get current simulated road conditions."""
    from app.utils.data_simulator import generate_road_conditions
    conditions = generate_road_conditions(15)
    return {"conditions": conditions, "count": len(conditions), "source": "simulated"}


@app.post("/api/v1/road-conditions/analyze", tags=["road-conditions"])
async def analyze_road_conditions():
    """Run Road Condition Monitoring Agent."""
    from app.utils.data_simulator import generate_road_conditions
    from app.mcp_servers.weather_tool_server import _fetch_live_weather
    from app.config import settings
    from app.agents.road_condition_agent import monitor_road_conditions
    conditions = generate_road_conditions(15)
    weather = _fetch_live_weather(settings.CITY_LAT, settings.CITY_LNG)
    return await monitor_road_conditions(conditions, weather)
