import streamlit as st
import plotly.express as px

from utils.climate.rainfall import load_rainfall
from utils.ui import setup_page

setup_page()

st.title("🌧 Climate Monitoring")
st.caption("SERPRO Project · automated rainfall monitoring")

rainfall = load_rainfall()

if rainfall.empty:
    st.warning(
        "Belum ada data rainfall otomatis. Jalankan workflow **Update SERPRO Rainfall** "
        "di GitHub Actions terlebih dahulu."
    )
    st.stop()

available_scopes = ["carbon_project_zone", "project_area"]
valid_scopes = [s for s in available_scopes if s in rainfall["scope"].unique()]

scope = st.selectbox(
    "Monitoring scope",
    valid_scopes,
    format_func=lambda x: {
        "carbon_project_zone": "Carbon Project Zone",
        "project_area": "Project Area",
    }.get(x, x.replace("_", " ").title()),
)

scoped = rainfall[rainfall["scope"] == scope].copy().sort_values("date")

latest_row = scoped.iloc[-1]
latest_date = latest_row["date"]
latest_value = float(latest_row["rainfall_mm"])
seven_day = float(scoped.tail(7)["rainfall_mm"].sum())

thirty_day = float(scoped.tail(30)["rainfall_mm"].sum())
source = str(latest_row["source"])
processed_at = str(latest_row["processing_time_utc"])

# Freshness/status banner
source_label = {
    "NASA/GPM_L3/IMERG_V07": "NASA GPM IMERG V07",
}.get(source, source)

st.info(
    f"**Latest available observation:** {latest_date.date()}  ·  "
    f"**Source:** {source_label}  ·  **Processed:** {processed_at}"
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Latest daily", f"{latest_value:.2f} mm")
c2.metric("7-day cumulative", f"{seven_day:.2f} mm")
c3.metric("30-day cumulative", f"{thirty_day:.2f} mm")
c4.metric("Observations", f"{len(scoped)}")

st.subheader("Daily Rainfall Trend")
fig = px.line(
    scoped,
    x="date",
    y="rainfall_mm",
    markers=True,
    title=f"Daily rainfall · {scope.replace('_', ' ').title()}",
    labels={"date": "Date", "rainfall_mm": "Rainfall (mm/day)"},
)
fig.update_layout(height=380, margin=dict(l=20, r=20, t=50, b=20))
fig.update_yaxes(rangemode="tozero")
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

st.subheader("Scope Comparison")
comparison = (
    rainfall.sort_values("date")
    .groupby("scope", as_index=False)
    .tail(1)[["scope", "date", "rainfall_mm", "source"]]
    .copy()
)
comparison["scope"] = comparison["scope"].map(
    {
        "carbon_project_zone": "Carbon Project Zone",
        "project_area": "Project Area",
    }
).fillna(comparison["scope"])
comparison = comparison.rename(
    columns={"scope": "Scope", "date": "Latest Date", "rainfall_mm": "Latest Rainfall (mm)", "source": "Source"}
)
st.dataframe(comparison, use_container_width=True, hide_index=True)

st.subheader("Processed Rainfall Data")
st.dataframe(scoped, use_container_width=True, hide_index=True)

st.caption(
    "Rainfall source: NASA GPM IMERG V07. The dashboard reports the latest observation actually available "
    "in Earth Engine; it does not assume that the latest calendar day is already published. "
    "Historical CHIRPS baseline/anomaly analysis will be added as a separate climate-baseline layer."
)
