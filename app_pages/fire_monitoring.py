import pandas as pd
import plotly.express as px
import folium
import streamlit as st
from streamlit_folium import st_folium

from utils.climate.fire import load_fire, build_field_alerts, CONFIDENCE_LABEL
from utils.climate.burned_area import load_burned_area
from utils.climate.hotspot_history import load_hotspot_history
from utils.map import load_carbon_project_zone, load_project_area
from utils.ui import setup_page

setup_page()

st.title("🔥 Fire Monitoring")
st.caption("SERPRO Project · NASA LANCE VIIRS 375 m near-real-time active fire monitoring")

fire = load_fire()
if fire.empty:
    st.info("Belum ada hotspot VIIRS. Jalankan **Update SERPRO Fire Monitoring** di GitHub Actions.")
    st.stop()

fire["date"] = pd.to_datetime(fire["date"], errors="coerce")
fire = fire.dropna(subset=["date"])

scope = st.selectbox(
    "Monitoring scope",
    ["carbon_project_zone", "project_area"],
    format_func=lambda x: {
        "carbon_project_zone": "🟣 Carbon Project Zone",
        "project_area": "🟢 Project Area",
    }[x],
)

scoped_all = fire[fire["scope"] == scope].copy().sort_values("date")
if scoped_all.empty:
    st.warning("Belum ada data hotspot untuk scope yang dipilih.")
    st.stop()

min_date = scoped_all["date"].min().date()
max_date = scoped_all["date"].max().date()

st.markdown("### 📅 Monitoring Date Filter")
f1, f2, f3 = st.columns([1, 1, 1])
with f1:
    start_date = st.date_input("Start date", value=min_date, min_value=min_date, max_value=max_date)
with f2:
    end_date = st.date_input("End date", value=max_date, min_value=min_date, max_value=max_date)
with f3:
    preset = st.selectbox("Quick range", ["Custom", "Latest 24H", "Latest 7D", "Latest 30D"])

if preset != "Custom":
    end_date = max_date
    days = {"Latest 24H": 1, "Latest 7D": 7, "Latest 30D": 30}[preset]
    start_date = max(min_date, max_date - pd.Timedelta(days=days - 1))

if start_date > end_date:
    st.error("Start date harus lebih kecil atau sama dengan End date.")
    st.stop()

scoped = scoped_all[
    (scoped_all["date"].dt.date >= start_date)
    & (scoped_all["date"].dt.date <= end_date)
].copy()

# Source filter for the map and current-period hotspot displays.
source_options = sorted(scoped["source"].dropna().astype(str).unique().tolist())
if source_options:
    st.markdown("### 🛰️ Fire Monitoring Data Source")
    selected_sources = st.multiselect(
        "Show hotspot sources on the map",
        options=source_options,
        default=source_options,
        format_func=lambda s: {
            "VIIRS-SNPP": "NASA VIIRS S-NPP",
            "VIIRS-NOAA20": "NASA VIIRS NOAA-20",
            "MODIS-TERRA": "MODIS Terra",
            "MODIS-AQUA": "MODIS Aqua",
        }.get(s, s),
        help="Filter only the hotspot detections displayed on the map and current-period hotspot summaries.",
    )
    scoped = scoped[scoped["source"].astype(str).isin(selected_sources)].copy()
    if scoped.empty:
        st.warning("Tidak ada hotspot untuk source yang dipilih pada periode monitoring ini.")
        st.stop()

selected_latest = scoped["date"].max() if not scoped.empty else pd.Timestamp(end_date)
last24 = scoped[scoped["date"] >= selected_latest - pd.Timedelta(days=1)]
last7 = scoped[scoped["date"] >= selected_latest - pd.Timedelta(days=6)]
last30 = scoped[scoped["date"] >= selected_latest - pd.Timedelta(days=29)]

low7 = int((last7["confidence"] == 0).sum())
moderate7 = int((last7["confidence"] == 1).sum())
high7 = int((last7["confidence"] == 2).sum())

c1, c2, c3, c4 = st.columns(4)
c1.metric("Hotspots — selected range", f"{len(scoped)}")
c2.metric("Hotspots — last 7D", f"{len(last7)}")
c3.metric("High confidence — last 7D", f"{high7}")
c4.metric("Latest selected observation", selected_latest.date().isoformat())

