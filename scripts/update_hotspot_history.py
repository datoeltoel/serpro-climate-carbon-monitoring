"""Build annual historical active-fire detection trend for SERPRO.

Source: MODIS Terra MOD14A1 Collection 6.1 (1 km daily fire mask).
Period: 2017-2025, using complete calendar years for comparable trend analysis.
The metric is annual fire-pixel detections, not unique fire events or burned area.
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import ee
from google.oauth2 import service_account

KML_NS = {"kml": "http://www.opengis.net/kml/2.2"}
PROJECT_AREA_KML = Path("data/static/project_boundary.kml.gz")
PROJECT_ZONE_GEOJSON = Path("data/static/boundaries/serpro_carbon_project_zone_web.geojson")
OUTPUT = Path("data/processed/climate/fire/hotspot_history_2017_2025.csv")
META = Path("data/processed/climate/fire/hotspot_history_metadata.json")
COLLECTION = "MODIS/061/MOD14A1"
START_YEAR = 2017
END_YEAR = 2025
SCALE = 1000


def authenticate_ee() -> None:
    key_json = os.environ.get("EE_SERVICE_ACCOUNT_JSON")
    cloud_project = os.environ.get("EE_PROJECT_ID")
    if not key_json or not cloud_project:
        raise RuntimeError("Set EE_SERVICE_ACCOUNT_JSON and EE_PROJECT_ID GitHub secrets.")
    info = json.loads(key_json)
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
    geoms = [ee.Geometry(f["geometry"]) for f in features if f.get("geometry")]
    geom = geoms[0]
    for other in geoms[1:]:
        geom = geom.union(other, maxError=1)
    return geom


def annual_fire_pixels(collection: ee.ImageCollection, geometry: ee.Geometry) -> ee.Dictionary:
    def fire_pixels(img: ee.Image) -> ee.Image:
        mask = img.select("FireMask").gte(7)
        return ee.Image.constant(1).rename("fire_pixel").updateMask(mask)

    fire = collection.map(fire_pixels).sum().rename("fire_pixel")
    result = fire.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=geometry,
        scale=SCALE,
        maxPixels=1e10,
        tileScale=4,
    )
    return ee.Dictionary({"fire_pixel_detections": result.get("fire_pixel")})


def main() -> None:
    authenticate_ee()
    scopes = {
        "carbon_project_zone": project_zone_geometry(),
        "project_area": project_area_geometry(),
    }

    rows = []
    for year in range(START_YEAR, END_YEAR + 1):
        collection = ee.ImageCollection(COLLECTION).filterDate(
            f"{year}-01-01", f"{year + 1}-01-01"
        )
        for scope, geometry in scopes.items():
            value = annual_fire_pixels(collection, geometry).get("fire_pixel_detections").getInfo()
            detections = float(value or 0.0)
            rows.append({
                "year": year,
                "scope": scope,
                "hotspot_detections": int(round(detections)),
                "source": COLLECTION,
                "resolution_m": SCALE,
                "metric": "annual fire-pixel detections",
                "processing_time_utc": datetime.now(timezone.utc).isoformat(),
            })
            print(f"{year} {scope}: {int(round(detections)):,} fire-pixel detections")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fields = ["year", "scope", "hotspot_detections", "source", "resolution_m", "metric", "processing_time_utc"]
    with OUTPUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    META.write_text(json.dumps({
        "source": COLLECTION,
        "period": f"{START_YEAR}-{END_YEAR}",
        "resolution_m": SCALE,
        "metric": "annual fire-pixel detections from FireMask classes 7-9",
        "classes": {
            "7": "Fire, low confidence",
            "8": "Fire, nominal confidence",
            "9": "Fire, high confidence",
        },
        "note": "Historical trend is a detection-count indicator and is not equivalent to unique fire events or burned area. Current operational map remains VIIRS 375 m NRT.",
    }, indent=2), encoding="utf-8")
    print(f"Wrote {len(rows)} historical hotspot records to {OUTPUT}")


if __name__ == "__main__":
    main()
