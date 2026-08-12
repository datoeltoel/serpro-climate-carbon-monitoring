"""Update recent SERPRO active-fire detections from NASA FIRMS in Earth Engine.

Source: FIRMS (MODIS LANCE near-real-time active fire raster), daily cadence.
Outputs fire hotspot points inside the official Carbon Project Zone and Project Area.
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
OUTPUT = Path("data/processed/climate/fire/fire_hotspots.csv")
FIRMS = "FIRMS"
LOOKBACK_DAYS = 30
SCALE = 1000


def authenticate_ee() -> None:
    key_json = os.environ.get("EE_SERVICE_ACCOUNT_JSON")
    cloud_project = os.environ.get("EE_PROJECT_ID")
    if not key_json or not cloud_project:
        raise RuntimeError("Set EE_SERVICE_ACCOUNT_JSON and EE_PROJECT_ID GitHub secrets.")
    info = json.loads(key_json)
    private_key = info["private_key"].strip()
    if "..." in private_key or not private_key.startswith("-----BEGIN PRIVATE KEY-----"):
        raise RuntimeError("Invalid EE service-account private key.")
    credentials = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    ee.Initialize(credentials=credentials, project=cloud_project)


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


def sample_image(image: ee.Image, geometry: ee.Geometry, scope_name: str, date_str: str):
    # FIRMS stores active fires in rasterized form. T21 is masked except where active fire is detected.
    fire = image.select(["T21", "confidence"])
    samples = fire.sample(
        region=geometry,
        scale=SCALE,
        geometries=True,
        dropNulls=True,
        tileScale=4,
    ).getInfo()
    rows = []
    for feature in samples.get("features", []):
        props = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates", [None, None])
        if coords[0] is None or coords[1] is None:
            continue
        rows.append({
            "date": date_str,
            "scope": scope_name,
            "longitude": float(coords[0]),
            "latitude": float(coords[1]),
            "brightness_temperature_k": float(props["T21"]) if props.get("T21") is not None else None,
            "confidence": float(props["confidence"]) if props.get("confidence") is not None else None,
            "source": FIRMS,
            "resolution_m": SCALE,
            "processing_time_utc": datetime.now(timezone.utc).isoformat(),
        })
    return rows


def main() -> None:
    authenticate_ee()
    scopes = {
        "carbon_project_zone": project_zone_geometry(),
        "project_area": project_area_geometry(),
    }
    end = date.today() + timedelta(days=1)
    start = end - timedelta(days=LOOKBACK_DAYS)
    region = scopes["carbon_project_zone"].union(scopes["project_area"], maxError=1)

    collection = ee.ImageCollection(FIRMS).filterDate(start.isoformat(), end.isoformat()).filterBounds(region)
    image_info = collection.sort("system:time_start").toList(collection.size()).getInfo()
    images = collection.sort("system:time_start").toList(collection.size())

    rows = []
    for idx, meta in enumerate(image_info):
        image = ee.Image(images.get(idx))
        date_str = ee.Date(meta.get("properties", {}).get("system:time_start")).format("YYYY-MM-dd").getInfo()
        for scope_name, geometry in scopes.items():
            rows.extend(sample_image(image, geometry, scope_name, date_str))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "date", "scope", "longitude", "latitude", "brightness_temperature_k",
        "confidence", "source", "resolution_m", "processing_time_utc",
    ]
    with OUTPUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"FIRMS images processed: {len(image_info)}")
    print(f"Wrote {len(rows)} hotspot records to {OUTPUT}")


if __name__ == "__main__":
    main()
