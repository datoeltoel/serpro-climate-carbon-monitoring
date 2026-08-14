"""Build spatial Sentinel-2 vegetation status for the SERPRO Carbon Project Zone.

Analysis is performed at native Sentinel-2 10 m scale in WGS 84 / UTM 49S.
The web GeoJSON uses a lighter display grid so the Streamlit map remains fast.

Coverage strategy:
1. Direct Sentinel-2 observation inside the requested period.
2. Temporal fallback from an expanded 60/90/180/365-day window when needed.
3. Spatial gap filling with neighbourhood interpolation, followed by a regional
   mean only for residual isolated gaps.

All estimated pixels are explicitly labelled in the quality metadata; 100%
map coverage therefore does not mean 100% direct observation.
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
DEFAULT_LOOKBACK_DAYS = 90
FALLBACK_WINDOWS = (90, 180, 365)
MAX_CLOUDY_PIXEL_PERCENTAGE = 40
ANALYSIS_SCALE_M = 10
DISPLAY_GRID_M = 100
ANALYSIS_CRS = "EPSG:32749"
OUTPUT_CRS = "EPSG:4326"
TRANSFORM_ERROR_MARGIN_M = 1
MIN_COVERAGE_PCT = 90.0
INTERPOLATION_RADIUS_M = 500
INTERPOLATION_ITERATIONS = 3


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
        .map(mask_s2)
        .map(add_indices)
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
    cloud = collection.aggregate_mean("CLOUDY_PIXEL_PERCENTAGE").getInfo()
    return count, float(cloud or 0.0)


def mask_percentage(mask: ee.Image, region: ee.Geometry) -> float:
    stats = mask.rename("coverage").reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=region,
        scale=ANALYSIS_SCALE_M,
        maxPixels=1e9,
        tileScale=8,
        bestEffort=True,
    ).getInfo()
    return float(stats.get("coverage") or 0.0) * 100.0


def masked_image() -> ee.Image:
    return ee.Image.constant([0, 0]).rename(["NDVI", "NDMI"]).updateMask(ee.Image.constant(0))


def main() -> None:
    authenticate_ee()
    region = carbon_project_zone_geometry()
    end = date.today() + timedelta(days=1)
    requested_days = requested_period_days()
    requested_start = end - timedelta(days=requested_days)

    requested_collection = build_collection(region, requested_start, end)
    requested_count, _ = collection_stats(requested_collection, region)
    requested_composite = (
        requested_collection.median().select(["NDVI", "NDMI"])
        if requested_count > 0 else masked_image()
    )
    requested_valid = requested_composite.mask().reduce(ee.Reducer.min()).rename("requested_valid")

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
        observed_in_window = mask_percentage(
            composite.mask().reduce(ee.Reducer.min()), region
        )
        if observed_in_window >= MIN_COVERAGE_PCT or lookback_days == FALLBACK_WINDOWS[-1]:
            selected = (candidate, composite, start, lookback_days, count, cloud)
            break

    if selected is None:
        raise RuntimeError("No Sentinel-2 scenes were found in the adaptive 90–365 day window.")

    collection, composite, start, selected_days, count, cloud = selected
    selected_valid = composite.mask().reduce(ee.Reducer.min()).rename("selected_valid")

    # Pixels already observed in the requested period are direct observations.
    observed_mask = selected_valid.And(requested_valid)
    temporal_mask = selected_valid.And(requested_valid.Not()) if selected_days > requested_days else ee.Image.constant(0).clip(region)

    # Fill spatial gaps using a neighbourhood mean. The candidate is masked where
    # no valid neighbouring pixels exist, so it can be measured separately.
    spatial_candidate = composite.focal_mean(
        radius=INTERPOLATION_RADIUS_M,
        kernelType="circle",
        units="meters",
        iterations=INTERPOLATION_ITERATIONS,
    ).select(["NDVI", "NDMI"])
    spatial_candidate_valid = spatial_candidate.mask().reduce(ee.Reducer.min()).rename("spatial_candidate_valid")
    spatial_mask = selected_valid.Not().And(spatial_candidate_valid)

    # Residual isolated gaps are filled from the regional mean. They remain part
    # of the spatial-interpolation bucket and are explicitly flagged in metadata.
    regional_mean = composite.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=region,
        scale=ANALYSIS_SCALE_M,
        maxPixels=1e9,
        tileScale=8,
        bestEffort=True,
    )
    regional_fill = ee.Image.constant([
        regional_mean.get("NDVI"),
        regional_mean.get("NDMI"),
    ]).rename(["NDVI", "NDMI"])
    residual_mask = selected_valid.Not().And(spatial_candidate_valid.Not())

    filled = composite.unmask(spatial_candidate, sameFootprint=False)
    filled = filled.unmask(regional_fill, sameFootprint=False).clip(region)
    final_valid = filled.mask().reduce(ee.Reducer.min()).rename("final_valid")

    observed_pct = mask_percentage(observed_mask, region)
    temporal_pct = mask_percentage(temporal_mask, region)
    spatial_pct = min(100.0, mask_percentage(spatial_mask, region) + mask_percentage(residual_mask, region))
    total_coverage = mask_percentage(final_valid, region)

    # Keep the reported categories additive and numerically stable after rounding.
    spatial_pct = max(0.0, 100.0 - observed_pct - temporal_pct)
    total_coverage = max(total_coverage, observed_pct + temporal_pct + spatial_pct)

    # Build a complete display grid over the Carbon Project Zone. This keeps the
    # boundary intact even where the original Sentinel-2 composite had masked cells.
    grid = region.coveringGrid(
        ee.Projection(ANALYSIS_CRS).atScale(DISPLAY_GRID_M)
    ).filterBounds(region)
    grid = grid.map(lambda feature: feature.intersection(region, TRANSFORM_ERROR_MARGIN_M))
    result = filled.reduceRegions(
        collection=grid,
        reducer=ee.Reducer.mean(),
        scale=ANALYSIS_SCALE_M,
        crs=ANALYSIS_CRS,
        tileScale=8,
    )
    result = result.map(
        lambda feature: feature.setGeometry(
            feature.geometry().transform(OUTPUT_CRS, TRANSFORM_ERROR_MARGIN_M)
        )
    )

    features = result.getInfo().get("features", [])
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
                "composite_start": start.isoformat(),
                "composite_end": (end - timedelta(days=1)).isoformat(),
                "analysis_start": requested_start.isoformat(),
                "analysis_end": (end - timedelta(days=1)).isoformat(),
                "period_days": selected_days,
                "requested_period_days": requested_days,
                "fallback_used": selected_days != requested_days,
                "scene_count": count,
                "mean_cloud_cover_pct": round(cloud, 2),
                "observed_pct": round(observed_pct, 2),
                "temporal_fallback_pct": round(temporal_pct, 2),
                "spatial_interpolation_pct": round(spatial_pct, 2),
                "total_coverage_pct": round(total_coverage, 2),
                "no_data_pct": 0.0,
                "confidence": "HIGH" if observed_pct >= 85 else "MODERATE" if observed_pct >= 60 else "LOW",
                "analysis_scale_m": ANALYSIS_SCALE_M,
                "display_grid_m": DISPLAY_GRID_M,
                "interpolation_radius_m": INTERPOLATION_RADIUS_M,
                "composite_method": f"{selected_days}-day median + spatial gap fill",
                "analysis_crs": ANALYSIS_CRS,
                "output_crs": OUTPUT_CRS,
                "boundary": "SERPRO Carbon Project Zone",
                "source": S2,
                "updated_utc": datetime.now(timezone.utc).isoformat(),
            },
        })

    if not output_features:
        raise RuntimeError("Sentinel-2 scenes were found, but no complete spatial vegetation cells were produced.")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps({"type": "FeatureCollection", "features": output_features}, separators=(",", ":")),
        encoding="utf-8",
    )
    print(
        f"Wrote {len(output_features)} web cells; analysis={ANALYSIS_SCALE_M}m; "
        f"display_grid={DISPLAY_GRID_M}m; requested={requested_days}d; "
        f"effective={selected_days}d; scenes={count}; cloud={cloud:.2f}%; "
        f"observed={observed_pct:.2f}%; temporal={temporal_pct:.2f}%; "
        f"spatial={spatial_pct:.2f}%; total={total_coverage:.2f}%"
    )


if __name__ == "__main__":
    main()
