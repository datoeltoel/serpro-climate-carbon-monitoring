import streamlit as st

from utils.scope_engine import get_scope


# -----------------------------------------------------------------------------
# Global project frame
# -----------------------------------------------------------------------------
project_area = get_scope("SERPRO Project Area")
project_zone = get_scope("SERPRO Carbon Project Zone")

with st.sidebar:
    st.markdown("### 🌿 PT KALAMANTHANA ALAM LESTARI")
    st.markdown("**CLIMATE & CARBON**  \n**MONITORING SYSTEM**")
    st.markdown("---")
    st.markdown("#### Project Info")
    st.markdown(f"**Carbon Project Zone**  \n{project_zone.area_ha:,.2f} ha")
    st.markdown(f"**Project Area**  \n{project_area.area_ha:,.2f} ha")
    st.markdown("**Location**  \nSeruyan, Central Kalimantan")
    st.markdown("**Status**  \nPrototype · Live connected")
    st.markdown("---")
    st.markdown("#### Data Sources")
    st.caption("GPM IMERG · CHIRPS · VIIRS S-NPP / NOAA-20 · Sentinel-2 · MODIS · BMKG Open Data")


def dashboard():
    st.markdown(
        """
        <div class="hero">
          <div class="eyebrow">SERPRO PROJECT · PT KALAMANTHANA ALAM LESTARI</div>
          <div class="title">🌿 Climate & Carbon Monitoring System</div>
          <div class="subtitle">Integrated monitoring workspace for historical climate, operational BMKG forecast, vegetation, fire and climate risk.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.info("Gunakan menu di sidebar. Climate Monitoring sekarang dipisahkan menjadi dua halaman: Historical Climate dan BMKG Local Weather Forecast.")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 📊 Historical Climate")
        st.caption("Rainfall, anomaly, SPI-3 / SPI-6, climate trend and historical climate-risk screening.")
        st.page_link("/historical_climate", label="Open Historical Climate", icon="📊")
    with c2:
        st.markdown("### 🌦️ BMKG Local Weather Forecast")
        st.caption("Operational 3-day BMKG ADM4 forecast and 1 km IDW spatial forecast surface.")
        st.page_link("/bmkg_local_weather_forecast", label="Open BMKG Local Weather Forecast", icon="🌦️")


pages = {
    "CLIMATE MONITORING": [
        st.Page("app_pages/historical_climate.py", title="Historical Climate", icon="📊", url_path="historical_climate", default=True),
        st.Page("app_pages/bmkg_local_weather_forecast.py", title="BMKG Local Weather Forecast", icon="🌦️", url_path="bmkg_local_weather_forecast"),
    ],
    "VEGETATION MONITORING": [
        st.Page("pages/2_🌿_Vegetation_Monitoring.py", title="Vegetation Monitoring", icon="🌿", url_path="vegetation_monitoring"),
    ],
    "FIRE MONITORING": [
        st.Page("pages/3_🔥_Fire_Monitoring.py", title="Fire Monitoring", icon="🔥", url_path="fire_monitoring"),
    ],
    "CLIMATE RISK": [
        st.Page("pages/4_⚠️_Climate_Risk.py", title="Climate Risk", icon="⚠️", url_path="climate_risk"),
    ],
}

pg = st.navigation(pages, position="sidebar", expanded=True)
pg.run()
