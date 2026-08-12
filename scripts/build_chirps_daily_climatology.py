"""Build daily CHIRPS climatology for SERPRO scopes.

Baseline period: 1991-2020.
The daily climatology is keyed by calendar month/day so current GPM daily
rainfall can be compared with the matching historical day-of-year window.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import ee
from google.oauth2 import service_account

COLLECTION = "UCSB-CHG/CHIRPS/DAILY"
BAND = "precipitation"
START = "1991-01-01"
END = "2021-01-01"
SCALE = 5566
OUT_DIR = Path("data/processed/climate/rainfall")
OUTPUT = OUT_DIR / "chirps_daily_climatology_1991_2020.csv"
META = OUT_DIR / "chirps_daily_climatology_metadata.json"


def authenticate_ee() -> None:
    raw = os.environ.get("EE_SERVICE_ACCOUNT_JSON")
    project = os.environ.get("EE_PROJECT_ID")
    if not raw or not project:
        raise RuntimeError("Set EE_SERVICE_ACCOUNT_JSON and EE_PROJECT_ID GitHub secrets.")
    info = json.loads(raw)
    required = ("type", "project_id", "private_key", "client_email", "token_uri")
    missing = [k for k in required if not info.get(k)]
    if missing:
        raise RuntimeError("Missing service-account fields: " + ", ".join(missing))
    key = info["private_key"].strip()
    if "..." in key or not key.startswith("-----BEGIN PRIVATE KEY-----") or not key.endswith("-----END PRIVATE KEY-----"):
        raise RuntimeError("Invalid or truncated service-account private key.")
    credentials = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    ee.Initialize(credentials=credentials, project=project)
    print(f"Earth Engine initialized with project: {project}")
    print(f"Earth Engine service account: {info['client_email']}")


def load_scope_geometries() -> dict[str, ee.Geometry]:
    import gzip
    import xml.etree.ElementTree as ET

    kml = Path("data/static/project_boundary.kml.gz")
    zone = Path("data/static/boundaries/serpro_carbon_project_zone_web.geojson")
    ns = {"k": "http://www.opengis.net/kml/2.2"}
    with gzip.open(kml, "rb") as fh:
        root = ET.fromstring(fh.read())
    polygons = []
    for node in root.findall(".//k:Polygon/k:outerBoundaryIs/k:LinearRing/k:coordinates", ns):
        ring = []
        for item in (node.text or "").split():
            parts = item.split(",")
            if len(parts) >= 2:
                ring.append([float(parts[0]), float(parts[1])])
        if len(ring) >= 4:
            polygons.append(ring)
    if not polygons:
        raise RuntimeError("No polygons found in Project Area KML.")
    project_area = ee.Geometry.MultiPolygon(polygons) if len(polygons) > 1 else ee.Geometry.Polygon(polygons[0])

    zone_obj = json.loads(zone.read_text(encoding="utf-8"))
    features = zone_obj.get("features", [])
    if not features:
        raise RuntimeError("No features found in Carbon Project Zone GeoJSON.")
    project_zone = ee.Geometry(features[0]["geometry"])
    return {"carbon_project_zone": project_zone, "project_area": project_area}


def calendar_days() -> list[tuple[int, int]]:
    return [(2, 29)] + [(month, day) for month in range(1, 13) for day in range(1, 32) if not (month == 2 and day == 29)]


def build_daily_features(scopes: dict[str, ee.Geometry]) -> ee.FeatureCollection:
    collection = ee.ImageCollection(COLLECTION).filterDate(START, END).select(BAND)
    day_features = [ee.Feature(None, {"month": m, "day": d}) for m, d in calendar_days()]
    template = ee.FeatureCollection(day_features)

    def one_day(feature: ee.Feature) -> ee.Feature:
        month = ee.Number(feature.get("month"))
        day = ee.Number(feature.get("day"))
        day_images = collection.filter(ee.Filter.calendarRange(month, month, "month")).filter(
            ee.Filter.calendarRange(day, day, "day_of_month")
        )

        def add_spatial_means(image: ee.Image) -> ee.Image:
            zone_mean = image.reduceRegion(
                reducer=ee.Reducer.mean(), geometry=scopes["carbon_project_zone"],
                scale=SCALE, maxPixels=1_000_000, bestEffort=True
            ).get(BAND)
            project_mean = image.reduceRegion(
                reducer=ee.Reducer.mean(), geometry=scopes["project_area"],
                scale=SCALE, maxPixels=1_000_000, bestEffort=True
            ).get(BAND)
            return image.set({"zone_mean": zone_mean, "project_mean": project_mean})

        scored = day_images.map(add_spatial_means).filter(ee.Filter.notNull(["zone_mean", "project_mean"]))
        zone_stats = scored.reduceColumns(
            ee.Reducer.mean().combine(ee.Reducer.stdDev(), sharedInputs=True)
            .combine(ee.Reducer.percentile([10, 25, 50, 75, 90]), sharedInputs=True),
            ["zone_mean"],
        )
        project_stats = scored.reduceColumns(
            ee.Reducer.mean().combine(ee.Reducer.stdDev(), sharedInputs=True)
            .combine(ee.Reducer.percentile([10, 25, 50, 75, 90]), sharedInputs=True),
            ["project_mean"],
        )
        return feature.set({
            "zone_mean_mm": zone_stats.get("mean"),
            "zone_std_mm": zone_stats.get("stdDev"),
            "zone_p10_mm": zone_stats.get("p10"),
            "zone_p25_mm": zone_stats.get("p25"),
            "zone_median_mm": zone_stats.get("p50"),
            "zone_p75_mm": zone_stats.get("p75"),
            "zone_p90_mm": zone_stats.get("p90"),
            "zone_n_obs": scored.aggregate_count("zone_mean"),
            "project_mean_mm": project_stats.get("mean"),
            "project_std_mm": project_stats.get("stdDev"),
            "project_p10_mm": project_stats.get("p10"),
            "project_p25_mm": project_stats.get("p25"),
            "project_median_mm": project_stats.get("p50"),
            "project_p75_mm": project_stats.get("p75"),
            "project_p90_mm": project_stats.get("p90"),
            "project_n_obs": scored.aggregate_count("project_mean"),
        })

    return template.map(one_day)


def main() -> None:
    authenticate_ee()
    scopes = load_scope_geometries()
    features = build_daily_features(scopes).getInfo()["features"]
    rows: list[dict] = []
    for feature in features:
        p = feature.get("properties", {})
        if p.get("zone_mean_mm") is None:
            continue
        rows.extend([
            {
                "month": int(p["month"]), "day": int(p["day"]),
                "scope": "carbon_project_zone",
                "normal_mean_mm": float(p["zone_mean_mm"]),
                "normal_std_mm": float(p["zone_std_mm"]),
                "p10_mm": float(p["zone_p10_mm"]), "p25_mm": float(p["zone_p25_mm"]),
                "median_mm": float(p["zone_median_mm"]), "p75_mm": float(p["zone_p75_mm"]),
                "p90_mm": float(p["zone_p90_mm"]), "n_years": int(p["zone_n_obs"]),
            },
            {
                "month": int(p["month"]), "day": int(p["day"]),
                "scope": "project_area",
                "normal_mean_mm": float(p["project_mean_mm"]),
                "normal_std_mm": float(p["project_std_mm"]),
                "p10_mm": float(p["project_p10_mm"]), "p25_mm": float(p["project_p25_mm"]),
                "median_mm": float(p["project_median_mm"]), "p75_mm": float(p["project_p75_mm"]),
                "p90_mm": float(p["project_p90_mm"]), "n_years": int(p["project_n_obs"]),
            },
        ])

    if len(rows) < 730:
        raise RuntimeError(f"Daily climatology incomplete: only {len(rows)} records returned; expected 732 including Feb 29.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    import csv
    fields = list(rows[0].keys())
    with OUTPUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    META.write_text(json.dumps({
        "source": COLLECTION,
        "baseline_period": "1991-2020",
        "calendar_key": "month-day",
        "scopes": ["carbon_project_zone", "project_area"],
        "records": len(rows),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }, indent=2), encoding="utf-8")
    print(f"Wrote {len(rows)} daily climatology records to {OUTPUT}")


if __name__ == "__main__":
    main()
