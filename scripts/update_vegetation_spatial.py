"""Build year-to-date Sentinel-2 spatial vegetation condition for SERPRO Project Area."""
from __future__ import annotations

import gzip
import json
import os
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import ee
from google.oauth2 import service_account

PROJECT_AREA_SOURCE = Path("data/static/project_boundary.kml.gz")
OUTPUT = Path("data/processed/climate/vegetation/vegetation_spatial_latest.geojson")
S2 = "COPERNICUS/S2_SR_HARMONIZED"
MAX_CLOUDY_PIXEL_PERCENTAGE = 40
ANALYSIS_SCALE_M = 10
DISPLAY_GRID_M = 100
COVERAGE_SCALE_M = 100
ANALYSIS_CRS = "EPSG:32749"
OUTPUT_CRS = "EPSG:4326"
TRANSFORM_ERROR_MARGIN_M = 1
INTERPOLATION_RADIUS_M = 150
INTERPOLATION_ITERATIONS = 1
KML_NS = {"kml": "http://www.opengis.net/kml/2.2"}


def authenticate_ee() -> None:
    key_json = os.environ.get("EE_SERVICE_ACCOUNT_JSON")
    cloud_project = os.environ.get("EE_PROJECT_ID")
    if not key_json or not cloud_project:
        raise RuntimeError("Set EE_SERVICE_ACCOUNT_JSON and EE_PROJECT_ID GitHub secrets.")
    info = json.loads(key_json)
    credentials = service_account.Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/cloud-platform"])
    ee.Initialize(credentials=credentials, project=cloud_project)


