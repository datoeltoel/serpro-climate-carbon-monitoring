"""Build an actual spatial vegetation-status layer from Sentinel-2 SR Harmonized.

The output is a compact GeoJSON grid covering the SERPRO project area. Each cell
contains recent composite NDVI, NDMI and a conservative combined stress class.
This is intentionally a screening layer, not a carbon-accounting output.
"""
from __future__ import annotations

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
OUTPUT = Path("data/processed/climate/vegetation/vegetation_spatial_latest.geojson")
S2 = "COPERNICUS/S2_SR_HARMONIZED"
LOOKBACK_DAYS = 30
MAX_CLOUDY_PIXEL_PERCENTAGE = 40
GRID_SCALE_M = 2000

# SERPRO is in Seruyan, Central Kalimantan, within WGS 84 / UTM zone 49S.
# EPSG:32749 = WGS 84 / UTM zone 49S (projected CRS for spatial analysis).
# GeoJSON is exported in EPSG:4326 because Leaflet/Folium expects WGS84
# longitude/latitude coordinates.
ANALYSIS_CRS = "EPSG:32749"
OUTPUT_CRS = "EPSG:4326"


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
        raise RuntimeError("No project-area polygons found.")
    return ee.Geometry.MultiPolygon(polygons) if len(polygons) > 1 else polygons[0]


def mask_s2(img: ee.Image) -> ee.Image:
    scl = img.select("SCL")
    valid = scl.neq(0).And(scl.neq(1)).And(scl.neq(3)).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10)).And(scl.neq(11))
    return img.updateMask(valid)


def add_indices(img: ee.Image) -> ee.Image:
    ndvi = img.normalizedDifference(["B8", "B4"]).rename("NDVI")
    ndmi = img.normalizedDifference(["B8", "B11"]).rename("NDMI")
    return img.addBands([ndvi, ndmi])


def main() -> None:
    authenticate_ee()
    region = project_area_geometry()
    end = date.today() + timedelta(days=1)
    start = end - timedelta(days=LOOKBACK_DAYS)
    collection = (
        ee.ImageCollection(S2)
        .filterBounds(region)
        .filterDate(start.isoformat(), end.isoformat())
        .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", MAX_CLOUDY_PIXEL_PERCENTAGE))
        .map(mask_s2)
        .map(add_indices)
    )
    count = int(collection.size().getInfo())
    if count == 0:
        raise RuntimeError("No valid Sentinel-2 scenes found for the latest 30 days.")

    composite = collection.median().select(["NDVI", "NDMI"])
    # Spatial analysis/grid uses WGS 84 / UTM 49S (EPSG:32749),
    # appropriate for the SERPRO project area in Seruyan.
    grid = region.coveringGrid(ee.Projection(ANALYSIS_CRS).atScale(GRID_SCALE_M)).filterBounds(region)
    result = composite.reduceRegions(
        collection=grid,
        reducer=ee.Reducer.mean(),
        scale=20,
        tileScale=4,
    )

    # Leaflet/Folium expects GeoJSON in WGS84 longitude/latitude.
    # Transform only the exported geometry from UTM 49S to EPSG:4326.
    result = result.map(
        lambda feature: feature.setGeometry(feature.geometry().transform(OUTPUT_CRS))
    )

    features = result.getInfo().get("features", [])
    output_features = []
    for feature in features:
        props = feature.get("properties", {})
        ndvi = props.get("NDVI")
        ndmi = props.get("NDMI")
        if ndvi is None and ndmi is None:
            continue
        ndvi = float(ndvi) if ndvi is not None else None
        ndmi = float(ndmi) if ndmi is not None else None
        if ndvi is not None and ndmi is not None and ndvi <= 0.5 and ndmi <= 0.2:
            stress = "HIGH"
        elif (ndvi is not None and ndvi <= 0.5) or (ndmi is not None and ndmi <= 0.2):
            stress = "MODERATE"
        elif (ndvi is not None and ndvi < 0.7) or (ndmi is not None and ndmi < 0.4):
            stress = "LOW"
        else:
            stress = "STABLE"
        output_features.append({
            "type": "Feature",
            "geometry": feature.get("geometry"),
            "properties": {
                "ndvi": ndvi,
                "ndmi": ndmi,
                "stress": stress,
                "composite_start": start.isoformat(),
                "composite_end": (end - timedelta(days=1)).isoformat(),
                "period_days": LOOKBACK_DAYS,
                "scene_count": count,
                "resolution_m": GRID_SCALE_M,
                "composite_method": "30-day median",
                "analysis_crs": ANALYSIS_CRS,
                "output_crs": OUTPUT_CRS,
                "source": S2,
                "updated_utc": datetime.now(timezone.utc).isoformat(),
            },
        })

    if not output_features:
        raise RuntimeError("Sentinel-2 scenes were found, but no spatial vegetation cells were produced.")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps({"type": "FeatureCollection", "features": output_features}, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Wrote {len(output_features)} spatial vegetation cells: analysis={ANALYSIS_CRS}, output={OUTPUT_CRS}")


if __name__ == "__main__":
    main()
