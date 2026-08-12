import folium
from folium.plugins import Fullscreen


def render_map(hotspots, monitoring_points):
    m = folium.Map(location=[-2.53, 112.72], zoom_start=10, tiles="CartoDB positron", control_scale=True)
    Fullscreen().add_to(m)
    folium.Rectangle(bounds=[[-2.70, 112.45], [-2.35, 113.00]], color="#0B5D3B", fill=True, fill_opacity=0.06, tooltip="Demo Project Boundary").add_to(m)

    hotspot_group = folium.FeatureGroup(name="🔥 VIIRS Hotspots")
    for _, row in hotspots.iterrows():
        level = "HIGH" if row["confidence"] >= 85 else "MEDIUM" if row["confidence"] >= 70 else "LOW"
        folium.CircleMarker(location=[row["lat"], row["lon"]], radius=6, color="#D32F2F" if level == "HIGH" else "#F9A825", fill=True, fill_opacity=0.85, popup=f"VIIRS hotspot<br>Confidence: {row['confidence']}%<br>Priority: {level}").add_to(hotspot_group)
    hotspot_group.add_to(m)

    point_group = folium.FeatureGroup(name="📍 Monitoring Points")
    for _, row in monitoring_points.iterrows():
        folium.Marker(location=[row["lat"], row["lon"]], tooltip=row["id"], popup=f"<b>{row['id']}</b><br>Demo monitoring point", icon=folium.Icon(color="green", icon="tint", prefix="fa")).add_to(point_group)
    point_group.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    return m