st.markdown("### Confidence & operational response")
legend_cols = st.columns(3)
legend = [
    ("LOW", "#9E9E9E", low7, "WATCH", "Retain for monitoring; no immediate field dispatch."),
    ("MODERATE", "#F9A825", moderate7, "VERIFY", "Review satellite context and nearby reports."),
    ("HIGH", "#D32F2F", high7, "FIELD ALERT", "Prioritize ground verification / patrol follow-up."),
]
for col, (label, color, count, action, text) in zip(legend_cols, legend):
    with col:
        st.markdown(
            f"<div style='border-left:6px solid {color};padding:12px 14px;border-radius:8px;background:#FAFBFA;'>"
            f"<b style='color:{color}'>{label}</b><br><span style='font-size:1.5rem;font-weight:800'>{count}</span> hotspots (7D)"
            f"<br><span style='font-weight:700'>{action}</span><br><span style='font-size:.78rem;color:#65736D'>{text}</span></div>",
            unsafe_allow_html=True,
        )

st.info(
    f"**Latest available selected observation:** {selected_latest.date()} · **Sources:** {', '.join(selected_sources) if source_options else 'VIIRS'} · "
    "**Resolution:** 375 m · Confidence is source-native (Low / Nominal / High); SERPRO displays Nominal as Moderate. "
    "Hotspots are satellite detections and must be verified in the field."
)

alerts = build_field_alerts(scoped, selected_latest)
st.markdown("### 🚨 Field Follow-up Alerts")
if alerts.empty:
    st.success("No high-confidence hotspot detected on the latest selected observation day for the selected scope.")
else:
    for _, a in alerts.iterrows():
        if a["priority"] == "HIGH":
            st.error(
                f"**HIGH PRIORITY — FIELD ALERT** · {a['date'].date()} · {a['scope'].replace('_', ' ').title()} · "
                f"{a['latitude']:.5f}, {a['longitude']:.5f} · {a['source']} · Confidence HIGH\n\n{a['action']}"
            )
        else:
            st.warning(
                f"**MODERATE PRIORITY — VERIFY** · {a['date'].date()} · {a['scope'].replace('_', ' ').title()} · "
                f"{a['latitude']:.5f}, {a['longitude']:.5f} · {a['source']}"
            )

st.markdown("### 🗺️ SERPRO Fire Monitoring Map")
st.caption("Live/near-real-time VIIRS hotspot map for the selected monitoring period and selected source(s). Purple = Carbon Project Zone; green = Project Area; gray/yellow/red = Low/Moderate/High confidence.")
m = folium.Map(location=[-3.10, 112.62], zoom_start=9, tiles="CartoDB positron", control_scale=True)
zone = load_carbon_project_zone()
area = load_project_area()
if zone.get("features"):
    folium.GeoJson(
        zone, name="🟣 Carbon Project Zone",
        style_function=lambda _: {"color": "#6A4C93", "weight": 3, "fillColor": "#9B7EBD", "fillOpacity": 0.06},
    ).add_to(m)
if area.get("features"):
    folium.GeoJson(
        area, name="🟢 Project Area",
        style_function=lambda _: {"color": "#146B43", "weight": 2.5, "fillColor": "#2E7D32", "fillOpacity": 0.03},
    ).add_to(m)

hotspots_layer = folium.FeatureGroup(name="🔥 VIIRS Hotspots", show=True)
for _, row in scoped.iterrows():
    conf = int(row["confidence"]) if pd.notna(row["confidence"]) else 0
    label = CONFIDENCE_LABEL.get(conf, "UNKNOWN")
    display_label = "MODERATE" if label == "NOMINAL" else label
    color = {0: "#9E9E9E", 1: "#F9A825", 2: "#D32F2F"}.get(conf, "#9E9E9E")
    ti4 = row.get("brightness_ti4_k")
    ti4_text = f"{float(ti4):.1f} K" if pd.notna(ti4) else "—"
    folium.CircleMarker(
        location=[row["latitude"], row["longitude"]],
        radius=6 if conf == 2 else 5,
        color=color,
        fill=True,
        fill_color=color,
        fill_opacity=0.9,
        popup=(
            f"<b>VIIRS Active Fire</b><br>Date: {row['date'].date()}<br>"
            f"Confidence: {display_label}<br>Source: {row['source']}<br>"
            f"TI4: {ti4_text}<br>"
            f"Location: {row['latitude']:.5f}, {row['longitude']:.5f}"
        ),
    ).add_to(hotspots_layer)
hotspots_layer.add_to(m)
folium.LayerControl(collapsed=False).add_to(m)
st_folium(m, width=None, height=560, returned_objects=[])

st.markdown("### Hotspot Trend — Selected Monitoring Period")
daily = scoped.groupby(["date", "confidence"], as_index=False).size().rename(columns={"size": "hotspots"})
daily["confidence_label"] = daily["confidence"].map({0: "LOW", 1: "MODERATE", 2: "HIGH"})
fig = px.bar(
    daily,
    x="date",
    y="hotspots",
    color="confidence_label",
    barmode="stack",
    title=f"Daily VIIRS hotspots · {scope.replace('_', ' ').title()} · {start_date} to {end_date}",
    labels={"date": "Date", "hotspots": "Hotspots", "confidence_label": "Confidence"},
)
fig.update_layout(height=340, margin=dict(l=20, r=20, t=50, b=20))
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

