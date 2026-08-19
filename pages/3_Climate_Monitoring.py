"""Enterprise Climate Monitoring landing page."""
import streamlit as st

st.set_page_config(page_title="Climate Monitoring · SERPRO", page_icon="🌦️", layout="wide")

st.title("🌦️ Climate Monitoring")
st.caption("Unified enterprise entry point for historical climate and operational weather monitoring.")

c1, c2 = st.columns(2, gap="large")
with c1:
    st.subheader("Historical Climate")
    st.write("Long-term climate evidence, including the existing CHIRPS historical rainfall workflow, remains the operational analytical source.")
    st.page_link("app_pages/historical_climate.py", label="Open Historical Climate", icon="📊")
with c2:
    st.subheader("BMKG Local Weather Forecast")
    st.write("Operational local weather forecast remains the authoritative BMKG-facing module and is preserved during the enterprise refactor.")
    st.page_link("app_pages/bmkg_local_weather_forecast.py", label="Open BMKG Local Weather Forecast", icon="🌦️")

st.markdown("### Architecture mapping")
st.markdown("**Climate Monitoring enterprise page** → **Historical Climate** + **BMKG Local Weather Forecast**")
st.info("Fire Monitoring and Climate Risk remain separate operational monitoring domains in Phase 1 and are preserved without recalculation.")
