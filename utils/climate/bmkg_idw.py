from __future__ import annotations

import numpy as np
import pandas as pd
import geopandas as gpd
from scipy.spatial.distance import cdist
from shapely.geometry import Point

PROJECT_ZONE_PATH = "data/static/boundaries/serpro_carbon_project_zone_web.geojson"
PROJECT_AREA_PATH = "data/static/boundaries/serpro_project_area_web.geojson"
PROJECT_CRS = 32749  # WGS 84 / UTM zone 49S


def idw_values(
    source_xy: np.ndarray,
    source_values: np.ndarray,
    target_xy: np.ndarray,
    power: float = 2.0,
    max_distance_m: float | None = None,
) -> np.ndarray:
    """Inverse-distance weighting from source points to target coordinates."""
    source_xy = np.asarray(source_xy, dtype=float)
    source_values = np.asarray(source_values, dtype=float)
    target_xy = np.asarray(target_xy, dtype=float)
    if source_xy.ndim != 2 or source_xy.shape[1] != 2:
        raise ValueError("source_xy must be an n x 2 array")
    if target_xy.ndim != 2 or target_xy.shape[1] != 2:
        raise ValueError("target_xy must be an m x 2 array")
    if len(source_xy) != len(source_values):
        raise ValueError("source coordinates and values must have equal length")
    if len(source_xy) == 0:
        return np.full(len(target_xy), np.nan)

    valid = np.isfinite(source_values)
    if not valid.any():
        return np.full(len(target_xy), np.nan)
    source_xy = source_xy[valid]
    source_values = source_values[valid]
    distances = cdist(target_xy, source_xy)
    exact = distances == 0

    if max_distance_m is not None:
        distances = np.where(distances <= max_distance_m, distances, np.inf)
    with np.errstate(divide="ignore", invalid="ignore"):
        weights = 1.0 / np.power(distances, power)
    weights[~np.isfinite(weights)] = 0.0

    result = np.full(len(target_xy), np.nan)
    exact_rows = np.where(exact.any(axis=1))[0]
    if len(exact_rows):
        result[exact_rows] = source_values[exact[exact_rows].argmax(axis=1)]

    other = np.isnan(result)
    if other.any():
        w = weights[other]
        denom = w.sum(axis=1)
        ok = denom > 0
        result_idx = np.where(other)[0][ok]
        result[result_idx] = (w[ok] @ source_values) / denom[ok]
    return result


def build_project_zone_grid(
    resolution_m: int = 1000,
    boundary_path: str = PROJECT_ZONE_PATH,
) -> gpd.GeoDataFrame:
    """Create a regular metric point grid clipped to a supplied SERPRO boundary."""
    boundary = gpd.read_file(boundary_path).to_crs(PROJECT_CRS)
    geom = boundary.geometry.union_all()
    minx, miny, maxx, maxy = geom.bounds
    xs = np.arange(minx, maxx + resolution_m, resolution_m)
    ys = np.arange(miny, maxy + resolution_m, resolution_m)
    points = []
    for x in xs:
        for y in ys:
            p = Point(float(x), float(y))
            if geom.contains(p):
                points.append(p)
    return gpd.GeoDataFrame({"geometry": points}, crs=PROJECT_CRS)


def interpolate_forecast_to_project_zone(
    forecast: pd.DataFrame,
    value_column: str,
    when: pd.Timestamp,
    resolution_m: int = 1000,
    power: float = 2.0,
    boundary_path: str = PROJECT_ZONE_PATH,
    boundary_label: str = "SERPRO Carbon Project Zone",
) -> gpd.GeoDataFrame:
    """Interpolate one BMKG forecast variable over a clipped SERPRO boundary.

    The five BMKG ADM4 locations are forecast input points. The output is a
    forecast surface clipped to the requested project boundary. It must not be
    interpreted as direct observations or used in historical climate-risk calculations.
    """
    required = {"location", "latitude", "longitude", "local_datetime", value_column}
    missing = required.difference(forecast.columns)
    if missing:
        raise ValueError(f"Missing forecast columns: {sorted(missing)}")

    subset = forecast.copy()
    subset["local_datetime"] = pd.to_datetime(subset["local_datetime"], errors="coerce")
    subset = subset.dropna(subset=["latitude", "longitude", value_column, "local_datetime"])
    subset = subset[subset["local_datetime"] == pd.Timestamp(when)]
    subset = subset.drop_duplicates("location")
    if len(subset) < 3:
        raise ValueError("At least three valid BMKG forecast points are required for IDW")

    source_gdf = gpd.GeoDataFrame(
        subset[["location", value_column]].copy(),
        geometry=[Point(xy) for xy in zip(subset["longitude"], subset["latitude"])],
        crs=4326,
    ).to_crs(PROJECT_CRS)
    source_coords = np.array([(p.x, p.y) for p in source_gdf.geometry], dtype=float)
    values = source_gdf[value_column].to_numpy(dtype=float)

    grid = build_project_zone_grid(resolution_m=resolution_m, boundary_path=boundary_path)
    if grid.empty:
        raise ValueError(f"No grid cells generated inside {boundary_label}")
    target_coords = np.array([(p.x, p.y) for p in grid.geometry], dtype=float)
    grid[value_column] = idw_values(source_coords, values, target_coords, power=power)
    grid["forecast_datetime"] = pd.Timestamp(when).isoformat()
    grid["source"] = "BMKG ADM4 forecast points + IDW"
    grid["boundary"] = boundary_label
    grid["interpretation"] = "Forecast surface clipped to project boundary; not direct station observation"
    return grid.to_crs(4326)
