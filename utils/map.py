import gzip
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import folium
import pandas as pd
from folium.plugins import Fullscreen

KML_NS = {"kml": "http://www.opengis.net/kml/2.2"}
PROJECT_AREA_SOURCE = Path("data/static/project_boundary.kml.gz")
CARBON_PROJECT_ZONE = Path("data/static/boundaries/serpro_carbon_project_zone_web.geojson")


def load_project_area(path=PROJECT_AREA_SOURCE):
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
                features.append({"type":"Feature","properties":{"name":name,"boundary_role":"project_area_concession"},"geometry":{"type":"Polygon","coordinates":[coords]}})
    return {"type":"FeatureCollection","features":features}


def load_carbon_project_zone(path=CARBON_PROJECT_ZONE):
    if not path.exists():
        return {"type":"FeatureCollection","features":[]}
    return json.loads(path.read_text(encoding="utf-8"))


def _bounds_from_geojson(collection):
    points=[]
    for feature in collection.get("features", []):
        geometry=feature.get("geometry") or {}
        coords=geometry.get("coordinates", [])
        if geometry.get("type")=="Polygon":
            rings=coords
        elif geometry.get("type")=="MultiPolygon":
            rings=[ring for polygon in coords for ring in polygon]
        else:
            rings=[]
        for ring in rings:
            points.extend(ring)
    if not points:
        return None
    lons=[p[0] for p in points]; lats=[p[1] for p in points]
    return [[min(lats),min(lons)],[max(lats),max(lons)]]


def _prepare_hotspots(hotspots):
    if hotspots is None or hotspots.empty:
        return pd.DataFrame(), False
    live=hotspots.copy()
    if {"latitude","longitude"}.issubset(live.columns):
        live["date"]=pd.to_datetime(live["date"],errors="coerce")
        live["lat"]=live["latitude"]
        live["lon"]=live["longitude"]
        return live, True
    if {"lat","lon"}.issubset(live.columns):
        return live, False
    return pd.DataFrame(), False


def render_map(hotspots, monitoring_points=None, focus="All Boundaries"):
    project_area=load_project_area(); project_zone=load_carbon_project_zone()
    hotspots, live_mode=_prepare_hotspots(hotspots)

    m=folium.Map(location=[-3.10,112.62], zoom_start=9, tiles=None, control_scale=True)
    folium.TileLayer("CartoDB positron", name="Light map", control=True, show=False).add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles © Esri",
        name="Satellite imagery",
        overlay=False,
        control=True,
        show=True,
    ).add_to(m)
    Fullscreen().add_to(m)

    show_project_area=focus in ("All Boundaries","SERPRO Project Area")
    show_project_zone=focus in ("All Boundaries","Carbon Project Zone")
    if project_area["features"]:
        area_layer=folium.FeatureGroup(name="🟢 SERPRO Project Area (Concession)",show=show_project_area)
        folium.GeoJson(project_area,style_function=lambda _: {"color":"#19A463","weight":3,"fillColor":"#19A463","fillOpacity":0.06},highlight_function=lambda _: {"weight":4,"fillOpacity":0.10},tooltip=folium.GeoJsonTooltip(fields=["name"],aliases=["Block"])).add_to(area_layer)
        area_layer.add_to(m)
    if project_zone["features"]:
        zone_layer=folium.FeatureGroup(name="🟣 SERPRO Carbon Project Zone",show=show_project_zone)
        folium.GeoJson(project_zone,style_function=lambda _: {"color":"#8A63B8","weight":2.5,"fillColor":"#8A63B8","fillOpacity":0.04},highlight_function=lambda _: {"weight":4,"fillOpacity":0.08},tooltip=folium.GeoJsonTooltip(fields=["name"],aliases=["Boundary"])).add_to(zone_layer)
        zone_layer.add_to(m)

    hotspot_group=folium.FeatureGroup(name="🔥 VIIRS Hotspots",show=True)
    if not hotspots.empty:
        for _,row in hotspots.iterrows():
            raw_conf=row.get("confidence")
            level={0:"LOW",1:"MODERATE",2:"HIGH"}.get(int(raw_conf) if pd.notna(raw_conf) else -1,"UNKNOWN") if live_mode else "HIGH" if float(raw_conf)>=85 else "MEDIUM" if float(raw_conf)>=70 else "LOW"
            confidence_text=level if live_mode else f"{float(raw_conf):.0f}%"
            color={"HIGH":"#E53935","MODERATE":"#F59E0B","MEDIUM":"#F59E0B","LOW":"#43A047"}.get(level,"#757575")
            source=str(row.get("source","NASA LANCE VIIRS")); date_text=str(row.get("date", ""))[:10]
            popup=(f"<b>🔥 VIIRS Active Fire</b><br>Date: {date_text}<br>Confidence: {confidence_text}<br>Source: {source}<br>Scope: {str(row.get('scope','SERPRO'))}<br>Coordinates: {float(row['lat']):.5f}, {float(row['lon']):.5f}")
            folium.CircleMarker(location=[float(row["lat"]),float(row["lon"])],radius=5.5,color=color,fill=True,fill_color=color,fill_opacity=.9,weight=1,popup=popup).add_to(hotspot_group)
    hotspot_group.add_to(m)

    # Monitoring points are shown only when backed by a live dataset.
    if monitoring_points is not None and not monitoring_points.empty and "is_live" in monitoring_points.columns:
        live_points=monitoring_points[monitoring_points["is_live"]==True]
        if not live_points.empty:
            point_group=folium.FeatureGroup(name="📍 Monitoring Points",show=True)
            for _,row in live_points.iterrows():
                folium.Marker(location=[row["lat"],row["lon"]],tooltip=row.get("id","Monitoring Point"),popup=f"<b>{row.get('id','Monitoring Point')}</b><br>{row.get('description','Live monitoring point')}",icon=folium.Icon(color="green",icon="leaf",prefix="fa")).add_to(point_group)
            point_group.add_to(m)

    target=project_zone if focus=="Carbon Project Zone" else project_area
    bounds=_bounds_from_geojson(target)
    if focus=="All Boundaries":
        ab=_bounds_from_geojson(project_area); zb=_bounds_from_geojson(project_zone)
        if ab and zb:
            bounds=[[min(ab[0][0],zb[0][0]),min(ab[0][1],zb[0][1])],[max(ab[1][0],zb[1][0]),max(ab[1][1],zb[1][1])]]
    if bounds: m.fit_bounds(bounds,padding=(18,18))
    folium.LayerControl(collapsed=False).add_to(m)
    return m
