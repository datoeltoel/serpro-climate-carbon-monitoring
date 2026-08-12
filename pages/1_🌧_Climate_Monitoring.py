import streamlit as st
import plotly.express as px
from utils.climate.rainfall import load_rainfall, latest_by_scope
from utils.demo_data import load_demo_data
from utils.ui import setup_page

setup_page()
demo = load_demo_data()
rainfall = load_rainfall()

st.title("🌧 Climate Monitoring")

if rainfall.empty:
    st.info("CHIRPS pipeline is ready, but no automated rainfall file has been generated yet. Configure the Earth Engine GitHub Secrets and run the workflow once. Showing demo values below until then.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Rainfall — latest", "84 mm", "DEMO")
    c2.metric("30-day cumulative", "507 mm", "DEMO")
    c3.metric("Temperature anomaly", "+0.6 °C", "DEMO")
    st.plotly_chart(demo["rainfall_chart"], use_container_width=True)
    st.subheader("Demo Rainfall Data")
    st.dataframe(demo["rainfall"], use_container_width=True, hide_index=True)
else:
    latest = latest_by_scope(rainfall)
    available_scopes = ["carbon_project_zone", "project_area"]
    scope = st.selectbox("Rainfall scope", available_scopes, format_func=lambda x: x.replace("_", " ").title())
    scoped = rainfall[rainfall["scope"] == scope].copy()
    scoped = scoped.sort_values("date")
    latest_value = float(scoped.iloc[-1]["rainfall_mm"])
    seven_day = float(scoped.tail(7)["rainfall_mm"].sum())
    st.caption(f"Source: CHIRPS v3 Daily NRT · Latest processed date: {scoped.iloc[-1]['date'].date()}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Rainfall — latest", f"{latest_value:.1f} mm")
    c2.metric("7-day cumulative", f"{seven_day:.1f} mm")
    c3.metric("Records", f"{len(scoped)}")
    fig = px.line(scoped, x="date", y="rainfall_mm", markers=True, title=f"Daily rainfall — {scope.replace('_', ' ').title()}")
    fig.update_layout(height=360, margin=dict(l=20, r=20, t=50, b=20))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.subheader("Processed Rainfall Data")
    st.dataframe(scoped, use_container_width=True, hide_index=True)
