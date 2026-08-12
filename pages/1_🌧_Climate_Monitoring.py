import streamlit as st
from utils.demo_data import load_demo_data
from utils.ui import setup_page

setup_page()
data = load_demo_data()
st.title("🌧 Climate Monitoring")
st.caption("MVP analytical view — demo data")

c1, c2, c3 = st.columns(3)
c1.metric("Rainfall — latest", "84 mm", "+18% vs normal")
c2.metric("30-day cumulative", "507 mm", "+8%")
c3.metric("Temperature anomaly", "+0.6 °C", "Moderate")
st.plotly_chart(data["rainfall_chart"], use_container_width=True)
st.subheader("Rainfall Data")
st.dataframe(data["rainfall"], use_container_width=True, hide_index=True)
