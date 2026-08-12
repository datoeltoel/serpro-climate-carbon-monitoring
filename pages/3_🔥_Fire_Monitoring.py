import pandas as pd
import plotly.express as px
import folium
import streamlit as st
from streamlit_folium import st_folium

from utils.climate.fire import load_fire
from utils.map import load_carbon_project_zone, load_project_area
from utils.ui import setup_page

setup_page()

st.title("🔥 Fire Monitoring")
st.caption("SERPRO Project · NASA FIRMS near-real-time active fire monitoring")

fire = load_fire()
if fire.empty:
    st.info("Belum ada hotspot FIRMS. Jalankan **Update SERPRO Fire Monitoring** di GitHub Actions.")
    st.stop()

scope = st.selectbox(
    "Monitoring scope",
    ["carbon_project_zone", "project_area"],
    format_func=lambda x: {
        "carbon_project_zone": "Carbon Project Zone",
        "project_area": "Project Area",
    }[x],
)

scoped = fire[fire["scope"] == scope].copy().sort_values("date")
latest_date = scoped["date"].max()
last24 = scoped[scoped["date"] >= latest_date - pd.Timedelta(days=1)]
last7 = scoped[scoped["date"] >= latest_date - pd.Timedelta(days=6)]
last30 = scoped[scoped["date"] >= latest_date - pd.Timedelta(days=29)]

confidence_label = {0: "LOW", 1: "NOMINAL", 2: "HIGH"}
max_conf = int(scoped["confidence"].max()) if not scoped.empty else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Hotspots — 24H", f"{len(last24)}")
c2.metric("Hotspots — 7D", f"{len(last7)}")
c3.metric("Hotspots — 30D", f"{len(last30)}")
c4.metric("Highest confidence", confidence_label.get(max_conf, "—"))

st.info(f"**Latest available FIRMS observation:** {latest_date.date()} · **Source:** NASA FIRMS · **Nominal resolution:** 1 km · NRT data are intended for monitoring and are not science-quality products.")

# Live hotspot map
m = folium.Map(location=[-3.10, 112.62], zoom_start=9, tiles="CartoDB positron", control_scale=True)

zone = load_carbon_project_zone()
area = load_project_area()
if zone.get("features"):
    folium.GeoJson(zone, name="🟣 Carbon Project Zone", style_function=lambda _: {"color": "#6A4C93", "weight": 3, "fillColor": "#9B7EBD", "fillOpacity": 0.06}).add_to(m)
if area.get("features"):
    folium.GeoJson(area, name="🟢 Project Area", style_function=lambda _: {"color": "#146B43", "weight": 2, "fillColor": "#2E7D32", "fillOpacity": 0.03}).add_to(m)

hotspots_layer = folium.FeatureGroup(name="🔥 FIRMS Hotspots", show=True)
for _, row in last30.iterrows():
    conf = int(row["confidence"]) if pd.notna(row["confidence"]) else 0
    color = {0: "#9E9E9E", 1: "#F9A825", 2: "#D32F2F"}.get(conf, "#9E9E9E")
    folium.CircleMarker(
        location=[row["latitude"], row["longitude"]],
        radius=5,
        color=color,
        fill=True,
        fill_color=color,
        fill_opacity=0.85,
        popup=(f"<b>FIRMS hotspot</b><br>Date: {row['date'].date()}<br>"
               f"Confidence: {confidence_label.get(conf, 'UNKNOWN')}<br>"
               f"Brightness T21: {row['brightness_temperature_k']:.1f} K"),
    ).add_to(hotspots_layer)
hotspots_layer.add_to(m)
folium.LayerControl(collapsed=False).add_to(m)

st_folium(m, width=None, height=520, returned_objects=[])

st.subheader("Hotspot Trend")
daily = scoped.groupby("date", as_index=False).size().rename(columns={"size": "hotspots"})
fig = px.bar(daily, x="date", y="hotspots", title=f"Daily FIRMS hotspots · {scope.replace('_', ' ').title()}", labels={"date": "Date", "hotspots": "Hotspots"})
fig.update_layout(height=320, margin=dict(l=20, r=20, t=50, b=20))
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

st.subheader("Recent Hotspot Observations")
show = scoped.sort_values(["date", "confidence"], ascending=[False, False]).copy()
show["confidence"] = show["confidence"].map(confidence_label).fillna("UNKNOWN")
show = show.rename(columns={
    "date": "Date",
    "latitude": "Latitude",
    "longitude": "Longitude",
    "brightness_temperature_k": "Brightness T21 (K)",
    "confidence": "Confidence",
})[["Date", "Latitude", "Longitude", "Brightness T21 (K)", "Confidence"]]
st.dataframe(show.head(100), use_container_width=True, hide_index=True)

st.caption("Source: NASA/LANCE FIRMS in Google Earth Engine. FIRMS is near-real-time MODIS active-fire monitoring at approximately 1 km; use hotspot observations as alerts, not as direct burned-area measurements.")
