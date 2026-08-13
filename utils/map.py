import gzip
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import folium
import pandas as pd
from folium.plugins import Fullscreen

from utils.climate.fire import load_fire

KML_NS = {"kml": "http://www.opengis.net/kml/2.2"}
PROJECT_AREA_SOURCE = Path("data/static/project_boundary.kml.gz")
CARBON_PROJECT_ZONE = Path("data/static/boundaries/serpro_carbon_project_zone_web.geojson")


def load_project_area(path=PROJECT_AREA_SOURCE):
    """Load the official KAL concession / SERPRO Project Area source KML."""
    if not path.exists():
        return {"type": "FeatureCollection", "features": []}
    with gzip.open(path, "rb") as f:
        root = ET.fromstring(f.read())
    features = []
    for placemark in root.findall(".//kml:Placemark", KML_NS):
        name = placemark.findtext("kml:name", default="Project Area Block", namespaces=KML_NS)
        for ring in placemark.findall(".//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", KML_NS):
            coords = []
            for item in (ring.text or "").split():
                parts = item.split(",")
                if len(parts) >= 2:
                    coords.append([float(parts[0]), float(parts[1])])
            if len(coords) >= 4:
                features.append({
                    "type": "Feature",
                    "properties": {"name": name, "boundary_role": "project_area_concession"},
                    "geometry": {"type": "Polygon", "coordinates": [coords]},
                })
    return {"type": "FeatureCollection", "features": features}


