"""Update recent SERPRO fire detections from NASA LANCE VIIRS in Earth Engine.

Sources:
- NASA/LANCE/SNPP_VIIRS/C2 (VIIRS 375 m)
- NASA/LANCE/NOAA20_VIIRS/C2 (VIIRS 375 m)

The VIIRS confidence class is native: 0=low, 1=nominal, 2=high.
For SERPRO UI these are presented as Low / Moderate / High.
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
LOOKBACK_DAYS = 30
SCALE = 375
COLLECTIONS = {
    "VIIRS-SNPP": "NASA/LANCE/SNPP_VIIRS/C2",
    "VIIRS-NOAA20": "NASA/LANCE/NOAA20_VIIRS/C2",
}


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
    print(f"Earth Engine initialized with project: {cloud_project}")
    print(f"Earth Engine service account: {info.get('client_email')}")


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


def sample_image(image: ee.Image, geometry: ee.Geometry, scope_name: str, source: str, date_str: str):
    bands = image.select(["Bright_ti4", "Bright_ti5", "confidence"])
    samples = bands.sample(
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
        confidence = props.get("confidence")
        if confidence is None:
            continue
        rows.append({
            "date": date_str,
            "scope": scope_name,
            "longitude": float(coords[0]),
            "latitude": float(coords[1]),
            "brightness_ti4_k": float(props["Bright_ti4"]) if props.get("Bright_ti4") is not None else None,
            "brightness_ti5_k": float(props["Bright_ti5"]) if props.get("Bright_ti5") is not None else None,
            "confidence": int(confidence),
            "source": source,
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

    rows = []
    total_images = 0
    for source_name, collection_id in COLLECTIONS.items():
        collection = ee.ImageCollection(collection_id).filterDate(start.isoformat(), end.isoformat()).filterBounds(region)
        image_info = collection.sort("system:time_start").toList(collection.size()).getInfo()
        images = collection.sort("system:time_start").toList(collection.size())
        total_images += len(image_info)
        for idx, meta in enumerate(image_info):
            image = ee.Image(images.get(idx))
            ts = meta.get("properties", {}).get("system:time_start")
            if ts is None:
                continue
            date_str = ee.Date(ts).format("YYYY-MM-dd").getInfo()
            for scope_name, geometry in scopes.items():
                rows.extend(sample_image(image, geometry, scope_name, source_name, date_str))

    # De-duplicate repeated detections from overlapping satellite products at identical coordinates/date/scope.
    dedup = {}
    for row in rows:
        key = (
            row["date"], row["scope"],
            round(row["latitude"], 5), round(row["longitude"], 5),
        )
        current = dedup.get(key)
        if current is None or row["confidence"] > current["confidence"]:
            dedup[key] = row
    rows = list(dedup.values())
    rows.sort(key=lambda r: (r["date"], r["scope"], -r["confidence"], r["latitude"], r["longitude"]))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "date", "scope", "longitude", "latitude", "brightness_ti4_k",
        "brightness_ti5_k", "confidence", "source", "resolution_m",
        "processing_time_utc",
    ]
    with OUTPUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"VIIRS collections processed: {', '.join(COLLECTIONS)}")
    print(f"VIIRS images processed: {total_images}")
    print(f"Wrote {len(rows)} hotspot records to {OUTPUT}")


if __name__ == "__main__":
    main()
