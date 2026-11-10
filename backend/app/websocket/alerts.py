"""WebSocket alerts handler for real-time notifications."""
import json
import asyncio
from datetime import datetime
from typing import Set
from fastapi import WebSocket, WebSocketDisconnect


class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: dict):
        disconnected = set()
        for ws in self.active_connections:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                disconnected.add(ws)
        self.active_connections -= disconnected

    async def send_personal(self, websocket: WebSocket, message: dict):
        try:
            await websocket.send_text(json.dumps(message))
        except Exception:
            self.disconnect(websocket)


manager = ConnectionManager()


async def ws_alert_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time risk alerts and updates."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; alerts are pushed via manager.broadcast()
            await asyncio.sleep(30)
            await websocket.send_text(json.dumps({"type": "ping", "ts": datetime.utcnow().isoformat()}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)


async def broadcast_risk_alert(risk_level: str, message: str, lat: float = None, lng: float = None):
    """Broadcast a risk alert to all connected WebSocket clients."""
    payload = {
        "type": "risk_alert",
        "risk_level": risk_level,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
    }
    if lat is not None:
        payload["location"] = {"lat": lat, "lng": lng}
    await manager.broadcast(payload)


async def broadcast_emergency_update(emergency_id: str, status: str, severity: str):
    """Broadcast an emergency status update."""
    await manager.broadcast({
        "type": "emergency_update",
        "emergency_id": emergency_id,
        "status": status,
        "severity": severity,
        "timestamp": datetime.utcnow().isoformat(),
    })
