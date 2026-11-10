"""
MCP Weather Tool Server
Provides weather data tools for agents.
"""
import json
import random
from datetime import datetime
from fastmcp import FastMCP
from app.config import settings

mcp = FastMCP("Weather Tool Server")


def _fetch_live_weather(lat: float, lng: float) -> dict:
    """Try live OpenWeatherMap API; fall back to simulated."""
    if settings.OPENWEATHER_API_KEY:
        try:
            import httpx
            url = f"{settings.OPENWEATHER_BASE_URL}/weather"
            params = {"lat": lat, "lon": lng, "appid": settings.OPENWEATHER_API_KEY, "units": "metric"}
            with httpx.Client(timeout=5) as client:
                resp = client.get(url, params=params)
                data = resp.json()
            return {
                "condition": data["weather"][0]["main"].lower(),
                "description": data["weather"][0]["description"],
                "temperature_c": data["main"]["temp"],
                "humidity_pct": data["main"]["humidity"],
                "wind_speed_kmh": round(data["wind"]["speed"] * 3.6, 1),
                "visibility_m": data.get("visibility", 10000),
                "precipitation_mm": data.get("rain", {}).get("1h", 0),
                "source": "openweathermap_live"
            }
        except Exception:
            pass
    return _simulate_weather()


def _simulate_weather() -> dict:
    conditions = [
        ("clear", "clear sky", 28, 0, 10000, 0),
        ("clouds", "scattered clouds", 26, 20, 8000, 0),
        ("mist", "mist", 22, 60, 2000, 0),
        ("rain", "moderate rain", 20, 80, 3000, 8),
        ("thunderstorm", "thunderstorm with rain", 19, 85, 1500, 20),
        ("fog", "dense fog", 18, 90, 500, 0),
    ]
    weights = [0.40, 0.25, 0.10, 0.15, 0.05, 0.05]
    c = random.choices(conditions, weights)[0]
    return {
        "condition": c[0],
        "description": c[1],
        "temperature_c": c[2] + random.uniform(-3, 3),
        "humidity_pct": c[3] + random.randint(-5, 5),
        "visibility_m": c[4],
        "precipitation_mm": c[5] + random.uniform(0, 2),
        "wind_speed_kmh": round(random.uniform(5, 30), 1),
        "source": "simulated"
    }


@mcp.tool()
def get_weather(lat: float, lng: float) -> str:
    """Get current weather conditions at the given coordinates."""
    data = _fetch_live_weather(lat, lng)
    data["coordinates"] = {"lat": lat, "lng": lng}
    data["timestamp"] = datetime.utcnow().isoformat()
    return json.dumps(data)


@mcp.tool()
def get_weather_risk_level(lat: float, lng: float) -> str:
    """Get weather-based accident risk contribution."""
    weather = _fetch_live_weather(lat, lng)
    risk_weights = {
        "clear": 0, "clouds": 5, "mist": 20, "fog": 40,
        "drizzle": 15, "rain": 25, "thunderstorm": 45, "snow": 35
    }
    cond = weather.get("condition", "clear")
    risk = risk_weights.get(cond, 10)
    vis = weather.get("visibility_m", 10000)
    if vis < 500:
        risk += 30
    elif vis < 1000:
        risk += 15
    level = "CRITICAL" if risk >= 40 else "HIGH" if risk >= 25 else "MEDIUM" if risk >= 10 else "LOW"
    return json.dumps({"weather_risk_score": risk, "risk_level": level, "weather": weather})


if __name__ == "__main__":
    mcp.run(transport="stdio")