def load_carbon_project_zone(path=CARBON_PROJECT_ZONE):
    """Load the official SERPRO Carbon Project Zone web geometry."""
    if not path.exists():
        return {"type": "FeatureCollection", "features": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _bounds_from_geojson(collection):
    points = []
    for feature in collection.get("features", []):
        geometry = feature.get("geometry") or {}
        coords = geometry.get("coordinates", [])
        if geometry.get("type") == "Polygon":
            rings = coords
        elif geometry.get("type") == "MultiPolygon":
            rings = [ring for polygon in coords for ring in polygon]
        else:
            rings = []
        for ring in rings:
            points.extend(ring)
    if not points:
        return None
    lons = [p[0] for p in points]
    lats = [p[1] for p in points]
    return [[min(lats), min(lons)], [max(lats), max(lons)]]


def _prepare_hotspots(hotspots):
    """Replace legacy/demo hotspot data with the latest connected VIIRS observations."""
    if hotspots is not None and not hotspots.empty and {"lat", "lon"}.issubset(hotspots.columns):
        live = load_fire()
        if live.empty:
            return hotspots.copy(), False
        live = live.copy()
        live["date"] = pd.to_datetime(live["date"], errors="coerce")
        latest = live["date"].max()
        live = live[live["date"] == latest].copy()
        if live.empty:
            return hotspots.copy(), False
        live["lat"] = live["latitude"]
        live["lon"] = live["longitude"]
        return live, True
    if hotspots is None:
        return pd.DataFrame(), False
    return hotspots.copy(), False


def render_map(hotspots, monitoring_points, focus="All Boundaries"):
    """Render SERPRO WebGIS with official boundaries and real VIIRS hotspots."""
    project_area = load_project_area()
    project_zone = load_carbon_project_zone()
    hotspots, live_mode = _prepare_hotspots(hotspots)

    m = folium.Map(location=[-3.10, 112.62], zoom_start=9, tiles="CartoDB positron", control_scale=True)
    Fullscreen().add_to(m)

    show_project_area = focus in ("All Boundaries", "SERPRO Project Area")
    show_project_zone = focus in ("All Boundaries", "Carbon Project Zone")

    if project_area["features"]:
        area_layer = folium.FeatureGroup(name="🟢 SERPRO Project Area (Concession)", show=show_project_area)
        folium.GeoJson(
            project_area,
            style_function=lambda _: {"color": "#146B43", "weight": 2.5, "fillColor": "#2E7D32", "fillOpacity": 0.04},
            highlight_function=lambda _: {"weight": 4, "fillOpacity": 0.09},
            tooltip=folium.GeoJsonTooltip(fields=["name"], aliases=["Block"]),
        ).add_to(area_layer)
        area_layer.add_to(m)

    if project_zone["features"]:
        zone_layer = folium.FeatureGroup(name="🟣 SERPRO Carbon Project Zone", show=show_project_zone)
        folium.GeoJson(
            project_zone,
            style_function=lambda _: {"color": "#6A4C93", "weight": 3, "fillColor": "#9B7EBD", "fillOpacity": 0.08},
            highlight_function=lambda _: {"weight": 4.5, "fillOpacity": 0.14},
            tooltip=folium.GeoJsonTooltip(fields=["name"], aliases=["Boundary"]),
        ).add_to(zone_layer)
        zone_layer.add_to(m)

    hotspot_group = folium.FeatureGroup(name="🔥 VIIRS Hotspots")
    if not hotspots.empty:
        for _, row in hotspots.iterrows():
            raw_conf = row.get("confidence")
            if live_mode:
                level = {0: "LOW", 1: "MODERATE", 2: "HIGH"}.get(int(raw_conf) if pd.notna(raw_conf) else -1, "UNKNOWN")
                confidence_text = level
            else:
                level = "HIGH" if float(raw_conf) >= 85 else "MEDIUM" if float(raw_conf) >= 70 else "LOW"
                confidence_text = f"{float(raw_conf):.0f}%"
            color = {"HIGH": "#D32F2F", "MODERATE": "#F9A825", "MEDIUM": "#F9A825", "LOW": "#43A047"}.get(level, "#757575")
            source = str(row.get("source", "NASA LANCE VIIRS"))
            date_text = str(row.get("date", ""))[:10]
            scope_text = str(row.get("scope", "SERPRO"))
            folium.CircleMarker(
                location=[float(row["lat"]), float(row["lon"])],
                radius=6,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.85,
                popup=(
                    f"<b>VIIRS Active Fire</b><br>"
                    f"Date: {date_text}<br>"
                    f"Confidence: {confidence_text}<br>"
                    f"Level: {level}<br>"
                    f"Source: {source}<br>"
                    f"Scope: {scope_text}<br>"
                    f"Location: {float(row['lat']):.5f}, {float(row['lon']):.5f}"
                ),
            ).add_to(hotspot_group)
    hotspot_group.add_to(m)

    # Do not display the former demo monitoring points on the landing page.
    if monitoring_points is not None and not monitoring_points.empty and "is_live" in monitoring_points.columns:
        live_points = monitoring_points[monitoring_points["is_live"] == True]
        if not live_points.empty:
            point_group = folium.FeatureGroup(name="📍 Monitoring Points")
            for _, row in live_points.iterrows():
                folium.Marker(
                    location=[row["lat"], row["lon"]],
                    tooltip=row.get("id", "Monitoring Point"),
                    popup=f"<b>{row.get('id', 'Monitoring Point')}</b><br>{row.get('description', 'Live monitoring point')}",
                    icon=folium.Icon(color="green", icon="tint", prefix="fa"),
                ).add_to(point_group)
            point_group.add_to(m)

    target = project_zone if focus == "Carbon Project Zone" else project_area
    bounds = _bounds_from_geojson(target)
    if focus == "All Boundaries":
        area_bounds = _bounds_from_geojson(project_area)
        zone_bounds = _bounds_from_geojson(project_zone)
        if area_bounds and zone_bounds:
            bounds = [[min(area_bounds[0][0], zone_bounds[0][0]), min(area_bounds[0][1], zone_bounds[0][1])], [max(area_bounds[1][0], zone_bounds[1][0]), max(area_bounds[1][1], zone_bounds[1][1])]]
    if bounds:
        m.fit_bounds(bounds, padding=(20, 20))

    folium.LayerControl(collapsed=False).add_to(m)
    return m
