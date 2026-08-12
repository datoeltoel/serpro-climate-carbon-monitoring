import streamlit as st
from utils.demo_data import load_demo_data
from utils.ui import setup_page
from utils.map import render_map
from streamlit_folium import st_folium

setup_page()
data = load_demo_data()
st.title("🔥 Fire Monitoring")
st.caption("MVP fire activity view — demo hotspot data")

c1, c2, c3 = st.columns(3)
c1.metric("Hotspots — 24H", "3")
c2.metric("Hotspots — 7D", "17", "+6")
c3.metric("Highest confidence", "95%", "HIGH")

st_folium(render_map(data["hotspots"], data["monitoring_points"]), width=None, height=520, returned_objects=[])
st.plotly_chart(data["fire_chart"], use_container_width=True)
st.subheader("Hotspot Observations")
st.dataframe(data["hotspots"], use_container_width=True, hide_index=True)
