from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests

BMKG_LOCATIONS = {
    "Pematang Limau": "62.07.01.2005",
    "Tanjung Rangas": "62.07.01.2007",
    "Mekar Indah": "62.07.06.2001",
    "Halimaung Jaya": "62.07.06.2002",
    "Sungai Bakau": "62.07.06.2006",
}
BMKG_BASE_URL = "https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4={}"


def _num(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_location(payload: dict, name: str, adm4: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    # BMKG forecast responses have weather lists under data[].cuaca, usually nested by day.
    for block in payload.get("data", []) or []:
        cuaca = block.get("cuaca", []) if isinstance(block, dict) else []
        if isinstance(cuaca, dict):
            cuaca = [cuaca]
        for day in cuaca or []:
            items = day if isinstance(day, list) else [day]
            for item in items:
                if not isinstance(item, dict):
                    continue
                dt = item.get("local_datetime") or item.get("datetime")
                if not dt:
                    continue
                rows.append({
                    "location": name,
                    "adm4": adm4,
                    "datetime": item.get("datetime"),
                    "local_datetime": dt,
                    "temperature_c": _num(item.get("t")),
                    "humidity_pct": _num(item.get("hu")),
                    "precipitation_mm": _num(item.get("tp")),
                    "weather": item.get("weather"),
                    "weather_desc": item.get("weather_desc"),
                    "weather_desc_en": item.get("weather_desc_en"),
                    "wind_direction_deg": _num(item.get("wd_deg") or item.get("wind_direction_degree")),
                    "wind_direction": item.get("wd") or item.get("wind_direction"),
                    "wind_direction_to": item.get("wd_to") or item.get("wind_direction_to"),
                    "wind_speed_ms": _num(item.get("ws") or item.get("wind_speed")),
                    "cloud_cover_pct": _num(item.get("tcc") or item.get("cloud_cover")),
                    "visibility": item.get("vs_text") or item.get("visibility"),
                    "time_index": item.get("time_index"),
                    "analysis_date": item.get("analysis_date"),
                })
    return rows


def load_bmkg_forecast(timeout: int = 20) -> tuple[pd.DataFrame, dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    quality: list[dict[str, Any]] = []
    fetched_at = datetime.now(timezone.utc).isoformat()
    for name, adm4 in BMKG_LOCATIONS.items():
        try:
            response = requests.get(BMKG_BASE_URL.format(adm4), timeout=timeout)
            response.raise_for_status()
            payload = response.json()
            location_rows = _parse_location(payload, name, adm4)
            rows.extend(location_rows)
            quality.append({"location": name, "adm4": adm4, "status": "OK", "records": len(location_rows), "error": ""})
        except Exception as exc:  # keep dashboard alive if one location is unavailable
            quality.append({"location": name, "adm4": adm4, "status": "ERROR", "records": 0, "error": str(exc)[:180]})

    df = pd.DataFrame(rows)
    if not df.empty:
        df["local_datetime"] = pd.to_datetime(df["local_datetime"], errors="coerce")
        df = df.dropna(subset=["local_datetime"]).sort_values(["location", "local_datetime"]).drop_duplicates(["location", "local_datetime"])
    meta = {
        "source": "BMKG Open Data",
        "endpoint_type": "3-day weather forecast",
        "interval": "3-hour",
        "locations": len(BMKG_LOCATIONS),
        "fetched_at_utc": fetched_at,
        "quality": pd.DataFrame(quality),
    }
    return df, meta
