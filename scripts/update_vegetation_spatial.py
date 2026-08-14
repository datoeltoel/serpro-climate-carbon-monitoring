"""Build actual spatial vegetation status from Sentinel-2 SR Harmonized.

Analysis is performed at Sentinel-2's native 10 m scale. For a practical web
map, the 10 m pixels are summarized into a 100 m display grid before GeoJSON
export. The spatial extent is the official SERPRO Carbon Project Zone.

The requested composite window is attempted first. If there are no valid
Sentinel-2 scenes after cloud/SCL masking, the workflow automatically expands
the window to 60 and then 90 days. The output records the actual period used.
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
FALLBACK_WINDOWS_DAYS = [30, 60, 90]
MAX_CLOUDY_PIXEL_PERCENTAGE = 40
ANALYSIS_SCALE_M = 10
DISPLAY_GRID_M = 100
ANALYSIS_CRS = "EPSG:32749"  # WGS 84 / UTM zone 49S
OUTPUT_CRS = "EPSG:4326"     # GeoJSON / Leaflet display CRS
TRANSFORM_ERROR_MARGIN_M = 1


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
    """Load the official SERPRO Carbon Project Zone boundary."""
    if not ZONE_GEOJSON.exists():
        raise RuntimeError(f"Carbon Project Zone file not found: {ZONE_GEOJSON}")
    data = json.loads(ZONE_GEOJSON.read_text(encoding="utf-8"))
    geometry = data.get("geometry") if data.get("type") == "Feature" else None
    if geometry is None and data.get("type") == "FeatureCollection":
        geoms = [f.get("geometry") for f in data.get("features", []) if f.get("geometry")]
        if not geoms:
            raise RuntimeError("No geometry found in Carbon Project Zone GeoJSON.")
        geometry = geoms[0] if len(geoms) == 1 else {"type": "GeometryCollection", "geometries": geoms}
    if geometry is None:
        geometry = data
    return ee.Geometry(geometry)


def mask_s2(img: ee.Image) -> ee.Image:
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


def main() -> None:
    authenticate_ee()
    region = carbon_project_zone_geometry()
    end = date.today() + timedelta(days=1)

    collection = None
    count = 0
    selected_days = None
    start = None

    # Automatic date fallback: 30D -> 60D -> 90D.
    for lookback_days in FALLBACK_WINDOWS_DAYS:
        candidate_start = end - timedelta(days=lookback_days)
        candidate = build_collection(region, candidate_start, end)
        candidate_count = int(candidate.size().getInfo())
        if candidate_count > 0:
            collection = candidate
            count = candidate_count
            selected_days = lookback_days
            start = candidate_start
            break

    if collection is None or start is None or selected_days is None:
        raise RuntimeError(
            "No valid Sentinel-2 scenes found for 30, 60, or 90-day fallback windows."
        )

    composite = collection.median().select(["NDVI", "NDMI"])

    # Native analysis stays at 10 m. The 100 m display grid is an aggregation
    # for web performance; it is NOT a claim that Sentinel-2 resolution is 100 m.
    grid = (
        region
        .coveringGrid(ee.Projection(ANALYSIS_CRS).atScale(DISPLAY_GRID_M))
        .filterBounds(region)
    )

    # Clip every display cell to the official Carbon Project Zone so that the
    # map follows the real boundary instead of showing rectangular cells outside it.
    grid = grid.map(
        lambda feature: feature.intersection(region, TRANSFORM_ERROR_MARGIN_M)
    )

    result = composite.reduceRegions(
        collection=grid,
        reducer=ee.Reducer.mean(),
        scale=ANALYSIS_SCALE_M,
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
                "period_days": selected_days,
                "requested_period_days": DEFAULT_LOOKBACK_DAYS,
                "fallback_used": selected_days != DEFAULT_LOOKBACK_DAYS,
                "scene_count": count,
                "analysis_scale_m": ANALYSIS_SCALE_M,
                "display_grid_m": DISPLAY_GRID_M,
                "composite_method": "30-day median" if selected_days == 30 else f"{selected_days}-day median fallback",
                "analysis_crs": ANALYSIS_CRS,
                "output_crs": OUTPUT_CRS,
                "boundary": "SERPRO Carbon Project Zone",
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
        f"Wrote {len(output_features)} cells: boundary=Carbon Project Zone, "
        f"analysis={ANALYSIS_SCALE_M}m, display_grid={DISPLAY_GRID_M}m, "
        f"period={selected_days}d, scenes={count}, analysis_crs={ANALYSIS_CRS}, "
        f"output_crs={OUTPUT_CRS}"
    )


if __name__ == "__main__":
    main()
