import streamlit as st
import plotly.express as px

from utils.climate.rainfall import load_rainfall
from utils.climate.anomaly import load_anomaly
from utils.ui import setup_page

setup_page()

st.title("🌧 Climate Monitoring")
st.caption("SERPRO Project · GPM IMERG current rainfall + CHIRPS 1991–2020 climate normal")

rainfall = load_rainfall()
anomaly = load_anomaly()

if rainfall.empty:
    st.warning("Belum ada data rainfall otomatis. Jalankan workflow **Update SERPRO Rainfall** di GitHub Actions terlebih dahulu.")
    st.stop()

available_scopes = ["carbon_project_zone", "project_area"]
valid_scopes = [s for s in available_scopes if s in rainfall["scope"].unique()]

scope = st.selectbox(
    "Monitoring scope",
    valid_scopes,
    format_func=lambda x: {"carbon_project_zone": "Carbon Project Zone", "project_area": "Project Area"}.get(x, x.replace("_", " ").title()),
)

scoped = rainfall[rainfall["scope"] == scope].copy().sort_values("date")
latest_row = scoped.iloc[-1]
latest_date = latest_row["date"]
latest_value = float(latest_row["rainfall_mm"])
seven_day = float(scoped.tail(7)["rainfall_mm"].sum())
thirty_day = float(scoped.tail(30)["rainfall_mm"].sum())
source = str(latest_row["source"])
processed_at = str(latest_row["processing_time_utc"])
source_label = {"NASA/GPM_L3/IMERG_V07": "NASA GPM IMERG V07"}.get(source, source)

st.info(f"**Latest available observation:** {latest_date.date()}  ·  **Source:** {source_label}  ·  **Processed:** {processed_at}")

if not anomaly.empty:
    scoped_anom = anomaly[anomaly["scope"] == scope].sort_values("date")
    if not scoped_anom.empty:
        a = scoped_anom.iloc[-1]
        status = str(a["climate_status"]).replace("_", " ").title()
        anomaly_pct = float(a["anomaly_pct"])
        z_score = float(a["z_score"])
        percentile = float(a["percentile_estimate"])
        icon = {"Very Wet": "🟣", "Wet": "🔵", "Normal": "🟢", "Dry": "🟡", "Drought": "🔴"}.get(status, "⚪")
        st.subheader("Climate Condition")
        c0, c1, c2, c3 = st.columns(4)
        c0.metric("Status", f"{icon} {status}")
        c1.metric("Rainfall anomaly", f"{anomaly_pct:+.1f}%")
        c2.metric("Z-score", f"{z_score:+.2f}")
        c3.metric("Estimated percentile", f"P{percentile:.0f}")
        st.caption("Baseline: CHIRPS v2 Final · 1991–2020 monthly climatology. Status uses anomaly-percentage classes; SPI is not yet applied.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Latest daily", f"{latest_value:.2f} mm")
c2.metric("7-day cumulative", f"{seven_day:.2f} mm")
c3.metric("30-day cumulative", f"{thirty_day:.2f} mm")
c4.metric("Observations", f"{len(scoped)}")

st.subheader("Daily Rainfall Trend")
fig = px.line(scoped, x="date", y="rainfall_mm", markers=True, title=f"Daily rainfall · {scope.replace('_', ' ').title()}", labels={"date": "Date", "rainfall_mm": "Rainfall (mm/day)"})
fig.update_layout(height=380, margin=dict(l=20, r=20, t=50, b=20))
fig.update_yaxes(rangemode="tozero")
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

if not anomaly.empty:
    scoped_anom = anomaly[anomaly["scope"] == scope].sort_values("date")
    if not scoped_anom.empty:
        fig2 = px.line(scoped_anom, x="date", y="anomaly_pct", markers=True, title="Rainfall anomaly vs CHIRPS 1991–2020 normal", labels={"date": "Date", "anomaly_pct": "Anomaly (%)"})
        fig2.add_hline(y=0, line_dash="dash")
        fig2.update_layout(height=320, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

st.subheader("Scope Comparison")
comparison = rainfall.sort_values("date").groupby("scope", as_index=False).tail(1)[["scope", "date", "rainfall_mm", "source"]].copy()
comparison["scope"] = comparison["scope"].map({"carbon_project_zone": "Carbon Project Zone", "project_area": "Project Area"}).fillna(comparison["scope"])
comparison = comparison.rename(columns={"scope": "Scope", "date": "Latest Date", "rainfall_mm": "Latest Rainfall (mm)", "source": "Source"})
st.dataframe(comparison, use_container_width=True, hide_index=True)

st.subheader("Processed Rainfall Data")
st.dataframe(scoped, use_container_width=True, hide_index=True)

st.caption("Current rainfall source: NASA GPM IMERG V07. Historical baseline: CHIRPS v2 Final. The dashboard reports the latest observation actually available in Earth Engine.")
