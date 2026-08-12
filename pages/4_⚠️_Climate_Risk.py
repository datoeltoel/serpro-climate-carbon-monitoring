import pandas as pd
import streamlit as st

from utils.climate.risk import load_integrated_risk
from utils.ui import setup_page

setup_page()

st.set_page_config(page_title="SERPRO Climate Risk", page_icon="⚠️", layout="wide")

st.markdown(
    """
    <style>
    .risk-hero {
        background: linear-gradient(135deg, #111820 0%, #18242d 100%);
        border: 1px solid #28343d;
        border-left: 7px solid #ff7a00;
        border-radius: 16px;
        padding: 22px 26px;
        margin: 8px 0 18px 0;
    }
    .risk-kicker {font-size: .72rem; letter-spacing: .15em; color: #8fa2af; text-transform: uppercase; font-weight: 700;}
    .risk-level {font-size: 2.35rem; font-weight: 800; margin-top: 4px;}
    .risk-date {color:#9baab4; font-size:.86rem; margin-top:4px;}
    .kpi-card {
        background: #121a21;
        border: 1px solid #26323b;
        border-radius: 14px;
        padding: 16px 18px;
        min-height: 112px;
    }
    .kpi-label {font-size:.78rem; color:#8fa2af; text-transform:uppercase; letter-spacing:.08em; font-weight:700;}
    .kpi-value {font-size:1.7rem; font-weight:800; margin-top:4px; color:#f4f7f8;}
    .kpi-sub {font-size:.78rem; color:#94a3ad; margin-top:3px;}
    .section-title {font-size:1.3rem; font-weight:800; margin:24px 0 10px 0;}
    .component {
        background:#121a21; border:1px solid #26323b; border-radius:14px; padding:16px 18px; margin-bottom:10px;
    }
    .component-row {display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;}
    .component-name {font-weight:700; color:#edf2f4;}
    .component-score {font-weight:800; color:#c8d4da;}
    .bar {height:10px; background:#25313a; border-radius:999px; overflow:hidden;}
    .bar-fill {height:100%; border-radius:999px;}
    .note {font-size:.78rem; color:#8fa2af; margin-top:7px;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("⚠️ Climate Risk")
st.caption("SERPRO Project · integrated climate screening")

risk = load_integrated_risk()
if risk.empty:
    st.info("Belum ada hasil Integrated Climate Risk. Jalankan **Build Integrated Climate Risk** di GitHub Actions.")
    st.stop()

risk["date"] = pd.to_datetime(risk["date"], errors="coerce")
risk = risk.dropna(subset=["date"]).copy()

available_scopes = [s for s in ["carbon_project_zone", "project_area"] if s in risk["scope"].unique()]
scope = st.selectbox(
    "Monitoring scope",
    available_scopes,
    format_func=lambda x: "🟣 Carbon Project Zone" if x == "carbon_project_zone" else "🟢 Project Area",
)

scoped_all = risk[risk["scope"] == scope].sort_values("date").copy()
if scoped_all.empty:
    st.warning("Belum ada data risk untuk scope yang dipilih.")
    st.stop()

min_date = scoped_all["date"].min().date()
max_date = scoped_all["date"].max().date()

st.markdown("### 📅 Monitoring period")
f1, f2, f3 = st.columns([1, 1, 1])
with f1:
    start_date = st.date_input("Start date", value=min_date, min_value=min_date, max_value=max_date)
with f2:
    end_date = st.date_input("End date", value=max_date, min_value=min_date, max_value=max_date)
with f3:
    preset = st.selectbox("Quick range", ["Custom", "Latest 7D", "Latest 30D", "Latest 90D", "YTD"])

if preset != "Custom":
    if preset == "YTD":
        start_date = max(min_date, pd.Timestamp(year=max_date.year, month=1, day=1).date())
        end_date = max_date
    else:
        days = {"Latest 7D": 7, "Latest 30D": 30, "Latest 90D": 90}[preset]
        end_date = max_date
        start_date = max(min_date, (pd.Timestamp(max_date) - pd.Timedelta(days=days - 1)).date())

if start_date > end_date:
    st.error("Start date harus lebih kecil atau sama dengan End date.")
    st.stop()

scoped = scoped_all[
    (scoped_all["date"].dt.date >= start_date) & (scoped_all["date"].dt.date <= end_date)
].copy()

if scoped.empty:
    st.warning("Tidak ada risk assessment pada periode yang dipilih.")
    st.stop()

latest = scoped.iloc[-1]
level = str(latest.get("risk_level", "UNKNOWN")).replace("_", " ").title()
score = float(latest.get("integrated_risk_score", 0) or 0)
assessment_date = latest["date"].date().isoformat()

risk_style = {
    "Low": ("🟢", "#39b54a"),
    "Moderate": ("🟡", "#f4c430"),
    "High": ("🟠", "#ff7a00"),
    "Very High": ("🔴", "#e23b3b"),
}
icon, accent = risk_style.get(level, ("⚪", "#7d8a93"))

st.markdown(
    f"""
    <div class='risk-hero' style='border-left-color:{accent};'>
        <div class='risk-kicker'>Latest risk within selected period</div>
        <div class='risk-level' style='color:{accent};'>{icon} {level}</div>
        <div class='risk-date'>Assessment date: {assessment_date} · Score: {score:.1f} / 15</div>
    </div>
    """,
    unsafe_allow_html=True,
)

k1, k2, k3, k4 = st.columns(4)

def metric_card(col, label, value, sub=""):
    col.markdown(
        f"<div class='kpi-card'><div class='kpi-label'>{label}</div><div class='kpi-value'>{value}</div><div class='kpi-sub'>{sub}</div></div>",
        unsafe_allow_html=True,
    )

rain_anom = latest.get("rainfall_anomaly_30d_pct")
spi3 = latest.get("spi_3")
spi6 = latest.get("spi_6")
hotspots = latest.get("hotspots_7d")
metric_card(k1, "30D rainfall anomaly", f"{float(rain_anom):+.1f}%" if pd.notna(rain_anom) else "—", "vs historical normal")
metric_card(k2, "SPI-3", f"{float(spi3):+.2f}" if pd.notna(spi3) else "—", "3-month drought signal")
metric_card(k3, "SPI-6", f"{float(spi6):+.2f}" if pd.notna(spi6) else "—", "6-month drought signal")
metric_card(k4, "Hotspots · 7D", f"{int(hotspots):,}" if pd.notna(hotspots) else "—", "within selected scope")

st.markdown("### Risk components")
components = [
    ("Rainfall", latest.get("rainfall_score", 0), 4, "Rainfall anomaly"),
    ("Drought / SPI", latest.get("drought_score", 0), 4, "SPI-3 / SPI-6"),
    ("Vegetation / NDMI", latest.get("vegetation_score", 0), 3, "Moisture stress"),
    ("Fire", latest.get("fire_score", 0), 4, "Recent hotspot activity"),
]

cols = st.columns(2)
for i, (name, val, maximum, note) in enumerate(components):
    val = float(val) if pd.notna(val) else 0.0
    pct = max(0.0, min(100.0, val / maximum * 100.0))
    color = "#39b54a" if pct < 34 else "#f4c430" if pct < 67 else "#e23b3b"
    with cols[i % 2]:
        st.markdown(
            f"""
            <div class='component'>
              <div class='component-row'><span class='component-name'>{name}</span><span class='component-score'>{val:.0f} / {maximum}</span></div>
              <div class='bar'><div class='bar-fill' style='width:{pct:.0f}%;background:{color};'></div></div>
              <div class='note'>{note}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("### 📈 Risk trend")
trend = scoped[["date", "integrated_risk_score"]].copy().sort_values("date")
trend = trend.rename(columns={"integrated_risk_score": "Risk Score"}).set_index("date")
st.line_chart(trend, height=260)

basis = str(latest.get("risk_basis", "Operational screening"))
st.caption(
    f"Assessment period: {start_date} → {end_date} · Latest assessment: {assessment_date} · Basis: {basis}. "
    "Integrated Risk is an operational screening index and not a calibrated fire-danger or carbon-accounting metric."
)
