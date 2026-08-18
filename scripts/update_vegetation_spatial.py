"""Build YTD Sentinel-2 vegetation analysis for SERPRO Project Area.

The analytical composite stays at native Sentinel-2 10 m. The dashboard map is
served as a compact 100 m PNG raster, while the spatial overview remains a
250 m GeoJSON layer for metadata/overview use. This avoids retrieving hundreds
of thousands of polygons from Earth Engine into the GitHub runner.
"""
from __future__ import annotations

import base64
import gzip
import json
import os
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import ee
import requests
from google.oauth2 import service_account

PROJECT_AREA_SOURCE = Path("data/static/project_boundary.kml.gz")
OUTPUT = Path("data/processed/climate/vegetation/vegetation_spatial_latest.geojson")
RASTER_OUTPUT = Path("data/processed/climate/vegetation/vegetation_spatial_raster.json")
S2 = "COPERNICUS/S2_SR_HARMONIZED"
MAX_CLOUDY_PIXEL_PERCENTAGE = 40
ANALYSIS_SCALE_M = 10
OVERVIEW_GRID_M = 250
WEB_DISPLAY_SCALE_M = 100
COVERAGE_SCALE_M = 250
ANALYSIS_CRS = "EPSG:32749"
OUTPUT_CRS = "EPSG:4326"
TRANSFORM_ERROR_MARGIN_M = 1
INTERPOLATION_RADIUS_M = 150
INTERPOLATION_ITERATIONS = 1
RETRIEVAL_PAGE_SIZE = 200
RETRIEVAL_MAX_FEATURES = 50000
RETRIEVAL_MAX_RETRIES = 5
THUMB_TIMEOUT_SECONDS = 180
KML_NS = {"kml": "http://www.opengis.net/kml/2.2"}


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
    with gzip.open(PROJECT_AREA_SOURCE, "rb") as f:
        root = ET.fromstring(f.read())
    polygons = []
    for ring in root.findall(".//kml:Placemark//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", KML_NS):
        coords = []
        for item in (ring.text or "").split():
            parts = item.split(",")
            if len(parts) >= 2:
                coords.append([float(parts[0]), float(parts[1])])
        if len(coords) >= 4:
            polygons.append([coords])
    if not polygons:
        raise RuntimeError("No polygon geometry found in Project Area KML.")
    return ee.Geometry.MultiPolygon(polygons)


def mask_s2(img: ee.Image) -> ee.Image:
    scl = img.select("SCL")
    valid = scl.neq(0).And(scl.neq(1)).And(scl.neq(3)).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10)).And(scl.neq(11))
    return img.updateMask(valid)


def add_indices(img: ee.Image) -> ee.Image:
    return img.addBands([
        img.normalizedDifference(["B8", "B4"]).rename("NDVI"),
        img.normalizedDifference(["B8", "B11"]).rename("NDMI"),
    ])


def build_collection(region: ee.Geometry, start: date, end: date) -> ee.ImageCollection:
    return (
        ee.ImageCollection(S2)
        .filterBounds(region)
        .filterDate(start.isoformat(), end.isoformat())
        .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", MAX_CLOUDY_PIXEL_PERCENTAGE))
        .map(mask_s2)
        .map(add_indices)
    )


def collection_stats(collection: ee.ImageCollection) -> tuple[int, float]:
    count = int(collection.size().getInfo())
    if count == 0:
        return 0, 0.0
    cloud = collection.aggregate_mean("CLOUDY_PIXEL_PERCENTAGE").getInfo()
    return count, float(cloud or 0.0)


def mask_percentage(mask: ee.Image, region: ee.Geometry) -> float:
    stats = mask.rename("coverage").reduceRegion(
        reducer=ee.Reducer.mean(), geometry=region.simplify(COVERAGE_SCALE_M),
        scale=COVERAGE_SCALE_M, maxPixels=1e8, tileScale=16, bestEffort=True,
    ).getInfo()
    return float(stats.get("coverage") or 0.0) * 100.0


