import gzip
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import folium
from folium.plugins import Fullscreen

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


def render_map(hotspots, monitoring_points, focus="All Boundaries"):
    """Render SERPRO WebGIS with official Project Area and Carbon Project Zone."""
    project_area = load_project_area()
    project_zone = load_carbon_project_zone()

    m = folium.Map(
        location=[-3.10, 112.62],
        zoom_start=9,
        tiles="CartoDB positron",
        control_scale=True,
    )
    Fullscreen().add_to(m)

    show_project_area = focus in ("All Boundaries", "SERPRO Project Area")
    show_project_zone = focus in ("All Boundaries", "Carbon Project Zone")

    if project_area["features"]:
        area_layer = folium.FeatureGroup(name="🟢 SERPRO Project Area (Concession)", show=show_project_area)
        folium.GeoJson(
            project_area,
            style_function=lambda _: {
                "color": "#146B43",
                "weight": 2.5,
                "fillColor": "#2E7D32",
                "fillOpacity": 0.04,
            },
            highlight_function=lambda _: {"weight": 4, "fillOpacity": 0.09},
            tooltip=folium.GeoJsonTooltip(fields=["name"], aliases=["Block"]),
        ).add_to(area_layer)
        area_layer.add_to(m)

    if project_zone["features"]:
        zone_layer = folium.FeatureGroup(name="🟣 SERPRO Carbon Project Zone", show=show_project_zone)
        folium.GeoJson(
            project_zone,
            style_function=lambda _: {
                "color": "#6A4C93",
                "weight": 3,
                "fillColor": "#9B7EBD",
                "fillOpacity": 0.08,
            },
            highlight_function=lambda _: {"weight": 4.5, "fillOpacity": 0.14},
            tooltip=folium.GeoJsonTooltip(fields=["name"], aliases=["Boundary"]),
        ).add_to(zone_layer)
        zone_layer.add_to(m)

    hotspot_group = folium.FeatureGroup(name="🔥 VIIRS Hotspots")
    for _, row in hotspots.iterrows():
        level = "HIGH" if row["confidence"] >= 85 else "MEDIUM" if row["confidence"] >= 70 else "LOW"
        color = {"HIGH": "#D32F2F", "MEDIUM": "#F9A825", "LOW": "#43A047"}[level]
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=6,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.85,
            popup=f"VIIRS hotspot<br>Confidence: {row['confidence']}%<br>Priority: {level}",
        ).add_to(hotspot_group)
    hotspot_group.add_to(m)

    point_group = folium.FeatureGroup(name="📍 Monitoring Points")
    for _, row in monitoring_points.iterrows():
        folium.Marker(
            location=[row["lat"], row["lon"]],
            tooltip=row["id"],
            popup=f"<b>{row['id']}</b><br>Demo monitoring point",
            icon=folium.Icon(color="green", icon="tint", prefix="fa"),
        ).add_to(point_group)
    point_group.add_to(m)

    target = project_zone if focus == "Carbon Project Zone" else project_area
    bounds = _bounds_from_geojson(target)
    if focus == "All Boundaries":
        area_bounds = _bounds_from_geojson(project_area)
        zone_bounds = _bounds_from_geojson(project_zone)
        if area_bounds and zone_bounds:
            bounds = [
                [min(area_bounds[0][0], zone_bounds[0][0]), min(area_bounds[0][1], zone_bounds[0][1])],
                [max(area_bounds[1][0], zone_bounds[1][0]), max(area_bounds[1][1], zone_bounds[1][1])],
            ]
    if bounds:
        m.fit_bounds(bounds, padding=(20, 20))

    folium.LayerControl(collapsed=False).add_to(m)
    return m
