"""Build recent Sentinel-2 NDMI observations for SERPRO scopes.

Uses Sentinel-2 SR Harmonized with scene-level cloud filtering and SCL
masking. Avoids fragile cross-collection joins so empty cloud matches cannot
produce null ee.Image objects.
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
LOOKBACK_DAYS = 90
MAX_CLOUDY_PIXEL_PERCENTAGE = 40
SCALE = 20


def authenticate_ee() -> None:
    key_json = os.environ.get("EE_SERVICE_ACCOUNT_JSON")
    cloud_project = os.environ.get("EE_PROJECT_ID")
    if not key_json or not cloud_project:
        raise RuntimeError("Set EE_SERVICE_ACCOUNT_JSON and EE_PROJECT_ID GitHub secrets.")

    info = json.loads(key_json)
    private_key = info["private_key"].strip()
    if (
        "..." in private_key
        or not private_key.startswith("-----BEGIN PRIVATE KEY-----")
        or not private_key.endswith("-----END PRIVATE KEY-----")
    ):
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


def mask_s2(img: ee.Image) -> ee.Image:
    # SCL classes to mask: saturated/defective (1), no-data (0), cloud shadow (3),
    # medium/high cloud (8, 9), cirrus (10), snow/ice (11).
    scl = img.select("SCL")
    valid = (
        scl.neq(0)
        .And(scl.neq(1))
        .And(scl.neq(3))
        .And(scl.neq(8))
        .And(scl.neq(9))
        .And(scl.neq(10))
        .And(scl.neq(11))
    )
    return img.updateMask(valid)


def add_ndmi(img: ee.Image) -> ee.Image:
    # NDMI = (NIR - SWIR1) / (NIR + SWIR1); Sentinel-2: B8 and B11.
    return img.addBands(img.normalizedDifference(["B8", "B11"]).rename("NDMI"))


def build_collection(region: ee.Geometry, start: str, end: str) -> ee.ImageCollection:
    return (
        ee.ImageCollection(S2)
        .filterBounds(region)
        .filterDate(start, end)
        .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", MAX_CLOUDY_PIXEL_PERCENTAGE))
        .map(mask_s2)
        .map(add_ndmi)
    )


def zonal_mean(img: ee.Image, geometry: ee.Geometry):
    return img.select("NDMI").reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geometry,
        scale=SCALE,
        maxPixels=2_000_000,
        bestEffort=True,
    ).get("NDMI")


def main() -> None:
    authenticate_ee()

    scopes = {
        "carbon_project_zone": project_zone_geometry(),
        "project_area": project_area_geometry(),
    }
    region = scopes["carbon_project_zone"].union(scopes["project_area"], maxError=1)

    end = date.today() + timedelta(days=1)
    start = end - timedelta(days=LOOKBACK_DAYS)
    collection = build_collection(region, start.isoformat(), end.isoformat()).sort("system:time_start")

    # Convert collection metadata to plain Python once; process each known scene
    # by its positional index rather than by a possibly missing system:index.
    scene_count = int(collection.size().getInfo())
    if scene_count == 0:
        raise RuntimeError("No Sentinel-2 scenes found for the latest 90 days after cloud filtering.")

    scene_dates = collection.aggregate_array("system:time_start").getInfo()
    cloud_pct = collection.aggregate_array("CLOUDY_PIXEL_PERCENTAGE").getInfo()

    rows = []
    for idx, timestamp_ms in enumerate(scene_dates):
        img = ee.Image(collection.toList(scene_count).get(idx))
        scene_date = datetime.fromtimestamp(float(timestamp_ms) / 1000.0, tz=timezone.utc).date().isoformat()
        cloudy = cloud_pct[idx] if idx < len(cloud_pct) else None

        for scope_name, geometry in scopes.items():
            value = zonal_mean(img, geometry)
            value = value.getInfo() if value is not None else None
            if value is None:
                continue
            rows.append(
                {
                    "date": scene_date,
                    "scope": scope_name,
                    "ndmi": float(value),
                    "cloudy_pixel_percentage": float(cloudy) if cloudy is not None else None,
                    "source": S2,
                    "processing_time_utc": datetime.now(timezone.utc).isoformat(),
                }
            )

    if not rows:
        raise RuntimeError("Sentinel-2 scenes were found, but no valid NDMI zonal observations were produced.")

    rows.sort(key=lambda r: (r["date"], r["scope"]))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} NDMI records to {OUTPUT}")
    print(f"Sentinel-2 scenes processed: {scene_count}")


if __name__ == "__main__":
    main()