def fetch_all_features(collection: ee.FeatureCollection) -> list[dict]:
    features: list[dict] = []
    offset = 0
    while offset < RETRIEVAL_MAX_FEATURES:
        page_size = min(RETRIEVAL_PAGE_SIZE, RETRIEVAL_MAX_FEATURES - offset)
        print(f"Retrieving overview cells {offset + 1}-{offset + page_size}")
        last_error: Exception | None = None
        for attempt in range(1, RETRIEVAL_MAX_RETRIES + 1):
            try:
                page = collection.toList(page_size, offset).getInfo() or []
                if not page:
                    return features
                features.extend(page)
                offset += len(page)
                print(f"Retrieved {len(page)} cells; total={len(features)}")
                if len(page) < page_size:
                    return features
                break
            except Exception as exc:
                last_error = exc
                print(f"Overview page offset={offset} failed (attempt {attempt}/{RETRIEVAL_MAX_RETRIES}): {exc}")
                if attempt < RETRIEVAL_MAX_RETRIES:
                    time.sleep(5 * attempt)
        else:
            raise RuntimeError(f"Earth Engine overview retrieval failed at offset {offset}.") from last_error
    raise RuntimeError(f"Spatial overview exceeded {RETRIEVAL_MAX_FEATURES} cells.")


def thumb_bytes(image: ee.Image, params: dict) -> bytes:
    url = image.getThumbURL(params)
    response = requests.get(url, timeout=THUMB_TIMEOUT_SECONDS)
    response.raise_for_status()
    if not response.content:
        raise RuntimeError("Earth Engine returned an empty vegetation raster.")
    return response.content


def pack_png(data: bytes) -> str:
    return base64.b64encode(gzip.compress(data, compresslevel=9)).decode("ascii")


def build_web_raster(filled: ee.Image, region: ee.Geometry, year: int, start: date, end: date, scene_count: int, cloud: float, observed_pct: float) -> None:
    bounds = region.bounds(TRANSFORM_ERROR_MARGIN_M).coordinates().getInfo()[0]
    lons = [float(p[0]) for p in bounds]
    lats = [float(p[1]) for p in bounds]
    map_bounds = [[min(lats), min(lons)], [max(lats), max(lons)]]
    common = {"region": region, "scale": WEB_DISPLAY_SCALE_M, "format": "png", "crs": OUTPUT_CRS}
    ndvi_img = filled.select("NDVI").visualize(
        min=0, max=1, palette=["#b91c1c", "#f59e0b", "#84cc16", "#15803d"]
    )
    ndmi_img = filled.select("NDMI").visualize(
        min=-0.2, max=0.6, palette=["#b91c1c", "#f59e0b", "#84cc16", "#15803d"]
    )
    stress_code = (
        ee.Image(0).where(filled.select("NDVI").lte(0.5).Or(filled.select("NDMI").lte(0.2)), 2)
        .where(filled.select("NDVI").lte(0.5).And(filled.select("NDMI").lte(0.2)), 3)
        .rename("stress")
    )
    stress_img = stress_code.visualize(
        min=0, max=3, palette=["#16a34a", "#eab308", "#f59e0b", "#dc2626"]
    )
    payload = {
        "schema_version": 1,
        "analysis_scale_m": ANALYSIS_SCALE_M,
        "web_display_scale_m": WEB_DISPLAY_SCALE_M,
        "overview_grid_m": OVERVIEW_GRID_M,
        "analysis_year": year,
        "analysis_start": start.isoformat(),
        "analysis_end": (end - timedelta(days=1)).isoformat(),
        "scene_count": scene_count,
        "mean_cloud_cover_pct": round(cloud, 2),
        "observed_pct": round(observed_pct, 2),
        "total_coverage_pct": 100.0,
        "bounds": map_bounds,
        "layers": {
            "ndvi": pack_png(thumb_bytes(ndvi_img, common)),
            "ndmi": pack_png(thumb_bytes(ndmi_img, common)),
            "stress": pack_png(thumb_bytes(stress_img, common)),
        },
        "encoding": "base64+gzip+png",
        "updated_utc": datetime.now(timezone.utc).isoformat(),
    }
    RASTER_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    RASTER_OUTPUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote 100 m raster web layers: NDVI, NDMI, stress; bounds={map_bounds}")


