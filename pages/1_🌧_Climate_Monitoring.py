import pandas as pd
import streamlit as st
import plotly.express as px

from utils.climate.rainfall import load_rainfall
from utils.climate.anomaly import load_anomaly
from utils.climate.spi import load_spi
from utils.climate.risk import load_risk
from utils.ui import setup_page

setup_page()

# -----------------------------------------------------------------------------
# Climate Monitoring UI only
# Data pipelines / loaders are intentionally unchanged.
# -----------------------------------------------------------------------------
st.markdown(
    """
    <style>
    :root {
        --serpro-deep: #156064;
        --serpro-green: #00C49A;
        --serpro-yellow: #F8E16C;
        --serpro-coral: #FFC2B4;
        --serpro-orange: #FB8F67;
        --serpro-ink: #16383A;
        --serpro-muted: #5E7779;
        --serpro-line: #DDE9E7;
        --serpro-soft: #F5FAF9;
    }
    .climate-hero {
        background: linear-gradient(135deg, #F5FAF9 0%, #FFFFFF 72%);
        border: 1px solid var(--serpro-line);
        border-radius: 18px;
        padding: 22px 24px;
        margin-bottom: 16px;
    }
    .climate-eyebrow { color: var(--serpro-deep); font-size: .72rem; font-weight: 800; letter-spacing: .13em; text-transform: uppercase; }
    .climate-title { color: var(--serpro-ink); font-size: 2rem; font-weight: 850; margin: 2px 0 4px; }
    .climate-subtitle { color: var(--serpro-muted); font-size: .92rem; margin: 0; }
    .section-title { color: var(--serpro-ink); font-size: 1.18rem; font-weight: 800; margin: 22px 0 8px; }
    .section-note { color: var(--serpro-muted); font-size: .78rem; margin: -3px 0 10px; }
    .kpi {
        background: #FFFFFF;
        border: 1px solid var(--serpro-line);
        border-radius: 15px;
        padding: 15px 16px;
        min-height: 112px;
        box-shadow: 0 2px 10px rgba(21,96,100,.05);
    }
    .kpi-label { color: var(--serpro-muted); font-size: .72rem; font-weight: 800; text-transform: uppercase; letter-spacing: .05em; }
    .kpi-value { color: var(--serpro-ink); font-size: 1.65rem; font-weight: 850; line-height: 1.15; margin-top: 7px; }
    .kpi-note { color: var(--serpro-muted); font-size: .72rem; margin-top: 6px; }
    .status-card { border-radius: 15px; padding: 17px 18px; border: 1px solid var(--serpro-line); background: #fff; min-height: 126px; }
    .status-label { color: var(--serpro-muted); font-size: .72rem; font-weight: 800; text-transform: uppercase; letter-spacing: .06em; }
    .status-value { color: var(--serpro-ink); font-size: 1.55rem; font-weight: 850; margin-top: 5px; }
    .status-desc { color: var(--serpro-muted); font-size: .76rem; margin-top: 5px; }
    .info-strip { background: #F5FAF9; border: 1px solid var(--serpro-line); border-radius: 14px; padding: 13px 16px; color: var(--serpro-muted); font-size: .78rem; }
    .legend-row { display:flex; gap:10px; flex-wrap:wrap; margin-top:8px; }
    .legend-item { display:flex; align-items:center; gap:6px; font-size:.74rem; color:var(--serpro-muted); }
    .dot { width:10px; height:10px; border-radius:50%; display:inline-block; }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Load existing pipeline outputs
# -----------------------------------------------------------------------------
rainfall = load_rainfall()
anomaly = load_anomaly()
spi = load_spi()
risk = load_risk()

st.markdown(
    """
    <div class="climate-hero">
      <div class="climate-eyebrow">SERPRO Project · Climate & Carbon Monitoring</div>
      <div class="climate-title">🌧 Climate Monitoring</div>
      <p class="climate-subtitle">Rainfall, climate anomaly, drought/wetness indicators and climate risk for the selected monitoring area.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if rainfall.empty:
    st.warning("Belum ada data rainfall otomatis. Jalankan **Update SERPRO Rainfall** di GitHub Actions terlebih dahulu.")
    st.stop()

rainfall["date"] = pd.to_datetime(rainfall["date"], errors="coerce")
rainfall = rainfall.dropna(subset=["date"]).sort_values("date")
valid_scopes = [s for s in ["project_area", "carbon_project_zone"] if s in rainfall["scope"].unique()]
if not valid_scopes:
    st.error("Tidak ditemukan monitoring scope yang valid pada data rainfall.")
    st.stop()

# -----------------------------------------------------------------------------
# Monitoring controls
# -----------------------------------------------------------------------------
st.markdown('<div class="section-title">Monitoring area & period</div>', unsafe_allow_html=True)
fc1, fc2, fc3 = st.columns([1.3, 1, .9])
with fc1:
    scope = st.selectbox(
        "Monitoring area",
        valid_scopes,
        format_func=lambda x: {
            "project_area": "🟢 SERPRO Project Area · analysis",
            "carbon_project_zone": "🟣 Carbon Project Zone · reference",
        }.get(x, x.replace("_", " ").title()),
    )
scoped_all = rainfall[rainfall["scope"] == scope].copy().sort_values("date")
if scoped_all.empty:
    st.warning("Belum ada data rainfall untuk scope yang dipilih.")
    st.stop()

min_date = scoped_all["date"].min().date()
max_date = scoped_all["date"].max().date()
with fc2:
    start_date = st.date_input("Start date", value=max(min_date, max_date - pd.Timedelta(days=29)), min_value=min_date, max_value=max_date)
with fc3:
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

# -----------------------------------------------------------------------------
# KPI snapshot
# -----------------------------------------------------------------------------
st.markdown('<div class="section-title">Climate snapshot</div>', unsafe_allow_html=True)
k1, k2, k3, k4 = st.columns(4)

def kpi_html(label, value, note):
    return f'<div class="kpi"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div><div class="kpi-note">{note}</div></div>'

with k1:
    st.markdown(kpi_html("Latest rainfall", f"{latest_value:.2f} mm", f"Observation · {latest_date.date()}"), unsafe_allow_html=True)
with k2:
    st.markdown(kpi_html("Rainfall · 30 days", f"{selected_30d:.1f} mm", "Accumulated selected period"), unsafe_allow_html=True)
with k3:
    # latest anomaly within selected period
    anom_latest = None
    if not anomaly.empty:
        anomaly["date"] = pd.to_datetime(anomaly["date"], errors="coerce")
        an = anomaly[(anomaly["scope"] == scope) & (anomaly["date"] <= pd.Timestamp(end_date))].sort_values("date")
        if not an.empty and pd.notna(an.iloc[-1].get("anomaly_30d_pct")):
            anom_latest = float(an.iloc[-1]["anomaly_30d_pct"])
    anomaly_text = f"{anom_latest:+.1f}%" if anom_latest is not None else "—"
    st.markdown(kpi_html("30-day anomaly", anomaly_text, "vs CHIRPS 1991–2020 normal"), unsafe_allow_html=True)
with k4:
    # latest risk within selection
    risk_level = "—"
    if not risk.empty:
        risk["date"] = pd.to_datetime(risk["date"], errors="coerce")
        selected_risk = risk[(risk["scope"] == scope) & (risk["date"] <= pd.Timestamp(end_date))].sort_values("date")
        if not selected_risk.empty:
            risk_level = str(selected_risk.iloc[-1].get("risk_level", "—")).replace("_", " ").title()
    risk_dot = {"Low": "🟢", "Moderate": "🟡", "High": "🟠", "Very High": "🔴"}.get(risk_level, "⚪")
    st.markdown(kpi_html("Climate risk", f"{risk_dot} {risk_level}", "Latest available assessment"), unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Condition + risk overview
# -----------------------------------------------------------------------------
st.markdown('<div class="section-title">Climate condition</div>', unsafe_allow_html=True)
cc1, cc2, cc3 = st.columns(3)

selected_anom = pd.DataFrame()
if not anomaly.empty:
    selected_anom = anomaly[(anomaly["scope"] == scope) & (anomaly["date"] >= pd.Timestamp(start_date)) & (anomaly["date"] <= pd.Timestamp(end_date))].sort_values("date")

with cc1:
    if selected_anom.empty:
        status, icon, desc = "Insufficient data", "⚪", "No anomaly observation available for this period."
    else:
        a = selected_anom.iloc[-1]
        status = str(a.get("climate_status", "Insufficient Data")).replace("_", " ").title()
        icon = {"Very Wet": "🟣", "Wet": "🔵", "Normal": "🟢", "Dry": "🟡", "Drought": "🔴", "Insufficient Data": "⚪"}.get(status, "⚪")
        desc = "Latest 30-day rainfall condition against the historical baseline."
    st.markdown(f'<div class="status-card"><div class="status-label">Rainfall condition</div><div class="status-value">{icon} {status}</div><div class="status-desc">{desc}</div></div>', unsafe_allow_html=True)

with cc2:
    if selected_risk.empty:
        rlevel, ricon, rdesc = "No assessment", "⚪", "Climate risk output is not available for this period."
    else:
        rr = selected_risk.iloc[-1]
        rlevel = str(rr.get("risk_level", "—")).replace("_", " ").title()
        ricon = {"Low": "🟢", "Moderate": "🟡", "High": "🟠", "Very High": "🔴"}.get(rlevel, "⚪")
        rdesc = f"Assessment date: {rr['date'].date()}."
    st.markdown(f'<div class="status-card"><div class="status-label">Climate risk</div><div class="status-value">{ricon} {rlevel}</div><div class="status-desc">{rdesc}</div></div>', unsafe_allow_html=True)

with cc3:
    if selected_anom.empty:
        obs_text = "—"
    else:
        obs = selected_anom.iloc[-1].get("obs_count_30d")
        obs_text = f"{int(obs)}/30 days" if pd.notna(obs) else "—"
    st.markdown(f'<div class="status-card"><div class="status-label">30-day observations</div><div class="status-value">{obs_text}</div><div class="status-desc">Observation availability in the latest anomaly calculation.</div></div>', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Rainfall trend and anomaly
# -----------------------------------------------------------------------------
st.markdown('<div class="section-title">📈 Rainfall trend</div>', unsafe_allow_html=True)
st.markdown('<div class="section-note">Daily rainfall for the selected monitoring area and period.</div>', unsafe_allow_html=True)
fig = px.line(scoped, x="date", y="rainfall_mm", markers=True, labels={"date": "Date", "rainfall_mm": "Rainfall (mm/day)"})
fig.update_traces(line=dict(color="#156064", width=3), marker=dict(color="#00C49A", size=6))
fig.update_layout(height=360, margin=dict(l=10, r=10, t=20, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#16383A"), hovermode="x unified")
fig.update_xaxes(showgrid=False)
fig.update_yaxes(gridcolor="#E7EFEE", rangemode="tozero")
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

if not selected_anom.empty:
    st.markdown('<div class="section-title">📊 Rainfall anomaly</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-note">30-day accumulated rainfall compared with the CHIRPS 1991–2020 climatological normal.</div>', unsafe_allow_html=True)
    fig2 = px.line(selected_anom, x="date", y="anomaly_30d_pct", markers=True, labels={"date": "Date", "anomaly_30d_pct": "30-day anomaly (%)"})
    fig2.update_traces(line=dict(color="#FB8F67", width=3), marker=dict(color="#FB8F67", size=6))
    fig2.add_hline(y=0, line_dash="dash", line_color="#8CA3A4")
    fig2.update_layout(height=310, margin=dict(l=10, r=10, t=20, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#16383A"), hovermode="x unified")
    fig2.update_xaxes(showgrid=False)
    fig2.update_yaxes(gridcolor="#E7EFEE")
    st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

# -----------------------------------------------------------------------------
# SPI overview
# -----------------------------------------------------------------------------
st.markdown('<div class="section-title">💧 Drought / wetness indicators</div>', unsafe_allow_html=True)
if spi.empty:
    st.info("SPI-3/SPI-6 belum tersedia untuk periode ini.")
else:
    spi["date"] = pd.to_datetime(spi["date"], errors="coerce")
    current_spi = spi[(spi["scope"] == scope) & (spi["date"] <= pd.Timestamp(end_date))].sort_values("date")
    if current_spi.empty:
        st.info("SPI-3/SPI-6 belum tersedia untuk periode ini.")
    else:
        latest_spi_date = current_spi["date"].max()
        latest_spi = current_spi[current_spi["date"] == latest_spi_date]
        s3 = latest_spi[latest_spi["period"] == "SPI-3"]
        s6 = latest_spi[latest_spi["period"] == "SPI-6"]
        sp1, sp2, sp3, sp4 = st.columns(4)
        vals = []
        if not s3.empty and pd.notna(s3.iloc[0].get("spi")):
            vals.extend([f"{float(s3.iloc[0]['spi']):+.2f}", str(s3.iloc[0]["spi_status"]).replace("_", " ").title()])
        else:
            vals.extend(["—", "Insufficient data"])
        if not s6.empty and pd.notna(s6.iloc[0].get("spi")):
            vals.extend([f"{float(s6.iloc[0]['spi']):+.2f}", str(s6.iloc[0]["spi_status"]).replace("_", " ").title()])
        else:
            vals.extend(["—", "Insufficient data"])
        sp1.metric("SPI-3", vals[0]); sp2.metric("SPI-3 status", vals[1]); sp3.metric("SPI-6", vals[2]); sp4.metric("SPI-6 status", vals[3])
        st.caption(f"Latest SPI calculation: {latest_spi_date.date()} · Values below zero indicate drier-than-normal conditions; values above zero indicate wetter-than-normal conditions.")

# -----------------------------------------------------------------------------
# Data quality and source
# -----------------------------------------------------------------------------
st.markdown('<div class="section-title">ℹ️ Data & quality</div>', unsafe_allow_html=True)
st.markdown(
    f"""
    <div class="info-strip">
      <b>Rainfall source:</b> {source_label} · <b>Monitoring area:</b> {scope.replace('_', ' ').title()} ·
      <b>Selected period:</b> {start_date} → {end_date} · <b>Observations:</b> {len(scoped)} ·
      <b>Latest processing:</b> {processed_at}.
    </div>
    <div class="legend-row">
      <div class="legend-item"><span class="dot" style="background:#00C49A"></span> Normal / favourable</div>
      <div class="legend-item"><span class="dot" style="background:#F8E16C"></span> Dry / moderate concern</div>
      <div class="legend-item"><span class="dot" style="background:#FB8F67"></span> High concern</div>
      <div class="legend-item"><span class="dot" style="background:#156064"></span> Monitoring baseline</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.caption("Climate indicators are monitoring and screening products. Risk classifications should be interpreted together with rainfall history, SPI indicators and field information.")
