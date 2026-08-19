"""Enterprise spatial data catalog shell for GIS users."""
import streamlit as st

st.set_page_config(page_title="Spatial Data Catalog · SERPRO", page_icon="🗺️", layout="wide")

st.title("🗺️ Spatial Data Catalog")
st.caption("Enterprise entry point for spatial metadata, layer management and future GIS export services.")

c1, c2, c3 = st.columns(3)
c1.metric("Layer Registry", "Phase 1 shell")
c2.metric("Metadata", "Planned")
c3.metric("Spatial Export", "Existing utilities preserved")

st.markdown("### Catalog scope")
st.markdown("- Project Area and Carbon Project Zone\n- Climate raster and time-series outputs\n- Vegetation and fire layers\n- Monitoring boundaries and reference data\n- Dataset source, date, CRS, resolution and processing metadata")

st.info("Phase 1 defines the catalog interface only. PostGIS, relational metadata storage and dynamic spatial querying are explicitly deferred to Phase 3.")
