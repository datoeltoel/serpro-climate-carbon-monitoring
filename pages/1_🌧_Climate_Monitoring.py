import pandas as pd
import streamlit as st
import plotly.express as px

from utils.climate.rainfall import load_rainfall
from utils.climate.anomaly import load_anomaly
from utils.climate.spi import load_spi
from utils.climate.risk import load_risk
from utils.ui import setup_page

setup_page()

st.title("🌧 Climate Monitoring")
st.caption("SERPRO Project · Rainfall, anomaly, drought/wetness indicators and climate risk")

rainfall = load_rainfall()
anomaly = load_anomaly()
spi = load_spi()
risk = load_risk()

if rainfall.empty:
    st.warning("Belum ada data rainfall otomatis. Jalankan **Update SERPRO Rainfall** di GitHub Actions terlebih dahulu.")
    st.stop()

rainfall["date"] = pd.to_datetime(rainfall["date"], errors="coerce")
rainfall = rainfall.dropna(subset=["date"]).sort_values("date")

valid_scopes = [s for s in ["carbon_project_zone", "project_area"] if s in rainfall["scope"].unique()]

st.markdown("### 🎛 Monitoring Controls")
f1, f2, f3 = st.columns([1.3, 1, 1])
with f1:
    scope = st.selectbox(
        "Monitoring scope",
        valid_scopes,
        format_func=lambda x: {
            "carbon_project_zone": "🟣 Carbon Project Zone",
            "project_area": "🟢 Project Area",
        }.get(x, x.replace("_", " ").title()),
    )

scoped_all = rainfall[rainfall["scope"] == scope].copy().sort_values("date")
if scoped_all.empty:
    st.warning("Belum ada data rainfall untuk scope yang dipilih.")
    st.stop()

min_date = scoped_all["date"].min().date()
max_date = scoped_all["date"].max().date()

with f2:
    start_date = st.date_input("Start date", value=max(min_date, max_date - pd.Timedelta(days=29)), min_value=min_date, max_value=max_date)
with f3:
    end_date = st.date_input("End date", value=max_date, min_value=min_date, max_value=max_date)

preset = st.selectbox("Quick range", ["Custom", "Latest 7D", "Latest 30D", "Latest 90D", "Year to date"], index=2)
if preset != "Custom":
    if preset == "Latest 7D":
        start_date = max(min_date, max_date - pd.Timedelta(days=6))
    elif preset == "Latest 30D":
        start_date = max(min_date, max_date - pd.Timedelta(days=29))
    elif preset == "Latest 90D":
        start_date = max(min_date, max_date - pd.Timedelta(days=89))
    elif preset == "Year to date":
        start_date = max(min_date, pd.Timestamp(max_date.year, 1, 1).date())
    end_date = max_date

if start_date > end_date:
    st.error("Start date harus lebih kecil atau sama dengan End date.")
    st.stop()

scoped = scoped_all[(scoped_all["date"].dt.date >= start_date) & (scoped_all["date"].dt.date <= end_date)].copy()
if scoped.empty:
    st.warning("Tidak ada data pada periode yang dipilih.")
    st.stop()

latest_row = scoped.iloc[-1]
latest_date = latest_row["date"]
latest_value = float(latest_row["rainfall_mm"])
selected_7d = float(scoped.tail(7)["rainfall_mm"].sum())
selected_30d = float(scoped.tail(30)["rainfall_mm"].sum())
source = str(latest_row.get("source", "—"))
processed_at = str(latest_row.get("processing_time_utc", "—"))
source_label = {"NASA/GPM_L3/IMERG_V07": "NASA GPM IMERG V07"}.get(source, source)

