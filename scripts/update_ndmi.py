"""Build recent Sentinel-2 NDMI observations for SERPRO scopes.

Source: COPERNICUS/S2_SR_HARMONIZED + COPERNICUS/S2_CLOUD_PROBABILITY.
Outputs scene-level zonal NDMI means for the latest 90 days.
"""
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
OUTPUT = Path("data/processed/climate/vegetation/ndmi_daily.csv")
S2 = "COPERNICUS/S2_SR_HARMONIZED"
S2_CLOUD = "COPERNICUS/S2_CLOUD_PROBABILITY"
LOOKBACK_DAYS = 90
MAX_CLOUD_PROBABILITY = 40
SCALE = 20


def authenticate_ee() -> None:
    key_json = os.environ.get("EE_SERVICE_ACCOUNT_JSON")
    cloud_project = os.environ.get("EE_PROJECT_ID")
    if not key_json or not cloud_project:
        raise RuntimeError("Set EE_SERVICE_ACCOUNT_JSON and EE_PROJECT_ID GitHub secrets.")
    info = json.loads(key_json)
    private_key = info["private_key"].strip()
    if "..." in private_key or not private_key.startswith("-----BEGIN PRIVATE KEY-----") or not private_key.endswith("-----END PRIVATE KEY-----"):
        raise RuntimeError("Invalid EE service-account private key.")
    credentials = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    ee.Initialize(credentials=credentials, project=cloud_project)
    print(f"Earth Engine initialized with project: {cloud_project}")
    print(f"Earth Engine service account: {info['client_email']}")


def project_area_geometry() -> ee.Geometry:
    with gzip.open(PROJECT_AREA_KML, "rb") as fh:
        root = ET.fromstring(fh.read())
    polygons = []
    for node in root.findall(".//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", KML_NS):
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


def add_cloud_mask(img):
    cloud_obj = img.get("cloud_mask")
    return ee.Image(img).updateMask(ee.Image(cloud_obj).select("probability").lt(MAX_CLOUD_PROBABILITY))


def add_ndmi(img):
    img = ee.Image(img)
    return img.addBands(img.normalizedDifference(["B8", "B11"]).rename("NDMI"))


def build_collection(region: ee.Geometry, start: str, end: str):
    criteria = ee.Filter.And(ee.Filter.bounds(region), ee.Filter.date(start, end))
    sr = ee.ImageCollection(S2).filter(criteria).filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 80))
    clouds = ee.ImageCollection(S2_CLOUD).filter(criteria)
    joined = ee.Join.saveFirst("cloud_mask").apply(
        primary=sr,
        secondary=clouds,
        condition=ee.Filter.equals(leftField="system:index", rightField="system:index"),
    )
    # Keep only SR scenes for which a matching cloud-probability image exists.
    joined = ee.ImageCollection(joined).filter(ee.Filter.notNull(["cloud_mask"]))
    return joined.map(add_cloud_mask).map(add_ndmi)


def zonal_mean(img, geometry):
    value = img.select("NDMI").reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geometry,
        scale=SCALE,
        maxPixels=2_000_000,
        bestEffort=True,
    ).get("NDMI")
    return value


def main() -> None:
    authenticate_ee()
    scopes = {
        "carbon_project_zone": project_zone_geometry(),
        "project_area": project_area_geometry(),
    }
    end = date.today() + timedelta(days=1)
    start = end - timedelta(days=LOOKBACK_DAYS)
    region = scopes["carbon_project_zone"].union(scopes["project_area"], maxError=1)
    collection = build_collection(region, start.isoformat(), end.isoformat()).sort("system:time_start")

    # Pull stable scene identifiers and timestamps in one server-side evaluation.
    scene_ids = collection.aggregate_array("system:index").getInfo()
    scene_times = collection.aggregate_array("system:time_start").getInfo()
    scene_cloud = collection.aggregate_array("CLOUDY_PIXEL_PERCENTAGE").getInfo()

    rows = []
    for idx, scene_id in enumerate(scene_ids):
        img = collection.filter(ee.Filter.eq("system:index", scene_id)).first()
        if img is None:
            continue
        scene_ms = scene_times[idx] if idx < len(scene_times) else None
        scene_date = datetime.fromtimestamp(scene_ms / 1000, tz=timezone.utc).date().isoformat() if scene_ms else None
        cloudy_pct = scene_cloud[idx] if idx < len(scene_cloud) else None
        if scene_date is None:
            continue

        for scope_name, geometry in scopes.items():
            value = zonal_mean(img, geometry)
            value = value.getInfo() if value is not None else None
            if value is None:
                continue
            rows.append({
                "date": scene_date,
                "scope": scope_name,
                "ndmi": float(value),
                "cloudy_pixel_percentage": float(cloudy_pct) if cloudy_pct is not None else None,
                "scene_id": scene_id,
                "source": S2,
                "processing_time_utc": datetime.now(timezone.utc).isoformat(),
            })

    if not rows:
        raise RuntimeError("No valid Sentinel-2 NDMI observations were found for the latest 90 days.")

    rows.sort(key=lambda r: (r["date"], r["scope"]))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} NDMI records to {OUTPUT}")


if __name__ == "__main__":
    main()
