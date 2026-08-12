import streamlit as st
from utils.demo_data import load_demo_data
from utils.ui import setup_page

setup_page()
data = load_demo_data()
st.title("🌿 Vegetation Monitoring")
st.caption("MVP vegetation condition view — demo Sentinel-2-style NDVI data")

c1, c2, c3 = st.columns(3)
c1.metric("Current NDVI", "0.71", "+4.3%")
c2.metric("7-day change", "+0.09", "Improving")
c3.metric("Vegetation status", "GOOD")
st.plotly_chart(data["ndvi_chart"], use_container_width=True)
st.subheader("NDVI Observations")
st.dataframe(data["ndvi"], use_container_width=True, hide_index=True)