def project_area_geometry() -> ee.Geometry:
    if not PROJECT_AREA_SOURCE.exists():
        raise RuntimeError(f"Project Area file not found: {PROJECT_AREA_SOURCE}")
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
    return (ee.ImageCollection(S2).filterBounds(region).filterDate(start.isoformat(), end.isoformat()).filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", MAX_CLOUDY_PIXEL_PERCENTAGE)).map(mask_s2).map(add_indices))


def collection_stats(collection: ee.ImageCollection) -> tuple[int, float]:
    count = int(collection.size().getInfo())
    if count == 0:
        return 0, 0.0
    cloud = collection.aggregate_mean("CLOUDY_PIXEL_PERCENTAGE").getInfo()
    return count, float(cloud or 0.0)


def mask_percentage(mask: ee.Image, region: ee.Geometry) -> float:
    stats = mask.rename("coverage").reduceRegion(reducer=ee.Reducer.mean(), geometry=region.simplify(COVERAGE_SCALE_M), scale=COVERAGE_SCALE_M, maxPixels=1e8, tileScale=16, bestEffort=True).getInfo()
    return float(stats.get("coverage") or 0.0) * 100.0


def fetch_all_features(collection: ee.FeatureCollection, page_size: int = 1000) -> list[dict]:
    """Fetch the complete FeatureCollection in bounded pages.

    A direct FeatureCollection.getInfo() is unsafe for a 100 m grid over ~150,000 ha:
    the response can be too large and leave the exported GeoJSON spatially incomplete.
    Earth Engine's computeFeatures API paginates the table server-side and retrieves
    all pages automatically.
    """
    result = ee.data.computeFeatures({
        "expression": collection,
        "pageSize": page_size,
        "fileFormat": "GEOPANDAS_GEODATAFRAME",
    })
    if hasattr(result, "to_json"):
        geojson = json.loads(result.to_json())
        return geojson.get("features", [])
    if isinstance(result, dict) and "features" in result:
        return result["features"]
    raise RuntimeError("Earth Engine returned an unexpected computeFeatures result.")


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

    # Build a genuinely complete gap-fill surface. The old approach applied focal_mean
    # directly to the masked composite, so pixels outside the original footprint stayed
    # masked. Here the regional mean is first used as a safe seed, then the local mean is
    # calculated from that complete surface and only applied to originally missing pixels.
    regional_mean = composite.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=region.simplify(COVERAGE_SCALE_M),
        scale=COVERAGE_SCALE_M,
        maxPixels=1e8,
        tileScale=16,
        bestEffort=True,
    )
    regional_ndvi = ee.Number(ee.Algorithms.If(regional_mean.contains("NDVI"), regional_mean.get("NDVI"), 0.5))
    regional_ndmi = ee.Number(ee.Algorithms.If(regional_mean.contains("NDMI"), regional_mean.get("NDMI"), 0.2))
    regional_fill = ee.Image.constant([regional_ndvi, regional_ndmi]).rename(["NDVI", "NDMI"])

    seeded = composite.unmask(regional_fill, sameFootprint=False)
    spatial_candidate = seeded.focal_mean(
        radius=INTERPOLATION_RADIUS_M,
        kernelType="circle",
        units="meters",
        iterations=INTERPOLATION_ITERATIONS,
    ).select(["NDVI", "NDMI"])
    missing_mask = observed_mask.Not()
    filled = composite.unmask(spatial_candidate, sameFootprint=False).clip(region)

    final_valid = filled.mask().reduce(ee.Reducer.min()).rename("final_valid")
    spatial_pct = min(100.0, mask_percentage(missing_mask, region))
    total_coverage = mask_percentage(final_valid, region)

    grid = region.coveringGrid(ee.Projection(ANALYSIS_CRS).atScale(DISPLAY_GRID_M)).filterBounds(region)
    grid = grid.map(lambda feature: feature.intersection(region, TRANSFORM_ERROR_MARGIN_M))
    result = filled.reduceRegions(
        collection=grid,
        reducer=ee.Reducer.mean(),
        scale=ANALYSIS_SCALE_M,
        crs=ANALYSIS_CRS,
        tileScale=8,
    )
    result = result.map(lambda feature: feature.setGeometry(feature.geometry().transform(OUTPUT_CRS, TRANSFORM_ERROR_MARGIN_M)))

    # IMPORTANT: retrieve the complete grid, not FeatureCollection.getInfo().
    features = fetch_all_features(result, page_size=1000)
    output_features = []
    for feature in features:
        props = feature.get("properties", {})
        ndvi = props.get("NDVI")
        ndmi = props.get("NDMI")
        if ndvi is None or ndmi is None:
            continue
        ndvi = float(ndvi)
        ndmi = float(ndmi)
        if ndvi <= 0.5 and ndmi <= 0.2:
            stress = "HIGH"
        elif ndvi <= 0.5 or ndmi <= 0.2:
            stress = "MODERATE"
        elif ndvi < 0.7 or ndmi < 0.4:
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
                "analysis_year": year,
                "analysis_start": start.isoformat(),
                "analysis_end": (end - timedelta(days=1)).isoformat(),
                "scene_count": count,
                "mean_cloud_cover_pct": round(cloud, 2),
                "observed_pct": round(observed_pct, 2),
                "temporal_fallback_pct": 0.0,
                "spatial_interpolation_pct": round(spatial_pct, 2),
                "total_coverage_pct": round(total_coverage, 2),
                "no_data_pct": round(max(0.0, 100.0 - total_coverage), 2),
                "confidence": "HIGH" if observed_pct >= 85 else "MODERATE" if observed_pct >= 60 else "LOW",
                "analysis_scale_m": ANALYSIS_SCALE_M,
                "display_grid_m": DISPLAY_GRID_M,
                "interpolation_radius_m": INTERPOLATION_RADIUS_M,
                "composite_method": f"{year} year-to-date median + complete spatial gap fill",
                "analysis_crs": ANALYSIS_CRS,
                "output_crs": OUTPUT_CRS,
                "boundary": "SERPRO Project Area",
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
    print(
        f"Wrote {len(output_features)} complete YTD {year} Project Area cells; "
        f"analysis={ANALYSIS_SCALE_M}m; display={DISPLAY_GRID_M}m; scenes={count}; "
        f"observed={observed_pct:.2f}%; spatial_fill={spatial_pct:.2f}%; total={total_coverage:.2f}%"
    )


if __name__ == "__main__":
    main()
