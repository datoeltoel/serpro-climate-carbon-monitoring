import pandas as pd
import plotly.express as px
import folium
import streamlit as st
from streamlit_folium import st_folium

from utils.climate.fire import load_fire, build_field_alerts, CONFIDENCE_LABEL
from utils.map import load_carbon_project_zone, load_project_area
from utils.ui import setup_page

setup_page()

st.title("🔥 Fire Monitoring")
st.caption("SERPRO Project · NASA LANCE VIIRS 375 m near-real-time active fire monitoring")

fire = load_fire()
if fire.empty:
    st.info("Belum ada hotspot VIIRS. Jalankan **Update SERPRO Fire Monitoring** di GitHub Actions.")
    st.stop()

scope = st.selectbox(
    "Monitoring scope",
    ["carbon_project_zone", "project_area"],
    format_func=lambda x: {
        "carbon_project_zone": "🟣 Carbon Project Zone",
        "project_area": "🟢 Project Area",
    }[x],
)

scoped = fire[fire["scope"] == scope].copy().sort_values("date")
latest_date = scoped["date"].max()
last24 = scoped[scoped["date"] >= latest_date - pd.Timedelta(days=1)]
last7 = scoped[scoped["date"] >= latest_date - pd.Timedelta(days=6)]
last30 = scoped[scoped["date"] >= latest_date - pd.Timedelta(days=29)]

low7 = int((last7["confidence"] == 0).sum())
moderate7 = int((last7["confidence"] == 1).sum())
high7 = int((last7["confidence"] == 2).sum())

c1, c2, c3, c4 = st.columns(4)
c1.metric("Hotspots — 24H", f"{len(last24)}")
c2.metric("Hotspots — 7D", f"{len(last7)}")
c3.metric("High confidence — 7D", f"{high7}")
c4.metric("Latest observation", latest_date.date().isoformat())

# Operational confidence legend
st.markdown("### Confidence & operational response")
legend_cols = st.columns(3)
legend = [
    ("LOW", "#9E9E9E", low7, "WATCH", "Retain for monitoring; no immediate field dispatch."),
    ("MODERATE", "#F9A825", moderate7, "VERIFY", "Review satellite context and nearby reports."),
    ("HIGH", "#D32F2F", high7, "FIELD ALERT", "Prioritize ground verification / patrol follow-up."),
]
for col, (label, color, count, action, text) in zip(legend_cols, legend):
    with col:
        st.markdown(
            f"<div style='border-left:6px solid {color};padding:12px 14px;border-radius:8px;background:#FAFBFA;'>"
            f"<b style='color:{color}'>{label}</b><br><span style='font-size:1.5rem;font-weight:800'>{count}</span> hotspots (7D)"
            f"<br><span style='font-weight:700'>{action}</span><br><span style='font-size:.78rem;color:#65736D'>{text}</span></div>",
            unsafe_allow_html=True,
        )

st.info(
    f"**Latest available VIIRS observation:** {latest_date.date()} · **Sources:** NASA LANCE VIIRS S-NPP + NOAA-20 · "
    "**Resolution:** 375 m · Confidence is source-native (Low / Nominal / High); SERPRO displays Nominal as Moderate. "
    "Hotspots are satellite detections and must be verified in the field."
)

# Field alerts
alerts = build_field_alerts(scoped, latest_date)
st.markdown("### 🚨 Field Follow-up Alerts")
if alerts.empty:
    st.success("No high-confidence hotspot detected on the latest available observation day for the selected scope.")
else:
    for _, a in alerts.iterrows():
        if a["priority"] == "HIGH":
            st.error(
                f"**HIGH PRIORITY — FIELD ALERT** · {a['date'].date()} · {a['scope'].replace('_', ' ').title()} · "
                f"{a['latitude']:.5f}, {a['longitude']:.5f} · {a['source']} · Confidence HIGH\n\n{a['action']}"
            )
        else:
            st.warning(
                f"**MODERATE PRIORITY — VERIFY** · {a['date'].date()} · {a['scope'].replace('_', ' ').title()} · "
                f"{a['latitude']:.5f}, {a['longitude']:.5f} · {a['source']}"
            )

