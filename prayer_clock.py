"""City-level prayer-time ambience; no GPS, address or precise location access.

Prayer times from Aladhan are approximate and may differ from the user's
mosque timetable or chosen school. This module controls visual atmosphere only:
it does not issue religious notifications or determine prayer obligations.
"""
from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo
import re

import requests

TIME_ZONE = "Europe/London"
CITIES = ("London", "Birmingham", "Manchester", "Leeds", "Glasgow", "Bristol", "Edinburgh", "Cardiff")
FIELDS = ("Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha")
_CLOCK = re.compile(r"^(\d{1,2}):(\d{2})")


@lru_cache(maxsize=40)
def _remote_times(city: str, date_string: str, six_hour_bucket: int) -> dict:
    if city not in CITIES:
        return {}
    try:
        response = requests.get(
            f"https://api.aladhan.com/v1/timingsByCity/{date_string}",
            params={
                "city": city, "country": "United Kingdom", "method": 3,
                "school": 0,  # MWL, Shafi calculation for illustrative ambience
            },
            timeout=(2, 4),
        )
        response.raise_for_status()
        payload = response.json()
        timings = payload.get("data", {}).get("timings", {})
        result = {}
        for key in FIELDS:
            raw = timings.get(key, "")
            m = _CLOCK.match(str(raw))
            if m and int(m.group(1)) < 24 and int(m.group(2)) < 60:
                result[key] = f"{int(m.group(1)):02d}:{m.group(2)}"
        return result if len(result) == len(FIELDS) else {}
    except (requests.RequestException, ValueError, TypeError, AttributeError):
        return {}


def room_prayer_times(city: str = "London") -> dict:
    """Provide visually indicative timings and the selected UK city only."""
    city = city if city in CITIES else "London"
    now = datetime.now(ZoneInfo(TIME_ZONE))
    current = _remote_times(city, now.strftime("%d-%m-%Y"), now.hour // 6)
    return {
        "city": city,
        "cities": list(CITIES),
        "date": now.strftime("%Y-%m-%d"),
        "timezone": TIME_ZONE,
        "method": "MWL (approximate)",
        "times": current,
        "available": bool(current),
        "note": ("Indicative city-level times, not a local mosque timetable."
                 if current else "Prayer times unavailable; automatic ambience follows approximate local daylight instead."),
    }
