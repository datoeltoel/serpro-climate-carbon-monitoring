from pathlib import Path

PAGE = Path('pages/1_🌧_Climate_Monitoring.py')
MARKER = '# -----------------------------------------------------------------------------\n# Rainfall trend and anomaly\n# -----------------------------------------------------------------------------'
IMPORT = 'from utils.climate.bmkg import load_bmkg_forecast\n'
BLOCK = r'''# -----------------------------------------------------------------------------
# BMKG local weather intelligence
# -----------------------------------------------------------------------------
bmkg_df, bmkg_meta = load_bmkg_forecast()

st.markdown('<div class="section-title">📡 BMKG local weather outlook</div>', unsafe_allow_html=True)
st.markdown('<div class="section-note">Local 3-day forecast from BMKG for five monitoring locations. This is supporting climate evidence and does not replace the rainfall analysis pipeline.</div>', unsafe_allow_html=True)

if bmkg_df.empty:
    st.warning("BMKG forecast is temporarily unavailable. Existing climate analytics remain unchanged.")
else:
    locs = sorted(bmkg_df["location"].dropna().unique().tolist())
    selected_bmkg = st.selectbox("BMKG location", ["All locations"] + locs, key="bmkg_location")
    view = bmkg_df.copy() if selected_bmkg == "All locations" else bmkg_df[bmkg_df["location"] == selected_bmkg].copy()
    if not view.empty:
        latest = view.sort_values("local_datetime").groupby("location", as_index=False).tail(1)
        cols = st.columns(min(5, max(1, len(latest))))
        for col, (_, row) in zip(cols, latest.iterrows()):
            weather = row.get("weather_desc_en") or row.get("weather_desc") or "—"
            with col:
                st.metric(str(row["location"]), f"{row['temperature_c']:.1f} °C" if pd.notna(row.get("temperature_c")) else "—", weather)

        forecast_cols = ["location", "local_datetime", "temperature_c", "humidity_pct", "precipitation_mm", "wind_speed_ms", "wind_direction", "cloud_cover_pct", "weather_desc_en"]
        available = [c for c in forecast_cols if c in view.columns]
        forecast = view[available].sort_values(["location", "local_datetime"]).copy()
        forecast = forecast.rename(columns={
            "local_datetime": "Local time", "temperature_c": "Temp (°C)", "humidity_pct": "RH (%)",
            "precipitation_mm": "Precipitation (mm)", "wind_speed_ms": "Wind (m/s)",
            "wind_direction": "Wind direction", "cloud_cover_pct": "Cloud (%)", "weather_desc_en": "Weather"
        })
        st.dataframe(forecast, use_container_width=True, hide_index=True)
        st.caption("Source: BMKG Open Data · 3-day forecast · 3-hour interval · Forecast data is separate from historical rainfall/anomaly calculations.")
        q = bmkg_meta.get("quality")
        if q is not None and not q.empty:
            with st.expander("BMKG data quality & provenance"):
                st.dataframe(q, use_container_width=True, hide_index=True)
                st.write(f"Fetched (UTC): {bmkg_meta.get('fetched_at_utc', '—')}")
'''

text = PAGE.read_text(encoding='utf-8')
if IMPORT not in text:
    anchor = 'from utils.climate.risk import load_risk\n'
    if anchor not in text:
        raise SystemExit('Climate page import anchor not found')
    text = text.replace(anchor, anchor + IMPORT, 1)
if 'load_bmkg_forecast()' not in text:
    if MARKER not in text:
        raise SystemExit('Climate page insertion marker not found')
    text = text.replace(MARKER, BLOCK + '\n' + MARKER, 1)
PAGE.write_text(text, encoding='utf-8')
print('BMKG integration applied')