st.markdown(
    f"""
    <div style='padding:16px 20px;border-radius:16px;background:linear-gradient(135deg,#123653,#1f5c82);color:white;margin:10px 0 18px 0;'>
      <div style='font-size:.75rem;opacity:.78;text-transform:uppercase;letter-spacing:.12em;'>Selected monitoring window</div>
      <div style='font-size:1.35rem;font-weight:800;margin-top:4px;'>{start_date} → {end_date}</div>
      <div style='font-size:.82rem;opacity:.78;margin-top:6px;'>Latest observation: {latest_date.date()} · {source_label}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Risk for latest available date within selection
selected_risk = pd.DataFrame()
if not risk.empty:
    risk["date"] = pd.to_datetime(risk["date"], errors="coerce")
    selected_risk = risk[(risk["scope"] == scope) & (risk["date"] <= pd.Timestamp(end_date))].sort_values("date")

st.markdown("### ⚠️ Climate Risk")
if selected_risk.empty:
    st.info("Climate risk output belum tersedia untuk periode ini.")
else:
    rr = selected_risk.iloc[-1]
    risk_level = str(rr.get("risk_level", "—")).replace("_", " ").title()
    risk_icon = {"Low": "🟢", "Moderate": "🟡", "High": "🟠", "Very High": "🔴"}.get(risk_level, "⚪")
    risk_color = {"Low": "#2E7D32", "Moderate": "#F9A825", "High": "#E65100", "Very High": "#C62828"}.get(risk_level, "#607D8B")
    st.markdown(
        f"""
        <div style='border-left:7px solid {risk_color};padding:14px 18px;border-radius:12px;background:#111820;'>
          <div style='font-size:.72rem;color:#94a6b6;text-transform:uppercase;letter-spacing:.12em;'>Latest risk within selected period</div>
          <div style='font-size:2rem;font-weight:850;color:{risk_color};margin-top:3px;'>{risk_icon} {risk_level}</div>
          <div style='font-size:.78rem;color:#8193a3;margin-top:4px;'>Assessment date: {rr['date'].date()}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    rc1, rc2, rc3 = st.columns(3)
    rc1.metric("30-day anomaly", f"{float(rr['anomaly_30d_pct']):+.1f}%" if pd.notna(rr.get("anomaly_30d_pct")) else "—")
    rc2.metric("SPI-3", f"{float(rr['spi_3']):+.2f}" if pd.notna(rr.get("spi_3")) else "—")
    rc3.metric("SPI-6", f"{float(rr['spi_6']):+.2f}" if pd.notna(rr.get("spi_6")) else "—")
    st.caption(f"Risk basis: {rr.get('risk_basis', '—')}")

# Anomaly and climate condition
selected_anom = pd.DataFrame()
if not anomaly.empty:
    anomaly["date"] = pd.to_datetime(anomaly["date"], errors="coerce")
    selected_anom = anomaly[(anomaly["scope"] == scope) & (anomaly["date"] >= pd.Timestamp(start_date)) & (anomaly["date"] <= pd.Timestamp(end_date))].sort_values("date")

st.markdown("### 🌦 Climate Condition")
if selected_anom.empty:
    st.info("Anomaly belum tersedia untuk periode yang dipilih.")
else:
    a = selected_anom.iloc[-1]
    status = str(a.get("climate_status", "Insufficient Data")).replace("_", " ").title()
    icon = {"Very Wet": "🟣", "Wet": "🔵", "Normal": "🟢", "Dry": "🟡", "Drought": "🔴", "Insufficient Data": "⚪"}.get(status, "⚪")
    c0, c1, c2 = st.columns(3)
    c0.metric("30-day status", f"{icon} {status}")
    c1.metric("30-day anomaly", f"{float(a['anomaly_30d_pct']):+.1f}%" if pd.notna(a.get("anomaly_30d_pct")) else "—")
    c2.metric("Observations", f"{int(a['obs_count_30d'])}/30" if pd.notna(a.get("obs_count_30d")) else "—")
    st.caption("Baseline: CHIRPS v2 Final · 1991–2020 daily calendar-day climatology.")

# SPI
current_spi = pd.DataFrame()
if not spi.empty:
    spi["date"] = pd.to_datetime(spi["date"], errors="coerce")
    current_spi = spi[(spi["scope"] == scope) & (spi["date"] <= pd.Timestamp(end_date))].sort_values("date")

st.markdown("### 📉 Drought / Wetness Indicators")
if current_spi.empty:
    st.info("SPI-3/SPI-6 belum tersedia untuk periode ini.")
else:
    latest_spi_date = current_spi["date"].max()
    latest_spi = current_spi[current_spi["date"] == latest_spi_date]
    s3 = latest_spi[latest_spi["period"] == "SPI-3"]
    s6 = latest_spi[latest_spi["period"] == "SPI-6"]
    s1, s2, s3c, s4 = st.columns(4)
    if not s3.empty and pd.notna(s3.iloc[0].get("spi")):
        s1.metric("SPI-3", f"{float(s3.iloc[0]['spi']):+.2f}")
        s2.metric("SPI-3 status", str(s3.iloc[0]["spi_status"]).replace("_", " ").title())
    else:
        s1.metric("SPI-3", "—")
        s2.metric("SPI-3 status", "Insufficient data")
    if not s6.empty and pd.notna(s6.iloc[0].get("spi")):
        s3c.metric("SPI-6", f"{float(s6.iloc[0]['spi']):+.2f}")
        s4.metric("SPI-6 status", str(s6.iloc[0]["spi_status"]).replace("_", " ").title())
    else:
        s3c.metric("SPI-6", "—")
        s4.metric("SPI-6 status", "Insufficient data")
    st.caption(f"Latest SPI calculation within selected period: {latest_spi_date.date()}.")

# Rainfall KPI cards
st.markdown("### 🌧 Rainfall Snapshot")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Latest daily", f"{latest_value:.2f} mm")
k2.metric("Selected 7-day", f"{selected_7d:.2f} mm")
k3.metric("Selected 30-day", f"{selected_30d:.2f} mm")
k4.metric("Observations", f"{len(scoped)}")

st.markdown("### 📈 Rainfall Trend")
fig = px.line(scoped, x="date", y="rainfall_mm", markers=True, title=f"Daily rainfall · {scope.replace('_', ' ').title()}", labels={"date": "Date", "rainfall_mm": "Rainfall (mm/day)"})
fig.update_layout(height=380, margin=dict(l=20, r=20, t=50, b=20))
fig.update_yaxes(rangemode="tozero")
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

if not selected_anom.empty:
    fig2 = px.line(selected_anom, x="date", y="anomaly_30d_pct", markers=True, title="30-day rainfall anomaly vs CHIRPS 1991–2020 normal", labels={"date": "Date", "anomaly_30d_pct": "30-day anomaly (%)"})
    fig2.add_hline(y=0, line_dash="dash")
    fig2.update_layout(height=320, margin=dict(l=20, r=20, t=50, b=20))
    st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

st.caption(f"Current rainfall: {source_label} · Processed: {processed_at} · Monitoring window: {start_date} → {end_date}")
