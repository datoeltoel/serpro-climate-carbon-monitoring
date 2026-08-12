import pandas as pd
import streamlit as st
import plotly.express as px

from utils.climate.vegetation import load_ndmi
from utils.ui import setup_page

setup_page()

st.title("🌿 Vegetation Monitoring")
st.caption("SERPRO Project · Sentinel-2 NDMI")

ndmi = load_ndmi()
if ndmi.empty:
    st.info("Belum ada data NDMI. Jalankan **Update SERPRO NDMI** di GitHub Actions.")
    st.stop()

scopes = ["carbon_project_zone", "project_area"]
valid = [s for s in scopes if s in ndmi["scope"].unique()]
scope = st.selectbox(
    "Monitoring scope",
    valid,
    format_func=lambda x: {
        "carbon_project_zone": "Carbon Project Zone",
        "project_area": "Project Area",
    }.get(x, x.replace("_", " ").title()),
)

scoped = ndmi[ndmi["scope"] == scope].sort_values("date")
latest = scoped.iloc[-1]
latest_date = latest["date"]
latest_ndmi = float(latest["ndmi"])
cloud_pct = latest.get("cloudy_pixel_percentage")

c1, c2, c3 = st.columns(3)
c1.metric("Latest NDMI", f"{latest_ndmi:.3f}")
c2.metric("Observation", latest_date.date().isoformat())
c3.metric("Scene cloudiness", f"{float(cloud_pct):.1f}%" if pd.notna(cloud_pct) else "—")

st.subheader("NDMI Trend")
fig = px.line(
    scoped,
    x="date",
    y="ndmi",
    markers=True,
    title=f"Sentinel-2 NDMI · {scope.replace('_', ' ').title()}",
    labels={"date": "Date", "ndmi": "NDMI"},
)
fig.add_hline(y=0, line_dash="dash")
fig.update_layout(height=380, margin=dict(l=20, r=20, t=50, b=20))
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

st.subheader("Scope Comparison")
comparison = ndmi.sort_values("date").groupby("scope", as_index=False).tail(1)[
    ["scope", "date", "ndmi", "cloudy_pixel_percentage"]
].copy()
comparison["scope"] = comparison["scope"].map({
    "carbon_project_zone": "Carbon Project Zone",
    "project_area": "Project Area",
}).fillna(comparison["scope"])
comparison = comparison.rename(columns={
    "scope": "Scope",
    "date": "Latest Date",
    "ndmi": "Latest NDMI",
    "cloudy_pixel_percentage": "Scene Cloudiness (%)",
})
st.dataframe(comparison, use_container_width=True, hide_index=True)

st.caption("Source: COPERNICUS/S2_SR_HARMONIZED with COPERNICUS/S2_CLOUD_PROBABILITY cloud masking. NDMI = (B8 − B11) / (B8 + B11).")
