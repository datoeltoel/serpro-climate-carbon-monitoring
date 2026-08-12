import streamlit as st
import plotly.express as px

from utils.climate.rainfall import load_rainfall
from utils.climate.anomaly import load_anomaly
from utils.ui import setup_page

setup_page()

st.title("🌧 Climate Monitoring")
st.caption("SERPRO Project · GPM IMERG current rainfall + CHIRPS 1991–2020 daily climatology")

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
source_label = {"NASA/GPM_L3/IMERG_V07": "NASA GPM IMERG V07"}.get(source, source)

st.info(f"**Latest available observation:** {latest_date.date()}  ·  **Source:** {source_label}  ·  **Processed:** {processed_at}")

if not anomaly.empty:
    scoped_anom = anomaly[anomaly["scope"] == scope].sort_values("date")
    if not scoped_anom.empty:
        a = scoped_anom.iloc[-1]
        status = str(a["climate_status"]).replace("_", " ").title()
        icon = {
            "Very Wet": "🟣",
            "Wet": "🔵",
            "Normal": "🟢",
            "Dry": "🟡",
            "Drought": "🔴",
            "Insufficient Data": "⚪",
        }.get(status, "⚪")
        st.subheader("Climate Condition")
        c0, c1, c2, c3 = st.columns(4)
        c0.metric("30-day status", f"{icon} {status}")
        if pd.notna(a.get("anomaly_30d_pct")):
            c1.metric("30-day anomaly", f"{float(a['anomaly_30d_pct']):+.1f}%")
        else:
            c1.metric("30-day anomaly", "—")
        c2.metric("7-day anomaly", f"{float(a['anomaly_7d_pct']):+.1f}%" if pd.notna(a.get("anomaly_7d_pct")) else "—")
        c3.metric("30-day observations", f"{int(a['obs_count_30d'])}/30")
        st.caption(
            "Baseline: CHIRPS v2 Final · 1991–2020 daily calendar-day climatology. "
            "Status is based on 30-day rainfall anomaly when a complete 30-day current window is available. SPI is not yet applied."
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

if not anomaly.empty:
    scoped_anom = anomaly[anomaly["scope"] == scope].sort_values("date")
    if not scoped_anom.empty:
        fig2 = px.line(
            scoped_anom,
            x="date",
            y="anomaly_30d_pct",
            markers=True,
            title="30-day rainfall anomaly vs CHIRPS 1991–2020 normal",
            labels={"date": "Date", "anomaly_30d_pct": "30-day anomaly (%)"},
        )
        fig2.add_hline(y=0, line_dash="dash")
        fig2.update_layout(height=320, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

        st.subheader("Anomaly Data")
        st.dataframe(
            scoped_anom[[
                "date", "rainfall_mm", "daily_normal_mean_mm", "daily_anomaly_pct",
                "rainfall_7d_mm", "normal_7d_mm", "anomaly_7d_pct",
                "rainfall_30d_mm", "normal_30d_mm", "anomaly_30d_pct",
                "obs_count_7d", "obs_count_30d", "climate_status"
            ]],
            use_container_width=True,
            hide_index=True,
        )

st.subheader("Scope Comparison")
comparison = rainfall.sort_values("date").groupby("scope", as_index=False).tail(1)[["scope", "date", "rainfall_mm", "source"]].copy()
comparison["scope"] = comparison["scope"].map({"carbon_project_zone": "Carbon Project Zone", "project_area": "Project Area"}).fillna(comparison["scope"])
comparison = comparison.rename(columns={"scope": "Scope", "date": "Latest Date", "rainfall_mm": "Latest Rainfall (mm)", "source": "Source"})
st.dataframe(comparison, use_container_width=True, hide_index=True)

st.caption("Current rainfall source: NASA GPM IMERG V07. Historical baseline: CHIRPS v2 Final 1991–2020. The dashboard reports only observations actually available in Earth Engine.")
