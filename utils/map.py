import gzip
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import folium
from folium.plugins import Fullscreen

KML_NS = {"kml": "http://www.opengis.net/kml/2.2"}
BOUNDARY_PATH = Path("data/static/project_boundary.kml.gz")


def load_project_boundary(path=BOUNDARY_PATH):
    """Read the preserved SERPRO KML source and convert polygons to GeoJSON."""
    if not path.exists():
        return None

    with gzip.open(path, "rb") as f:
        root = ET.fromstring(f.read())

    features = []
    for placemark in root.findall(".//kml:Placemark", KML_NS):
        name = placemark.findtext("kml:name", default="Project Block", namespaces=KML_NS)
        polygons = []
        for ring in placemark.findall(".//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", KML_NS):
            coords = []
            for item in (ring.text or "").split():
                parts = item.split(",")
                if len(parts) >= 2:
                    coords.append([float(parts[0]), float(parts[1])])
            if coords:
                polygons.append([coords])

        if not polygons:
            continue

        geometry = polygons[0] if len(polygons) == 1 else {
            "type": "MultiPolygon",
            "coordinates": polygons,
        }
        if len(polygons) == 1:
            geometry = {"type": "Polygon", "coordinates": polygons[0]}

        features.append({
            "type": "Feature",
            "properties": {"Name": name},
            "geometry": geometry,
        })

    return {"type": "FeatureCollection", "features": features}


def render_map(hotspots, monitoring_points):
    m = folium.Map(
        location=[-3.085, 112.62],
        zoom_start=10,
        tiles="CartoDB positron",
        control_scale=True,
    )
    Fullscreen().add_to(m)

    boundary = load_project_boundary()
    if boundary:
        folium.GeoJson(
            boundary,
            name="🟢 SERPRO Project Boundary",
            style_function=lambda _: {
                "color": "#0B5D3B",
                "weight": 3,
                "fillColor": "#2E7D32",
                "fillOpacity": 0.08,
            },
            highlight_function=lambda _: {"weight": 4, "fillOpacity": 0.12},
            tooltip=folium.GeoJsonTooltip(fields=["Name"], aliases=["Block"]),
        ).add_to(m)

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

    folium.LayerControl(collapsed=False).add_to(m)
    return m