# Map
m = folium.Map(location=[-3.10, 112.62], zoom_start=9, tiles="CartoDB positron", control_scale=True)
zone = load_carbon_project_zone()
area = load_project_area()
if zone.get("features"):
    folium.GeoJson(
        zone, name="🟣 Carbon Project Zone",
        style_function=lambda _: {"color": "#6A4C93", "weight": 3, "fillColor": "#9B7EBD", "fillOpacity": 0.06},
    ).add_to(m)
if area.get("features"):
    folium.GeoJson(
        area, name="🟢 Project Area",
        style_function=lambda _: {"color": "#146B43", "weight": 2.5, "fillColor": "#2E7D32", "fillOpacity": 0.03},
    ).add_to(m)

hotspots_layer = folium.FeatureGroup(name="🔥 VIIRS Hotspots", show=True)
for _, row in last30.iterrows():
    conf = int(row["confidence"]) if pd.notna(row["confidence"]) else 0
    label = CONFIDENCE_LABEL.get(conf, "UNKNOWN")
    display_label = "MODERATE" if label == "NOMINAL" else label
    color = {0: "#9E9E9E", 1: "#F9A825", 2: "#D32F2F"}.get(conf, "#9E9E9E")
    folium.CircleMarker(
        location=[row["latitude"], row["longitude"]],
        radius=6 if conf == 2 else 5,
        color=color,
        fill=True,
        fill_color=color,
        fill_opacity=0.9,
        popup=(
            f"<b>VIIRS Active Fire</b><br>Date: {row['date'].date()}<br>"
            f"Confidence: {display_label}<br>Source: {row['source']}<br>"
            f"TI4: {row['brightness_ti4_k']:.1f} K<br>"
            f"Location: {row['latitude']:.5f}, {row['longitude']:.5f}"
        ),
    ).add_to(hotspots_layer)
hotspots_layer.add_to(m)
folium.LayerControl(collapsed=False).add_to(m)
st_folium(m, width=None, height=540, returned_objects=[])

st.markdown("### Hotspot Trend")
daily = scoped.groupby(["date", "confidence"], as_index=False).size().rename(columns={"size": "hotspots"})
daily["confidence_label"] = daily["confidence"].map({0: "LOW", 1: "MODERATE", 2: "HIGH"})
fig = px.bar(
    daily,
    x="date",
    y="hotspots",
    color="confidence_label",
    barmode="stack",
    title=f"Daily VIIRS hotspots · {scope.replace('_', ' ').title()}",
    labels={"date": "Date", "hotspots": "Hotspots", "confidence_label": "Confidence"},
)
fig.update_layout(height=340, margin=dict(l=20, r=20, t=50, b=20))
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

st.markdown("### Recent Hotspot Observations")
show = scoped.sort_values(["date", "confidence"], ascending=[False, False]).copy()
show["Confidence"] = show["confidence"].map({0: "LOW", 1: "MODERATE", 2: "HIGH"})
show = show.rename(columns={
    "date": "Date",
    "latitude": "Latitude",
    "longitude": "Longitude",
    "brightness_ti4_k": "TI4 (K)",
    "brightness_ti5_k": "TI5 (K)",
    "source": "Source",
})[["Date", "Latitude", "Longitude", "TI4 (K)", "TI5 (K)", "Confidence", "Source"]]
st.dataframe(show.head(200), use_container_width=True, hide_index=True)

st.caption(
    "Source: NASA/LANCE VIIRS C2. VIIRS NRT active-fire products use native Low/Nominal/High confidence classes at 375 m. "
    "SERPRO maps Nominal to Moderate for operational display. High-confidence detections trigger field follow-up alerts; they are not treated as confirmed ground fires."
)
