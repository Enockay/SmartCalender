"""Weather service using Open-Meteo API (free, no API key required).

Workflow:
1. Resolve the user's location:
   - If a city is saved in AppSettings, geocode it via Open-Meteo Geocoding.
   - Otherwise, auto-detect via ip-api.com (IP geolocation).
2. Fetch current weather from api.open-meteo.com.
3. Cache results for 30 minutes to avoid excessive calls.
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Optional

from app.database.db_manager import DatabaseManager
from app.repositories.settings_repository import SettingsRepository


# ── Data models ──────────────────────────────────────────────

@dataclass
class WeatherData:
    temperature_c: float = 0.0
    temperature_f: float = 32.0
    weather_code: int = 0          # WMO weather code
    description: str = "Unknown"
    icon: str = "🌡"               # Emoji icon
    city: str = ""
    wind_speed_kmh: float = 0.0
    humidity: int = 0
    is_day: bool = True
    fetched_at: float = 0.0        # timestamp


# ── WMO weather codes → description + icon ──────────────────

_WMO_MAP: dict[int, tuple[str, str, str]] = {
    # code: (description, day_icon, night_icon)
    0:  ("Clear sky",           "☀️", "🌙"),
    1:  ("Mainly clear",        "🌤", "🌙"),
    2:  ("Partly cloudy",       "⛅", "☁️"),
    3:  ("Overcast",            "☁️", "☁️"),
    45: ("Foggy",               "🌫", "🌫"),
    48: ("Rime fog",            "🌫", "🌫"),
    51: ("Light drizzle",       "🌦", "🌧"),
    53: ("Moderate drizzle",    "🌦", "🌧"),
    55: ("Dense drizzle",       "🌧", "🌧"),
    56: ("Freezing drizzle",    "🌧", "🌧"),
    57: ("Heavy freezing drizzle", "🌧", "🌧"),
    61: ("Slight rain",         "🌦", "🌧"),
    63: ("Moderate rain",       "🌧", "🌧"),
    65: ("Heavy rain",          "🌧", "🌧"),
    66: ("Freezing rain",       "🌧", "🌧"),
    67: ("Heavy freezing rain", "🌧", "🌧"),
    71: ("Slight snow",         "🌨", "🌨"),
    73: ("Moderate snow",       "❄️", "❄️"),
    75: ("Heavy snow",          "❄️", "❄️"),
    77: ("Snow grains",         "❄️", "❄️"),
    80: ("Slight showers",      "🌦", "🌧"),
    81: ("Moderate showers",    "🌧", "🌧"),
    82: ("Violent showers",     "⛈", "⛈"),
    85: ("Snow showers",        "🌨", "🌨"),
    86: ("Heavy snow showers",  "❄️", "❄️"),
    95: ("Thunderstorm",        "⛈", "⛈"),
    96: ("Thunderstorm + hail", "⛈", "⛈"),
    99: ("Heavy thunderstorm",  "⛈", "⛈"),
}


def _decode_wmo(code: int, is_day: bool = True) -> tuple[str, str]:
    """Return (description, emoji) for a WMO weather code."""
    entry = _WMO_MAP.get(code, ("Unknown", "🌡", "🌡"))
    desc = entry[0]
    icon = entry[1] if is_day else entry[2]
    return desc, icon


# ── Service ──────────────────────────────────────────────────

SETTINGS_CITY_KEY = "weather_city"
_CACHE_TTL = 1800  # 30 minutes


def _ssl_ctx() -> ssl.SSLContext:
    """Create an SSL context, falling back to unverified if certs are missing.

    macOS + conda/miniconda Python often lacks the system CA bundle,
    causing CERTIFICATE_VERIFY_FAILED.  We try certifi first, then
    do a real probe, and finally fall back to unverified for these
    public read-only weather APIs.
    """
    # Try 1: use certifi CA bundle if available
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass

    # Try 2: default context — probe a real HTTPS host to check
    try:
        ctx = ssl.create_default_context()
        import socket
        with socket.create_connection(("api.open-meteo.com", 443), timeout=4) as sock:
            with ctx.wrap_socket(sock, server_hostname="api.open-meteo.com"):
                pass
        return ctx
    except Exception:
        pass

    # Try 3: unverified (safe for public read-only weather APIs)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


class WeatherService:
    """Fetches live weather data with caching."""

    def __init__(self, db: DatabaseManager | None = None) -> None:
        self._db = db or DatabaseManager()
        self._cache: Optional[WeatherData] = None
        self._ssl: ssl.SSLContext = _ssl_ctx()

    # ── Public API ───────────────────────────────────────────

    def get_current_weather(self) -> WeatherData:
        """Return current weather data, using cache if fresh."""
        if self._cache and (time.time() - self._cache.fetched_at) < _CACHE_TTL:
            return self._cache

        try:
            lat, lon, city = self._resolve_location()
            data = self._fetch_weather(lat, lon, city)
            self._cache = data
            return data
        except Exception:
            # Return cached (even stale) or a fallback
            if self._cache:
                return self._cache
            return WeatherData(description="Unavailable", icon="🌡")

    def get_saved_city(self) -> str:
        """Return the city name saved in settings, or empty."""
        session = self._db.session()
        try:
            repo = SettingsRepository(session)
            return repo.get(SETTINGS_CITY_KEY) or ""
        finally:
            session.close()

    def set_city(self, city: str) -> None:
        """Save a city name to settings and invalidate cache."""
        session = self._db.session()
        try:
            repo = SettingsRepository(session)
            repo.set(SETTINGS_CITY_KEY, city.strip())
        finally:
            session.close()
        self._cache = None  # force refresh

    # ── Location resolution ──────────────────────────────────

    def _resolve_location(self) -> tuple[float, float, str]:
        """Return (lat, lon, city_name)."""
        city = self.get_saved_city()
        if city:
            return self._geocode_city(city)
        return self._geolocate_ip()

    def _geocode_city(self, city: str) -> tuple[float, float, str]:
        """Geocode a city name via Open-Meteo Geocoding API."""
        url = (
            f"https://geocoding-api.open-meteo.com/v1/search"
            f"?name={urllib.request.quote(city)}&count=1&language=en&format=json"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "SmartCalender/1.0"})
        with urllib.request.urlopen(req, timeout=8, context=self._ssl) as resp:
            data = json.loads(resp.read().decode())

        results = data.get("results", [])
        if not results:
            raise ValueError(f"City not found: {city}")

        r = results[0]
        return r["latitude"], r["longitude"], r.get("name", city)

    def _geolocate_ip(self) -> tuple[float, float, str]:
        """Auto-detect location from IP address via ip-api.com."""
        url = "http://ip-api.com/json/?fields=status,city,lat,lon"
        req = urllib.request.Request(url, headers={"User-Agent": "SmartCalender/1.0"})
        # ip-api.com uses HTTP, so no SSL context needed
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())

        if data.get("status") != "success":
            # Fallback: Nairobi, Kenya
            return -1.2921, 36.8219, "Nairobi"

        return data["lat"], data["lon"], data.get("city", "Unknown")

    # ── Weather fetch ────────────────────────────────────────

    def _fetch_weather(self, lat: float, lon: float, city: str) -> WeatherData:
        """Fetch current weather from Open-Meteo."""
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,is_day"
            f"&temperature_unit=celsius"
            f"&wind_speed_unit=kmh"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "SmartCalender/1.0"})
        with urllib.request.urlopen(req, timeout=8, context=self._ssl) as resp:
            data = json.loads(resp.read().decode())

        current = data.get("current", {})
        temp_c = current.get("temperature_2m", 0.0)
        temp_f = round(temp_c * 9 / 5 + 32, 1)
        code = current.get("weather_code", 0)
        is_day = bool(current.get("is_day", 1))
        desc, icon = _decode_wmo(code, is_day)

        return WeatherData(
            temperature_c=temp_c,
            temperature_f=temp_f,
            weather_code=code,
            description=desc,
            icon=icon,
            city=city,
            wind_speed_kmh=current.get("wind_speed_10m", 0.0),
            humidity=int(current.get("relative_humidity_2m", 0)),
            is_day=is_day,
            fetched_at=time.time(),
        )
