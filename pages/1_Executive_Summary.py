"""Enterprise management landing page for SERPRO MRV."""
import streamlit as st

st.set_page_config(page_title="Executive Summary · SERPRO", page_icon="📊", layout="wide")

st.title("📊 Executive Summary")
st.caption("Enterprise management view. Phase 1 establishes the application shell; domain KPI engines remain in their existing modules.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Project Area", "Operational")
c2.metric("Climate Monitoring", "Active")
c3.metric("Vegetation Monitoring", "Active")
c4.metric("MRV Platform", "Phase 1")

st.markdown("### Monitoring domains")
st.info(
    "This page is the enterprise landing layer. Historical Climate, BMKG Local Weather Forecast, "
    "Vegetation Monitoring, Fire Monitoring and Climate Risk remain the authoritative operational modules "
    "and are not recalculated or replaced by this refactor."
)

st.markdown("### Architecture mapping")
for label, target in [
    ("Climate Monitoring", "Historical Climate + BMKG Local Weather Forecast"),
    ("MRV Carbon Tracker", "Future carbon accounting, LULC, AGB, SOC and carbon-pool integration"),
    ("Spatial Data Catalog", "Future metadata, layer management and GIS export integration"),
]:
    st.markdown(f"**{label}** → {target}")