def main() -> None:
    authenticate_ee()
    region = project_area_geometry()
    year = date.today().year
    start = date(year, 1, 1)
    end = date.today() + timedelta(days=1)
    collection = build_collection(region, start, end)
    count, cloud = collection_stats(collection)
    if count == 0:
        raise RuntimeError(f"No Sentinel-2 scenes found for year-to-date {year}.")

    composite = collection.median().select(["NDVI", "NDMI"])
    observed_mask = composite.mask().reduce(ee.Reducer.min()).rename("observed_valid")
    observed_pct = mask_percentage(observed_mask, region)
    regional_mean = composite.reduceRegion(
        reducer=ee.Reducer.mean(), geometry=region.simplify(COVERAGE_SCALE_M),
        scale=COVERAGE_SCALE_M, maxPixels=1e8, tileScale=16, bestEffort=True,
    )
    regional_ndvi = ee.Number(ee.Algorithms.If(regional_mean.contains("NDVI"), regional_mean.get("NDVI"), 0.5))
    regional_ndmi = ee.Number(ee.Algorithms.If(regional_mean.contains("NDMI"), regional_mean.get("NDMI"), 0.2))
    regional_fill = ee.Image.constant([regional_ndvi, regional_ndmi]).rename(["NDVI", "NDMI"])
    seeded = composite.unmask(regional_fill, sameFootprint=False)
    spatial_candidate = seeded.focal_mean(
        radius=INTERPOLATION_RADIUS_M, kernelType="circle", units="meters", iterations=INTERPOLATION_ITERATIONS
    ).select(["NDVI", "NDMI"])
    missing_mask = observed_mask.Not()
    filled = composite.unmask(spatial_candidate, sameFootprint=False).unmask(regional_fill, sameFootprint=False).clip(region)
    spatial_pct = min(100.0, mask_percentage(missing_mask, region))

    # The dashboard spatial overview remains a 250 m GeoJSON. Its values are still
    # reduced from the native 10 m analytical surface.
    grid = region.coveringGrid(ee.Projection(ANALYSIS_CRS).atScale(OVERVIEW_GRID_M)).filterBounds(region)
    grid = grid.map(lambda feature: feature.intersection(region, TRANSFORM_ERROR_MARGIN_M))
    result = filled.reduceRegions(
        collection=grid, reducer=ee.Reducer.mean(), scale=ANALYSIS_SCALE_M,
        crs=ANALYSIS_CRS, tileScale=8,
    )
    result = result.map(lambda feature: feature.setGeometry(feature.geometry().transform(OUTPUT_CRS, TRANSFORM_ERROR_MARGIN_M)))
    features = fetch_all_features(result)
    output_features = []
    for feature in features:
        props = feature.get("properties", {})
        ndvi = float(props.get("NDVI") if props.get("NDVI") is not None else regional_ndvi.getInfo())
        ndmi = float(props.get("NDMI") if props.get("NDMI") is not None else regional_ndmi.getInfo())
        if ndvi <= 0.5 and ndmi <= 0.2:
            stress = "HIGH"
        elif ndvi <= 0.5 or ndmi <= 0.2:
            stress = "MODERATE"
        elif ndvi < 0.7 or ndmi < 0.4:
            stress = "LOW"
        else:
            stress = "STABLE"
        props_out = {
            "ndvi": ndvi, "ndmi": ndmi, "stress": stress,
            "NDVI": ndvi, "NDMI": ndmi, "STRESS": stress,
            "ndvi_ytd": ndvi, "ndmi_ytd": ndmi, "stress_condition": stress,
            "analysis_year": year, "analysis_start": start.isoformat(),
            "analysis_end": (end - timedelta(days=1)).isoformat(),
            "scene_count": count, "mean_cloud_cover_pct": round(cloud, 2),
            "observed_pct": round(observed_pct, 2), "temporal_fallback_pct": 0.0,
            "spatial_interpolation_pct": round(max(spatial_pct, 0.0), 2),
            "total_coverage_pct": 100.0, "web_display_coverage_pct": 100.0,
            "no_data_pct": 0.0, "confidence": "HIGH" if observed_pct >= 85 else "MODERATE" if observed_pct >= 60 else "LOW",
            "analysis_scale_m": ANALYSIS_SCALE_M, "display_grid_m": OVERVIEW_GRID_M,
            "web_display_scale_m": WEB_DISPLAY_SCALE_M,
            "interpolation_radius_m": INTERPOLATION_RADIUS_M,
            "composite_method": f"{year} year-to-date median + complete spatial gap fill",
            "analysis_crs": ANALYSIS_CRS, "output_crs": OUTPUT_CRS,
            "boundary": "SERPRO Project Area", "source": S2,
            "updated_utc": datetime.now(timezone.utc).isoformat(),
        }
        output_features.append({"type": "Feature", "geometry": feature.get("geometry"), "properties": props_out})
    if not output_features:
        raise RuntimeError("Sentinel-2 scenes were found, but no spatial overview cells were produced.")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({"type": "FeatureCollection", "features": output_features}, separators=(",", ":")), encoding="utf-8")
    build_web_raster(filled, region, year, start, end, count, cloud, observed_pct)
    print(f"Complete: analysis={ANALYSIS_SCALE_M}m; overview={OVERVIEW_GRID_M}m; web_raster={WEB_DISPLAY_SCALE_M}m; scenes={count}; observed={observed_pct:.2f}%")


if __name__ == "__main__":
    main()
