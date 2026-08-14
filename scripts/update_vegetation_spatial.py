"""Build spatial vegetation status and quality metadata from Sentinel-2 SR Harmonized.

Sentinel-2 indices are calculated at native 10 m in WGS 84 / UTM 49S. The
GeoJSON remains a lightweight web-display layer; its display cells summarize
10 m observations. Quality metadata records valid Sentinel-2 coverage,
cloudiness, temporal fallback and spatial interpolation availability.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import ee
from google.oauth2 import service_account

ZONE_GEOJSON = Path("data/static/boundaries/serpro_carbon_project_zone_web.geojson")
OUTPUT = Path("data/processed/climate/vegetation/vegetation_spatial_latest.geojson")
S2 = "COPERNICUS/S2_SR_HARMONIZED"
DEFAULT_LOOKBACK_DAYS = 30
FALLBACK_WINDOWS = (30, 60, 90, 180, 365)
MAX_CLOUDY_PIXEL_PERCENTAGE = 40
ANALYSIS_SCALE_M = 10
DISPLAY_GRID_M = 100
ANALYSIS_CRS = "EPSG:32749"  # WGS 84 / UTM zone 49S
OUTPUT_CRS = "EPSG:4326"     # GeoJSON / Leaflet display CRS
TRANSFORM_ERROR_MARGIN_M = 1
MIN_COVERAGE_PCT = 90.0


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


def carbon_project_zone_geometry() -> ee.Geometry:
    if not ZONE_GEOJSON.exists():
        raise RuntimeError(f"Carbon Project Zone file not found: {ZONE_GEOJSON}")
    data = json.loads(ZONE_GEOJSON.read_text(encoding="utf-8"))
    if data.get("type") == "Feature":
        geometry = data.get("geometry")
    elif data.get("type") == "FeatureCollection":
        geoms = [f.get("geometry") for f in data.get("features", []) if f.get("geometry")]
        if not geoms:
            raise RuntimeError("No geometry found in Carbon Project Zone GeoJSON.")
        geometry = geoms[0] if len(geoms) == 1 else {"type": "GeometryCollection", "geometries": geoms}
    else:
        geometry = data
    return ee.Geometry(geometry)


def mask_s2(img: ee.Image) -> ee.Image:
    scl = img.select("SCL")
    valid = (
        scl.neq(0).And(scl.neq(1)).And(scl.neq(3))
        .And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10)).And(scl.neq(11))
    )
    return img.updateMask(valid)


def add_indices(img: ee.Image) -> ee.Image:
    ndvi = img.normalizedDifference(["B8", "B4"]).rename("NDVI")
    ndmi = img.normalizedDifference(["B8", "B11"]).rename("NDMI")
    return img.addBands([ndvi, ndmi])


def build_collection(region: ee.Geometry, start: date, end: date) -> ee.ImageCollection:
    return (
        ee.ImageCollection(S2)
        .filterBounds(region)
        .filterDate(start.isoformat(), end.isoformat())
        .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", MAX_CLOUDY_PIXEL_PERCENTAGE))
        .map(mask_s2).map(add_indices)
    )


def requested_period_days() -> int:
    raw = os.environ.get("SPATIAL_PERIOD_DAYS", str(DEFAULT_LOOKBACK_DAYS))
    try:
        value = int(raw)
    except ValueError:
        value = DEFAULT_LOOKBACK_DAYS
    return value if value in FALLBACK_WINDOWS else DEFAULT_LOOKBACK_DAYS


def collection_stats(collection: ee.ImageCollection, region: ee.Geometry) -> tuple[int, float]:
    count = int(collection.size().getInfo())
    if count == 0:
        return 0, 0.0
    # Mean scene-level CLOUDY_PIXEL_PERCENTAGE is a quality indicator only;
    # pixel-level validity is calculated separately from the composite mask.
    cloud = collection.aggregate_mean("CLOUDY_PIXEL_PERCENTAGE").getInfo()
    return count, float(cloud or 0.0)


def coverage_stats(composite: ee.Image, region: ee.Geometry) -> tuple[float, float]:
    valid = composite.mask().reduce(ee.Reducer.min()).rename("valid")
    stats = valid.reduceRegion(
        reducer=ee.Reducer.mean(), geometry=region, scale=ANALYSIS_SCALE_M,
        maxPixels=1e9, tileScale=8, bestEffort=True,
    ).getInfo()
    observed = float(stats.get("valid") or 0.0) * 100.0
    return observed, max(0.0, 100.0 - observed)


def main() -> None:
    authenticate_ee()
    region = carbon_project_zone_geometry()
    end = date.today() + timedelta(days=1)
    requested_days = requested_period_days()

    selected = None
    for lookback_days in FALLBACK_WINDOWS:
        if lookback_days < requested_days:
            continue
        start = end - timedelta(days=lookback_days)
        candidate = build_collection(region, start, end)
        count, cloud = collection_stats(candidate, region)
        if count == 0:
            continue
        composite = candidate.median().select(["NDVI", "NDMI"])
        observed, no_data = coverage_stats(composite, region)
        if observed >= MIN_COVERAGE_PCT or lookback_days == FALLBACK_WINDOWS[-1]:
            selected = (candidate, composite, start, lookback_days, count, cloud, observed, no_data)
            break

    if selected is None:
        raise RuntimeError("No Sentinel-2 scenes were found in the 30–365 day adaptive window.")

    collection, composite, start, selected_days, count, cloud, observed, no_data = selected
    temporal_fallback = 0.0 if selected_days == requested_days else max(0.0, 100.0 - observed)
    # Spatial interpolation is intentionally not fabricated here. It will be
    # populated only by a subsequent gap-filling stage that records its own mask.
    spatial_interpolation = 0.0
    total_coverage = min(100.0, observed + temporal_fallback + spatial_interpolation)

    grid = region.coveringGrid(ee.Projection(ANALYSIS_CRS).atScale(DISPLAY_GRID_M)).filterBounds(region)
    grid = grid.map(lambda feature: feature.intersection(region, TRANSFORM_ERROR_MARGIN_M))
    result = composite.reduceRegions(collection=grid, reducer=ee.Reducer.mean(), scale=ANALYSIS_SCALE_M, tileScale=8)
    result = result.map(lambda feature: feature.setGeometry(feature.geometry().transform(OUTPUT_CRS, TRANSFORM_ERROR_MARGIN_M)))

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
            "type": "Feature", "geometry": feature.get("geometry"),
            "properties": {
                "ndvi": ndvi, "ndmi": ndmi, "stress": stress,
                "composite_start": start.isoformat(),
                "composite_end": (end - timedelta(days=1)).isoformat(),
                "analysis_start": start.isoformat(), "analysis_end": (end - timedelta(days=1)).isoformat(),
                "period_days": selected_days, "requested_period_days": requested_days,
                "fallback_used": selected_days != requested_days, "scene_count": count,
                "mean_cloud_cover_pct": round(cloud, 2),
                "observed_pct": round(observed, 2),
                "temporal_fallback_pct": round(temporal_fallback, 2),
                "spatial_interpolation_pct": round(spatial_interpolation, 2),
                "total_coverage_pct": round(total_coverage, 2),
                "no_data_pct": round(no_data, 2),
                "confidence": "HIGH" if observed >= 85 else "MODERATE" if observed >= 60 else "LOW",
                "analysis_scale_m": ANALYSIS_SCALE_M, "display_grid_m": DISPLAY_GRID_M,
                "composite_method": f"{selected_days}-day median",
                "analysis_crs": ANALYSIS_CRS, "output_crs": OUTPUT_CRS,
                "boundary": "SERPRO Carbon Project Zone", "source": S2,
                "updated_utc": datetime.now(timezone.utc).isoformat(),
            },
        })

    if not output_features:
        raise RuntimeError("Sentinel-2 scenes were found, but no spatial vegetation cells were produced.")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({"type": "FeatureCollection", "features": output_features}, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {len(output_features)} web cells; analysis=10m, CRS={ANALYSIS_CRS}, period={selected_days}d, scenes={count}, cloud={cloud:.2f}%, observed={observed:.2f}%")


if __name__ == "__main__":
    main()
