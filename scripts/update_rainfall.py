"""Earth Engine rainfall query for SERPRO scopes using NASA GPM IMERG V07."""
from __future__ import annotations

import csv
import gzip
import json
import os
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import ee
from google.oauth2 import service_account

KML_NS = {"kml": "http://www.opengis.net/kml/2.2"}
PROJECT_AREA_KML = Path("data/static/project_boundary.kml.gz")
PROJECT_ZONE_GEOJSON = Path("data/static/boundaries/serpro_carbon_project_zone_web.geojson")
OUTPUT = Path("data/processed/climate/rainfall/rainfall_daily.csv")
COLLECTION = "NASA/GPM_L3/IMERG_V07"
PRECIP_BAND = "precipitation"
HALF_HOUR_HOURS = 0.5
DAYS_TO_KEEP = 30


def authenticate_ee() -> None:
    key_json = os.environ.get("EE_SERVICE_ACCOUNT_JSON")
    cloud_project = os.environ.get("EE_PROJECT_ID")
    if not key_json or not cloud_project:
        raise RuntimeError("Set EE_SERVICE_ACCOUNT_JSON and EE_PROJECT_ID GitHub secrets.")
    try:
        info = json.loads(key_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError("EE_SERVICE_ACCOUNT_JSON is not valid JSON.") from exc
    required = ("type", "project_id", "private_key", "client_email", "token_uri")
    missing = [field for field in required if not info.get(field)]
    if missing:
        raise RuntimeError("EE_SERVICE_ACCOUNT_JSON is missing required fields: " + ", ".join(missing))
    private_key = info["private_key"].strip()
    if "..." in private_key:
        raise RuntimeError("EE_SERVICE_ACCOUNT_JSON contains placeholder text ('...') in private_key.")
    if not private_key.startswith("-----BEGIN PRIVATE KEY-----"):
        raise RuntimeError("EE_SERVICE_ACCOUNT_JSON private_key does not start with the expected PEM header.")
    if not private_key.endswith("-----END PRIVATE KEY-----"):
        raise RuntimeError("EE_SERVICE_ACCOUNT_JSON private_key does not contain the expected PEM footer.")
    if len(private_key) < 500:
        raise RuntimeError("EE_SERVICE_ACCOUNT_JSON private_key appears truncated.")

    credentials = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    ee.Initialize(credentials=credentials, project=cloud_project)
    print(f"Earth Engine initialized with project: {cloud_project}")
    print(f"Earth Engine service account: {info['client_email']}")


def project_area_geometry() -> ee.Geometry:
    with gzip.open(PROJECT_AREA_KML, "rb") as fh:
        root = ET.fromstring(fh.read())
    polygons = []
    for node in root.findall(
        ".//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", KML_NS
    ):
        coords = []
        for item in (node.text or "").split():
            p = item.split(",")
            if len(p) >= 2:
                coords.append([float(p[0]), float(p[1])])
        if len(coords) >= 4:
            polygons.append(ee.Geometry.Polygon(coords))
    if not polygons:
        raise RuntimeError("No polygons found in SERPRO Project Area KML.")
    return ee.Geometry.MultiPolygon(polygons) if len(polygons) > 1 else polygons[0]


def project_zone_geometry() -> ee.Geometry:
    obj = json.loads(PROJECT_ZONE_GEOJSON.read_text(encoding="utf-8"))
    features = obj.get("features", [])
    if not features:
        raise RuntimeError("No features found in SERPRO Carbon Project Zone GeoJSON.")
    return ee.Geometry(features[0]["geometry"])


def zonal_daily_rainfall(collection: ee.ImageCollection, geometry: ee.Geometry) -> float:
    # IMERG precipitation is a rain rate (mm/hour) on 30-minute images.
    # Convert each half-hour rate to mm per interval, then sum across the day.
    daily_mm = collection.select(PRECIP_BAND).sum().multiply(HALF_HOUR_HOURS)
    value = daily_mm.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geometry,
        scale=11132,
        maxPixels=1_000_000,
        bestEffort=True,
    ).get(PRECIP_BAND)
    result = value.getInfo() if value is not None else None
    return float(result) if result is not None else float("nan")


def latest_available_date() -> date | None:
    collection = ee.ImageCollection(COLLECTION)
    latest_ms = collection.aggregate_max("system:time_start").getInfo()
    if latest_ms is None:
        return None
    return datetime.fromtimestamp(latest_ms / 1000, tz=timezone.utc).date()


def fetch_day(date_value: date, scopes):
    start = ee.Date(date_value.strftime("%Y-%m-%d"))
    end = start.advance(1, "day")
    collection = ee.ImageCollection(COLLECTION).filterDate(start, end)
    count = collection.size().getInfo()
    if count == 0:
        print(f"No GPM IMERG image available for {date_value}; skipping.")
        return []

    rows = []
    for scope_name, geometry in scopes.items():
        rows.append({
            "date": date_value.strftime("%Y-%m-%d"),
            "scope": scope_name,
            "rainfall_mm": zonal_daily_rainfall(collection, geometry),
            "source": COLLECTION,
            "processing_time_utc": datetime.now(timezone.utc).isoformat(),
        })
    return rows


def main() -> None:
    authenticate_ee()
    scopes = {
        "carbon_project_zone": project_zone_geometry(),
        "project_area": project_area_geometry(),
    }

    latest = latest_available_date()
    if latest is None:
        raise RuntimeError("GPM IMERG collection contains no observations.")

    dates = [latest - timedelta(days=i) for i in range(DAYS_TO_KEEP - 1, -1, -1)]
    rows = []
    for date_value in dates:
        rows.extend(fetch_day(date_value, scopes))

    if not rows:
        raise RuntimeError("No GPM IMERG rainfall observations were available.")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUTPUT}")
    print(f"Latest available GPM date: {latest}")
    print(f"Retention window: {DAYS_TO_KEEP} calendar days")


if __name__ == "__main__":
    main()
