import streamlit as st

from utils.auth import require_authentication, require_role
from utils.enterprise_ui import apply_enterprise_css, hero, render_split_map_analysis

st.set_page_config(page_title="SERPRO · Spatial Data Catalog", page_icon="🗺️", layout="wide")
apply_enterprise_css()
require_authentication()
require_role("gis_specialist", "mrv_specialist")

hero(
    "🗺️ Spatial Data Catalog",
    "GIS workspace for dataset metadata, layer governance, provenance and reproducible exports.",
)

with st.expander("Catalog filters", expanded=True):
    f1, f2, f3 = st.columns(3)
    with f1:
        st.selectbox("Theme", ["All", "Carbon", "Climate", "Vegetation", "Fire", "Administrative"], key="catalog_theme")
    with f2:
        st.selectbox("Data type", ["All", "Raster", "Vector", "Table", "Time series"], key="catalog_type")
    with f3:
        st.selectbox("Status", ["All", "Production", "Validated", "Prototype"], key="catalog_status")

render_split_map_analysis(
    map_title="Catalog spatial preview",
    map_key="spatial_catalog_map",
)
