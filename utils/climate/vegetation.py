"""Load processed Sentinel-2 vegetation index data."""
from pathlib import Path
import base64
import gzip
import json
import pandas as pd

NDMI_PATH = Path("data/processed/climate/vegetation/ndmi_daily.csv")
NDVI_PATH = Path("data/processed/climate/vegetation/ndvi_daily.csv")
NDVI_ANNUAL_PATH = Path("data/processed/climate/vegetation/ndvi_annual_2015_2025.csv")
VEGETATION_SPATIAL_PATH = Path("data/processed/climate/vegetation/vegetation_spatial_latest.geojson")
VEGETATION_RASTER_PATH = Path("data/processed/climate/vegetation/vegetation_spatial_raster.json")


def _load(path: Path, value_col: str) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["date", "scope", value_col, "cloudy_pixel_percentage", "source", "processing_time_utc"])
    df = pd.read_csv(path, parse_dates=["date"])
    df = df.dropna(subset=["date", "scope", value_col]).copy()
    df = (df.groupby(["date", "scope"], as_index=False)
          .agg(**{value_col: (value_col, "mean"),
                  "cloudy_pixel_percentage": ("cloudy_pixel_percentage", "mean"),
                  "source": ("source", "first"),
                  "processing_time_utc": ("processing_time_utc", "max")})
          .sort_values(["date", "scope"]))
    return df


def load_ndmi() -> pd.DataFrame:
    return _load(NDMI_PATH, "ndmi")


def load_ndvi() -> pd.DataFrame:
    return _load(NDVI_PATH, "ndvi")


def load_ndvi_annual() -> pd.DataFrame:
    if not NDVI_ANNUAL_PATH.exists():
        return pd.DataFrame(columns=["year", "scope", "ndvi_mean", "observation_count", "source", "note"])
    df = pd.read_csv(NDVI_ANNUAL_PATH)
    return df.dropna(subset=["year", "scope", "ndvi_mean"]).sort_values(["year", "scope"])


def load_vegetation_spatial() -> dict:
    """Return the latest Sentinel-2 spatial overview GeoJSON."""
    if not VEGETATION_SPATIAL_PATH.exists():
        return {"type": "FeatureCollection", "features": []}
    try:
        return json.loads(VEGETATION_SPATIAL_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"type": "FeatureCollection", "features": []}


def load_vegetation_spatial_raster() -> dict:
    """Return the compact 100 m web raster package."""
    if not VEGETATION_RASTER_PATH.exists():
        return {}
    try:
        return json.loads(VEGETATION_RASTER_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def raster_data_uri(packed: str) -> str:
    """Decode base64+gzip PNG payload into a browser-ready data URI."""
    raw = gzip.decompress(base64.b64decode(packed))
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
