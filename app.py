import streamlit as st
from streamlit_folium import st_folium
from utils.demo_data import load_demo_data
from utils.ui import setup_page
from utils.map import render_map

setup_page()
data = load_demo_data()

st.markdown('<div class="brand">🌿 SERPRO Climate & Carbon Monitoring</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Climate intelligence and spatial monitoring platform — MVP</div>', unsafe_allow_html=True)
st.markdown('<div class="status">● Demo data · Last update: 12 Aug 2026 20:00 WIB</div>', unsafe_allow_html=True)

cols = st.columns(6)
metrics = [("🌧 Rainfall", "245 mm", "+18% vs normal"), ("🌡 Temperature", "27.8 °C", "+0.6 °C anomaly"), ("💧 Wetness", "0.72", "+12% vs 7 days"), ("🔥 Hotspots", "17", "+6 vs previous 7D"), ("🌿 NDVI", "0.71", "+4.3% vs 7 days"), ("🟣 Carbon Risk", "68 / 100", "HIGH RISK")]
for col, (label, value, delta) in zip(cols, metrics):
    with col:
        st.markdown(f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="metric-delta">{delta}</div></div>', unsafe_allow_html=True)

st.markdown('<div class="section-title">Project WebGIS & Climate Risk</div>', unsafe_allow_html=True)
map_col, risk_col = st.columns([2.1, 1])
with map_col:
    st_folium(render_map(data["hotspots"], data["monitoring_points"]), width=None, height=480, returned_objects=[])
with risk_col:
    st.markdown('<div class="risk-card"><div>CLIMATE RISK INDEX</div><div class="risk-number">68</div><div class="risk-label">HIGH RISK</div><hr>', unsafe_allow_html=True)
    for label, value in data["risk_inputs"].items():
        st.markdown(f"**{label.replace('_', ' ').title()}** — {value:.2f}")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="section-title">Monitoring Trends</div>', unsafe_allow_html=True)
c1, c2, c3 = st.columns(3)
with c1:
    st.plotly_chart(data["rainfall_chart"], use_container_width=True, config={"displayModeBar": False})
with c2:
    st.plotly_chart(data["fire_chart"], use_container_width=True, config={"displayModeBar": False})
with c3:
    st.plotly_chart(data["ndvi_chart"], use_container_width=True, config={"displayModeBar": False})

st.markdown('<div class="section-title">Recent Alerts</div>', unsafe_allow_html=True)
for _, alert in data["alerts"].iterrows():
    priority = alert["Priority"]
    cls = "alert-high" if priority == "HIGH" else "alert-medium" if priority == "MEDIUM" else "alert-low"
    st.markdown(f'<div class="{cls}"><b>{alert["Type"]}</b> · {alert["Location"]} · {alert["Date"]} · <b>{priority}</b></div>', unsafe_allow_html=True)

st.caption("MVP note: all values and spatial layers are demo data. Official PT KAL/Seruyan project boundary and live satellite/climate feeds will be connected in the next phase.")
