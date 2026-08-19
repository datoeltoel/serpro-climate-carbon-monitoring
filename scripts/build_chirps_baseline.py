"""Build SERPRO rainfall baseline from CHIRPS v2 Final (1981-2025).

Outputs:
- data/processed/climate/rainfall/chirps_monthly_1981_2025.csv
- data/processed/climate/rainfall/chirps_climatology_1991_2020.csv
- data/processed/climate/rainfall/chirps_baseline_metadata.json

The monthly series is spatially averaged over the official SERPRO Carbon Project
Zone and Project Area. Monthly rainfall is the sum of daily CHIRPS precipitation
(mm/day), then spatially averaged over each scope. Observation exports also carry
representative centroid longitude/latitude for the selected scope.
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
import pandas as pd
from google.oauth2 import service_account

KML_NS = {"kml": "http://www.opengis.net/kml/2.2"}
PROJECT_AREA_KML = Path("data/static/project_boundary.kml.gz")
PROJECT_ZONE_GEOJSON = Path("data/static/boundaries/serpro_carbon_project_zone_web.geojson")
OUT_DIR = Path("data/processed/climate/rainfall")
MONTHLY_OUTPUT = OUT_DIR / "chirps_monthly_1981_2025.csv"
CLIMATOLOGY_OUTPUT = OUT_DIR / "chirps_climatology_1991_2020.csv"
METADATA_OUTPUT = OUT_DIR / "chirps_baseline_metadata.json"
COLLECTION = "UCSB-CHG/CHIRPS/DAILY"
BAND = "precipitation"
SCALE = 5566
START = "1981-01-01"
END = "2026-01-01"
NORMAL_START = 1991
NORMAL_END = 2020


def authenticate_ee() -> None:
    key_json = os.environ.get("EE_SERVICE_ACCOUNT_JSON")
    cloud_project = os.environ.get("EE_PROJECT_ID")
    if not key_json or not cloud_project:
        raise RuntimeError("Set EE_SERVICE_ACCOUNT_JSON and EE_PROJECT_ID GitHub secrets.")

    try:
        info = json.loads(key_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError("EE_SERVICE_ACCOUNT_JSON is not valid JSON.") from exc

    required = ("type", "project_id", "private_key", "client_email", "token_uri")
    missing = [field for field in required if not info.get(field)]
    if missing:
        raise RuntimeError("EE_SERVICE_ACCOUNT_JSON is missing required fields: " + ", ".join(missing))

    private_key = info["private_key"].strip()
    if "..." in private_key:
        raise RuntimeError("EE_SERVICE_ACCOUNT_JSON contains placeholder text ('...') in private_key.")
    if not private_key.startswith("-----BEGIN PRIVATE KEY-----") or not private_key.endswith("-----END PRIVATE KEY-----"):
        raise RuntimeError("EE_SERVICE_ACCOUNT_JSON contains an invalid PEM private key block.")
    if len(private_key) < 500:
        raise RuntimeError("EE_SERVICE_ACCOUNT_JSON private_key appears truncated.")

    credentials = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    ee.Initialize(credentials=credentials, project=cloud_project)
    print(f"Earth Engine initialized with project: {cloud_project}")
    print(f"Earth Engine service account: {info['client_email']}")


def project_area_geometry() -> ee.Geometry:
    with gzip.open(PROJECT_AREA_KML, "rb") as fh:
        root = ET.fromstring(fh.read())
    polygons = []
    for node in root.findall(
        ".//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", KML_NS
    ):
        coords = []
        for item in (node.text or "").split():
            parts = item.split(",")
            if len(parts) >= 2:
                coords.append([float(parts[0]), float(parts[1])])
        if len(coords) >= 4:
            polygons.append(coords)
    if not polygons:
        raise RuntimeError("No polygons found in SERPRO Project Area KML.")
    return ee.Geometry.MultiPolygon(polygons) if len(polygons) > 1 else ee.Geometry.Polygon(polygons[0])


def project_zone_geometry() -> ee.Geometry:
    obj = json.loads(PROJECT_ZONE_GEOJSON.read_text(encoding="utf-8"))
    features = obj.get("features", [])
    if not features:
        raise RuntimeError("No features found in SERPRO Carbon Project Zone GeoJSON.")
    return ee.Geometry(features[0]["geometry"])


def build_monthly_features(scopes: dict[str, ee.Geometry]) -> ee.FeatureCollection:
    collection = ee.ImageCollection(COLLECTION).filterDate(START, END).select(BAND)
    month_count = 45 * 12
    month_indices = ee.List.sequence(0, month_count - 1)

    centroids = {
        name: geometry.centroid(maxError=100).coordinates()
        for name, geometry in scopes.items()
    }

    def make_month(index):
        index = ee.Number(index)
        start = ee.Date(START).advance(index, "month")
        end = start.advance(1, "month")
        image = collection.filterDate(start, end).sum()

        zone_value = image.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=scopes["carbon_project_zone"],
            scale=SCALE,
            maxPixels=1_000_000,
            bestEffort=True,
        ).get(BAND)
        project_value = image.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=scopes["project_area"],
            scale=SCALE,
            maxPixels=1_000_000,
            bestEffort=True,
        ).get(BAND)

        zone_centroid = centroids["carbon_project_zone"]
        project_centroid = centroids["project_area"]

        return ee.FeatureCollection([
            ee.Feature(None, {
                "year": start.get("year"),
                "month": start.get("month"),
                "scope": "carbon_project_zone",
                "longitude": zone_centroid.get(0),
                "latitude": zone_centroid.get(1),
                "rainfall_mm": zone_value,
                "source": COLLECTION,
            }),
            ee.Feature(None, {
                "year": start.get("year"),
                "month": start.get("month"),
                "scope": "project_area",
                "longitude": project_centroid.get(0),
                "latitude": project_centroid.get(1),
                "rainfall_mm": project_value,
                "source": COLLECTION,
            }),
        ])

    return ee.FeatureCollection(month_indices.map(make_month)).flatten()


def main() -> None:
    authenticate_ee()
    scopes = {
        "carbon_project_zone": project_zone_geometry(),
        "project_area": project_area_geometry(),
    }
    features = build_monthly_features(scopes).getInfo()["features"]
    rows = []
    for feature in features:
        props = feature.get("properties", {})
        value = props.get("rainfall_mm")
        if value is None:
            continue
        rows.append({
            "year": int(props["year"]),
            "month": int(props["month"]),
            "scope": props["scope"],
            "longitude": float(props["longitude"]),
            "latitude": float(props["latitude"]),
            "rainfall_mm": float(value),
            "source": props["source"],
        })

    if not rows:
        raise RuntimeError("CHIRPS baseline returned no monthly rainfall records.")

    df = pd.DataFrame(rows).sort_values(["scope", "year", "month"])
    expected = 45 * 12 * 2
    if len(df) < expected:
        print(f"Warning: expected up to {expected} rows, received {len(df)}.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(MONTHLY_OUTPUT, index=False, float_format="%.6f")

    normal = df[df["year"].between(NORMAL_START, NORMAL_END)].copy()
    climatology = (
        normal.groupby(["scope", "month"], as_index=False)["rainfall_mm"]
        .agg(
            normal_mean_mm="mean",
            normal_std_mm="std",
            p10_mm=lambda s: s.quantile(0.10),
            p25_mm=lambda s: s.quantile(0.25),
            median_mm="median",
            p75_mm=lambda s: s.quantile(0.75),
            p90_mm=lambda s: s.quantile(0.90),
            n_years="count",
        )
    )
    climatology["normal_period"] = f"{NORMAL_START}-{NORMAL_END}"
    climatology.to_csv(CLIMATOLOGY_OUTPUT, index=False, float_format="%.4f")

    metadata = {
        "source": COLLECTION,
        "historical_period": "1981-2025",
        "historical_download_period": "1996-2025",
        "climatology_period": f"{NORMAL_START}-{NORMAL_END}",
        "spatial_resolution_m": SCALE,
        "cadence": "daily",
        "aggregation": "monthly sum of daily precipitation, then spatial mean over scope",
        "coordinate_reference_system": "EPSG:4326",
        "coordinate_definition": "representative centroid longitude/latitude of each SERPRO monitoring scope",
        "scope": ["carbon_project_zone", "project_area"],
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "monthly_records": int(len(df)),
        "climatology_records": int(len(climatology)),
    }
    metadata["scope_coordinates"] = {
        scope: {
            "longitude": float(df.loc[df["scope"] == scope, "longitude"].iloc[0]),
            "latitude": float(df.loc[df["scope"] == scope, "latitude"].iloc[0]),
        }
        for scope in metadata["scope"]
        if not df.loc[df["scope"] == scope].empty
    }
    METADATA_OUTPUT.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Wrote {len(df)} monthly records to {MONTHLY_OUTPUT}")
    print(f"Wrote {len(climatology)} climatology records to {CLIMATOLOGY_OUTPUT}")


if __name__ == "__main__":
    main()
