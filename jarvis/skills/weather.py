"""Live weather for the user's city (from memory/settings)."""

from __future__ import annotations

from typing import Any

import httpx

from jarvis.config import settings
from jarvis.memory.store import memory
from jarvis.skills.base import Skill


class WeatherSkill(Skill):
    name = "weather"
    TOOL = {
        "name": "weather_report",
        "description": "Get live weather for a city (defaults to remembered city)",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
        },
    }

    def handler(self, args: dict) -> Any:
        city = (args.get("city") or settings.get("city") or "").strip()
        if not city:
            hits = memory.search("city lives OR location OR weather", limit=3)
            for h in hits:
                city = h.content
                break
        if not city:
            return {"ok": False, "error": "No city known — ask the user or set city in settings"}
        try:
            # Open-Meteo geocoding + forecast (no API key)
            geo = httpx.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": city, "count": 1},
                timeout=20,
            ).json()
            results = geo.get("results") or []
            if not results:
                return {"ok": False, "error": f"city not found: {city}"}
            lat, lon = results[0]["latitude"], results[0]["longitude"]
            name = results[0].get("name", city)
            wx = httpx.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                },
                timeout=20,
            ).json()
            cur = wx.get("current", {})
            report = {
                "city": name,
                "temperature_c": cur.get("temperature_2m"),
                "humidity": cur.get("relative_humidity_2m"),
                "wind_kmh": cur.get("wind_speed_10m"),
                "weather_code": cur.get("weather_code"),
            }
            return {"ok": True, "report": report, "display": report}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