st.markdown("### 📈 Historical Hotspot Trend — 2017–2025")
history = load_hotspot_history()
if history.empty:
    st.info("Belum ada historical hotspot trend. Jalankan **Update SERPRO Hotspot History** di GitHub Actions.")
else:
    hist_scope = history[history["scope"] == scope].copy().sort_values("year")
    if not hist_scope.empty:
        h1, h2, h3 = st.columns(3)
        peak_row = hist_scope.loc[hist_scope["hotspot_detections"].idxmax()]
        h1.metric("9Y total detections", f"{hist_scope['hotspot_detections'].sum():,.0f}")
        h2.metric("Annual average", f"{hist_scope['hotspot_detections'].mean():,.0f}")
        h3.metric("Peak year", f"{int(peak_row['year'])}", f"{int(peak_row['hotspot_detections']):,}")

        hist_fig = px.bar(
            hist_scope,
            x="year",
            y="hotspot_detections",
            title=f"Annual MODIS Terra fire-pixel detections · {scope.replace('_', ' ').title()} · 2017–2025",
            labels={"year": "Year", "hotspot_detections": "Fire-pixel detections"},
            text_auto=".0f",
        )
        hist_fig.update_layout(height=380, margin=dict(l=20, r=20, t=55, b=20))
        st.plotly_chart(hist_fig, use_container_width=True, config={"displayModeBar": False})
        st.caption("Historical trend source: MODIS Terra MOD14A1.061, 1 km daily FireMask. FireMask classes 7–9 are counted as fire detections. This historical indicator is not directly equivalent to VIIRS 375 m hotspot counts or burned area.")

st.markdown("### 🔥 Burned Area Trend — 10 Years")
burn = load_burned_area()
if burn.empty:
    st.info("Belum ada historical burned-area data. Jalankan **Update SERPRO Burned Area History** di GitHub Actions.")
else:
    burn_scope = burn[burn["scope"] == scope].copy().sort_values("year")
    if not burn_scope.empty:
        total_10y = burn_scope["burned_area_ha"].sum()
        avg_10y = burn_scope["burned_area_ha"].mean()
        peak = burn_scope.loc[burn_scope["burned_area_ha"].idxmax()]
        b1, b2, b3 = st.columns(3)
        b1.metric("10Y total burned area", f"{total_10y:,.1f} ha")
        b2.metric("10Y annual average", f"{avg_10y:,.1f} ha/year")
        b3.metric("Peak year", f"{int(peak['year'])}", f"{peak['burned_area_ha']:,.1f} ha")

        burn_fig = px.bar(
            burn_scope,
            x="year",
            y="burned_area_ha",
            title=f"Annual burned area · {scope.replace('_', ' ').title()} · 2016–2025",
            labels={"year": "Year", "burned_area_ha": "Burned area (ha)"},
            text_auto=".0f",
        )
        burn_fig.update_layout(height=380, margin=dict(l=20, r=20, t=55, b=20))
        st.plotly_chart(burn_fig, use_container_width=True, config={"displayModeBar": False})
        st.caption("Source: MODIS MCD64A1 v6.1 monthly burned-area product at 500 m. Trend uses ten complete calendar years (2016–2025); 2026 is excluded because the current year is incomplete.")

st.markdown("### Recent Hotspot Observations")
show = scoped.sort_values(["date", "confidence"], ascending=[False, False]).copy()
show["Confidence"] = show["confidence"].map({0: "LOW", 1: "MODERATE", 2: "HIGH"})
show = show.rename(columns={
    "date": "Date",
    "latitude": "Latitude",
    "longitude": "Longitude",
    "brightness_ti4_k": "TI4 (K)",
    "brightness_ti5_k": "TI5 (K)",
    "source": "Source",
})
for col in ["TI4 (K)", "TI5 (K)"]:
    if col not in show.columns:
        show[col] = None
show = show[["Date", "Latitude", "Longitude", "TI4 (K)", "TI5 (K)", "Confidence", "Source"]]
st.dataframe(show.head(200), use_container_width=True, hide_index=True)

st.caption(
    "Source: NASA/LANCE VIIRS C2. VIIRS NRT active-fire products use native Low/Nominal/High confidence classes at 375 m. "
    "SERPRO maps Nominal to Moderate for operational display. High-confidence detections trigger field follow-up alerts; they are not treated as confirmed ground fires. "
    "Historical hotspot trend is derived separately from MODIS Terra MOD14A1.061, while burned-area history is derived from MODIS MCD64A1 v6.1."
)
