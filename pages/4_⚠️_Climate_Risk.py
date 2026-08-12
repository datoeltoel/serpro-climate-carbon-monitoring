import pandas as pd
import streamlit as st

from utils.climate.risk import load_integrated_risk
from utils.ui import setup_page

setup_page()
st.title("⚠️ Climate Risk")
st.caption("SERPRO integrated climate screening · rainfall + drought + vegetation + fire")

risk = load_integrated_risk()
if risk.empty:
    st.info("Belum ada hasil Integrated Climate Risk. Jalankan **Build Integrated Climate Risk** di GitHub Actions.")
    st.stop()

scope = st.selectbox(
    "Monitoring scope",
    ["carbon_project_zone", "project_area"],
    format_func=lambda x: "Carbon Project Zone" if x == "carbon_project_zone" else "Project Area",
)

scoped = risk[risk["scope"] == scope].sort_values("date")
latest = scoped.iloc[-1]

level = str(latest["risk_level"]).replace("_", " ").upper()
score = float(latest["integrated_risk_score"])
basis = str(latest["risk_basis"]).upper()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Risk Level", level)
c2.metric("Risk Score", f"{score:.1f} / 15")
c3.metric("30D Rainfall Anomaly", f"{float(latest['rainfall_anomaly_30d_pct']):.1f}%")
c4.metric("FIRMS Hotspots 7D", f"{int(latest['hotspots_7d'])}")

st.subheader("Risk Components")
comp = pd.DataFrame({
    "Component": ["Rainfall", "Drought / SPI", "Vegetation / NDMI", "Fire"],
    "Score": [latest["rainfall_score"], latest["drought_score"], latest["vegetation_score"], latest["fire_score"]],
    "Maximum": [4, 4, 3, 4],
})
comp["Component Status"] = comp.apply(lambda r: f"{r['Score']:.0f} / {r['Maximum']:.0f}", axis=1)
st.dataframe(comp[["Component", "Component Status"]], use_container_width=True, hide_index=True)

st.subheader("Current Indicators")
indicators = pd.DataFrame({
    "Indicator": ["SPI-3", "SPI-6", "Latest NDMI", "NDMI change 30D", "Hotspot density / 10,000 ha"],
    "Value": [latest["spi_3"], latest["spi_6"], latest["ndmi_latest"], latest["ndmi_change_30d_pct"], latest["hotspot_density_7d_per_10kha"]],
})
st.dataframe(indicators, use_container_width=True, hide_index=True)

st.subheader("Risk Trend")
chart = scoped[["date", "integrated_risk_score"]].copy().set_index("date")
st.line_chart(chart)

st.caption(f"Assessment date: {latest['date'].date().isoformat()} · Basis: {basis} · Screening index only; not a calibrated fire-danger or carbon-accounting metric.")
