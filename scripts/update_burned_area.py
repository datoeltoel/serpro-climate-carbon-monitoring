"""Build annual burned-area history for SERPRO monitoring scopes.

Source: MODIS/061/MCD64A1, monthly 500 m burned-area product.
Uses complete calendar years 2016-2025 so the 10-year trend is not mixed
with the incomplete current year.
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
OUTPUT = Path("data/processed/climate/fire/burned_area_annual_2016_2025.csv")
META = Path("data/processed/climate/fire/burned_area_metadata.json")
COLLECTION = "MODIS/061/MCD64A1"
START_YEAR = 2016
END_YEAR = 2025
SCALE = 500


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


def annual_burned_area(image_collection: ee.ImageCollection, geometry: ee.Geometry) -> ee.Number:
    # BurnDate > 0 identifies burned pixels. QA bit 0 = land and bit 1 = valid data.
    def month_area(img: ee.Image) -> ee.Image:
        burn = img.select("BurnDate")
        qa = img.select("QA")
        land = qa.bitwiseAnd(1).eq(1)
        valid = qa.rightShift(1).bitwiseAnd(1).eq(1)
        burned = burn.gt(0).And(land).And(valid)
        area_ha = ee.Image.pixelArea().divide(10000).updateMask(burned)
        return area_ha

    monthly = image_collection.map(month_area)
    annual = ee.ImageCollection(monthly).sum()
    result = annual.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=geometry,
        scale=SCALE,
        maxPixels=1e10,
        tileScale=4,
    ).get("BurnDate")
    return ee.Number(result).defaultValue(0)


def main() -> None:
    authenticate_ee()
    scopes = {
        "carbon_project_zone": project_zone_geometry(),
        "project_area": project_area_geometry(),
    }

    rows = []
    for year in range(START_YEAR, END_YEAR + 1):
        start = f"{year}-01-01"
        end = f"{year + 1}-01-01"
        collection = ee.ImageCollection(COLLECTION).filterDate(start, end)
        for scope, geometry in scopes.items():
            area_ha = annual_burned_area(collection, geometry).getInfo()
            rows.append({
                "year": year,
                "scope": scope,
                "burned_area_ha": float(area_ha or 0.0),
                "processing_time_utc": datetime.now(timezone.utc).isoformat(),
                "source": COLLECTION,
                "resolution_m": SCALE,
            })
            print(f"{year} {scope}: {float(area_ha or 0.0):,.2f} ha")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fields = ["year", "scope", "burned_area_ha", "processing_time_utc", "source", "resolution_m"]
    with OUTPUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    META.write_text(json.dumps({
        "source": COLLECTION,
        "period": f"{START_YEAR}-{END_YEAR}",
        "cadence": "monthly source aggregated to annual burned area",
        "resolution_m": SCALE,
        "method": "sum pixel area where BurnDate > 0 and QA land + valid bits are set",
        "note": "Ten complete calendar years; 2026 is excluded because the current year is incomplete.",
    }, indent=2), encoding="utf-8")
    print(f"Wrote {len(rows)} annual burned-area records to {OUTPUT}")


if __name__ == "__main__":
    main()
