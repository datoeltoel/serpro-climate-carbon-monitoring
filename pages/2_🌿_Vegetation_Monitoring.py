import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from utils.climate.vegetation import load_ndmi, load_ndvi, load_ndvi_annual
from utils.ui import setup_page

setup_page()

st.markdown("# 🌿 Vegetation Monitoring")
st.caption("SERPRO Project · Sentinel-2 NDVI vegetation vigor + NDMI vegetation moisture")

ndmi = load_ndmi()
ndvi = load_ndvi()
annual = load_ndvi_annual()

for df in (ndmi, ndvi):
    if not df.empty and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

if ndmi.empty and ndvi.empty:
    st.info("Belum ada data NDVI/NDMI. Jalankan **Update SERPRO NDVI** dan **Update SERPRO NDMI** di GitHub Actions.")
    st.stop()

scope_keys = sorted(set(ndmi.get("scope", pd.Series(dtype=str)).dropna().astype(str)) | set(ndvi.get("scope", pd.Series(dtype=str)).dropna().astype(str)))
if not scope_keys:
    st.info("Belum ada scope vegetation yang tersedia.")
    st.stop()

scope_labels = {
    "carbon_project_zone": "🟣 Carbon Project Zone",
    "project_area": "🟢 Project Area",
}

c_scope, c_period = st.columns([1.25, 1])
with c_scope:
    scope = st.selectbox(
        "Monitoring scope",
        scope_keys,
        format_func=lambda x: scope_labels.get(x, x.replace("_", " ").title()),
    )

ndvi_s = ndvi[ndvi["scope"].astype(str) == scope].copy() if not ndvi.empty else pd.DataFrame()
ndmi_s = ndmi[ndmi["scope"].astype(str) == scope].copy() if not ndmi.empty else pd.DataFrame()

all_dates = pd.concat(
    [x["date"] for x in (ndvi_s, ndmi_s) if not x.empty], ignore_index=True
).dropna()

with c_period:
    if not all_dates.empty:
        min_date = all_dates.min().date()
        max_date = all_dates.max().date()
        date_range = st.date_input("Monitoring period", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    else:
        date_range = None

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
    ndvi_p = ndvi_s[(ndvi_s["date"] >= start_date) & (ndvi_s["date"] <= end_date)].copy()
    ndmi_p = ndmi_s[(ndmi_s["date"] >= start_date) & (ndmi_s["date"] <= end_date)].copy()
else:
    ndvi_p, ndmi_p = ndvi_s.copy(), ndmi_s.copy()

ndvi_p = ndvi_p.sort_values("date")
ndmi_p = ndmi_p.sort_values("date")


def pct_change(df: pd.DataFrame, col: str, days: int):
    if df.empty or len(df) < 2:
        return None
    latest = df["date"].max()
    w = df[df["date"] >= latest - pd.Timedelta(days=days)]
    if len(w) < 2:
        return None
    first = float(w.iloc[0][col])
    last = float(w.iloc[-1][col])
    if first == 0:
        return None
    return (last - first) / abs(first) * 100


def index_status(value):
    if value is None or pd.isna(value):
        return "No data", "#718096"
    value = float(value)
    if value >= 0.70:
        return "Good vigor", "#18864B"
    if value >= 0.50:
        return "Moderate vigor", "#B26A00"
    if value >= 0.30:
        return "Low vigor", "#D97706"
    return "Very low vigor", "#C62828"


def moisture_status(value):
    if value is None or pd.isna(value):
        return "No data", "#718096"
    value = float(value)
    if value >= 0.40:
        return "Moist", "#18864B"
    if value >= 0.20:
        return "Moderate", "#B26A00"
    if value >= 0.00:
        return "Drying", "#D97706"
    return "Low moisture", "#C62828"

latest_ndvi = float(ndvi_p.iloc[-1]["ndvi"]) if not ndvi_p.empty else None
latest_ndmi = float(ndmi_p.iloc[-1]["ndmi"]) if not ndmi_p.empty else None
ndvi_30 = pct_change(ndvi_p, "ndvi", 30)
ndmi_30 = pct_change(ndmi_p, "ndmi", 30)
ndvi_90 = pct_change(ndvi_p, "ndvi", 90)
ndmi_90 = pct_change(ndmi_p, "ndmi", 90)

ndvi_label, ndvi_color = index_status(latest_ndvi)
ndmi_label, ndmi_color = moisture_status(latest_ndmi)

# Combined vegetation stress logic is deliberately conservative: both vigor and moisture must decline.
if ndvi_30 is not None and ndmi_30 is not None and ndvi_30 <= -10 and ndmi_30 <= -10:
    stress_level = "HIGH"
elif (ndvi_30 is not None and ndvi_30 <= -10) or (ndmi_30 is not None and ndmi_30 <= -10):
    stress_level = "MODERATE"
elif (ndvi_30 is not None and ndvi_30 < 0) or (ndmi_30 is not None and ndmi_30 < 0):
    stress_level = "LOW"
else:
    stress_level = "STABLE"

st.markdown("### 🌱 Vegetation Condition Overview")
kpis = [
    ("🌿", "NDVI", f"{latest_ndvi:.3f}" if latest_ndvi is not None else "—", ndvi_label, ndvi_color),
    ("💧", "NDMI", f"{latest_ndmi:.3f}" if latest_ndmi is not None else "—", ndmi_label, ndmi_color),
    ("📉", "NDVI · 30D", f"{ndvi_30:+.1f}%" if ndvi_30 is not None else "—", "Change", "#C62828" if ndvi_30 is not None and ndvi_30 < 0 else "#18864B"),
    ("💦", "NDMI · 30D", f"{ndmi_30:+.1f}%" if ndmi_30 is not None else "—", "Change", "#C62828" if ndmi_30 is not None and ndmi_30 < 0 else "#18864B"),
    ("⚠️", "VEGETATION STRESS", stress_level, "NDVI + NDMI screening", "#C62828" if stress_level == "HIGH" else "#B26A00" if stress_level == "MODERATE" else "#18864B"),
]
cols = st.columns(5)
for col, (icon, title, value, sub, color) in zip(cols, kpis):
    with col:
        st.markdown(
            f'<div class="kpi-card"><div class="kpi-top"><span class="kpi-icon">{icon}</span><span>{title}</span></div>'
            f'<div class="kpi-value">{value}</div><div class="kpi-sub" style="color:{color}"><b>{sub}</b></div></div>',
            unsafe_allow_html=True,
        )

if stress_level == "HIGH":
    st.error("🚨 High vegetation stress: NDVI dan NDMI sama-sama menunjukkan penurunan ≥10% dalam 30 hari. Prioritaskan verifikasi lapangan dan cek konteks tutupan lahan/fenologi.")
elif stress_level == "MODERATE":
    st.warning("⚠️ Moderate vegetation stress: terdapat penurunan salah satu indikator ≥10% dalam 30 hari. Review lokasi dan tren sebelum field follow-up.")
else:
    st.success("✅ Tidak ada sinyal combined vegetation stress berdasarkan aturan screening saat ini.")

# Tabs keep the dashboard readable while retaining detailed analysis.
tab_overview, tab_trend, tab_stress, tab_data = st.tabs(["Overview", "Trends", "Stress Analysis", "Data & Quality"])

with tab_overview:
    left, right = st.columns([1.5, 1])
    with left:
        st.markdown("#### 📈 Recent Vegetation Trend")
        if not ndvi_p.empty or not ndmi_p.empty:
            fig = go.Figure()
            if not ndvi_p.empty:
                fig.add_scatter(x=ndvi_p["date"], y=ndvi_p["ndvi"], mode="lines+markers", name="NDVI · vigor")
            if not ndmi_p.empty:
                fig.add_scatter(x=ndmi_p["date"], y=ndmi_p["ndmi"], mode="lines+markers", name="NDMI · moisture")
            fig.update_layout(height=350, margin=dict(l=10,r=10,t=15,b=10), yaxis_title="Index", hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("Tidak ada observasi pada periode terpilih.")
    with right:
        st.markdown("#### 🧭 Current Interpretation")
        st.markdown(f"**NDVI:** {ndvi_label}")
        st.caption("NDVI digunakan sebagai indikator vigor/kehijauan vegetasi.")
        st.markdown(f"**NDMI:** {ndmi_label}")
        st.caption("NDMI digunakan sebagai indikator kelembapan vegetasi/canopy moisture.")
        st.markdown(f"**Combined stress:** {stress_level}")
        st.caption("Screening konservatif; bukan bukti tunggal degradasi atau kerusakan.")
        if latest_ndvi is not None:
            st.metric("NDVI 90-day change", f"{ndvi_90:+.1f}%" if ndvi_90 is not None else "—")
        if latest_ndmi is not None:
            st.metric("NDMI 90-day change", f"{ndmi_90:+.1f}%" if ndmi_90 is not None else "—")

with tab_trend:
    st.markdown("#### 📅 Annual NDVI Trend · 2015–2025")
    if annual.empty:
        st.warning("Annual NDVI dataset belum tersedia. Jalankan workflow **Update SERPRO NDVI**.")
    else:
        annual_s = annual[annual["scope"].astype(str) == scope].copy()
        if annual_s.empty:
            st.info("Belum ada annual NDVI untuk scope ini.")
        else:
            annual_s["year"] = annual_s["year"].astype(int)
            annual_s = annual_s.sort_values("year")
            fig = go.Figure()
            fig.add_scatter(x=annual_s["year"], y=annual_s["ndvi_mean"], mode="lines+markers", name="Annual NDVI")
            fig.update_layout(height=360, margin=dict(l=10,r=10,t=15,b=10), xaxis=dict(dtick=1), yaxis_title="NDVI mean", xaxis_title="Year", hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.caption("2015 merupakan tahun observasi parsial Sentinel-2; annual series digunakan sebagai indikator monitoring jangka panjang, bukan sebagai carbon-accounting output.")

            a1, a2, a3 = st.columns(3)
            latest_a = annual_s.iloc[-1]
            first_a = annual_s.iloc[0]
            a1.metric("Latest annual NDVI", f"{float(latest_a['ndvi_mean']):.3f}", str(int(latest_a["year"])))
            a2.metric("Change vs first year", f"{float(latest_a['ndvi_mean'] - first_a['ndvi_mean']):+.3f}")
            a3.metric("Annual observations", f"{int(annual_s['observation_count'].sum()):,}")

    st.markdown("#### 📆 Monthly Trend")
    monthly_parts = []
    if not ndvi_s.empty:
        x = ndvi_s.copy()
        x["month"] = x["date"].dt.to_period("M").dt.to_timestamp()
        monthly_parts.append(x.groupby("month", as_index=False)["ndvi"].mean())
    if not ndmi_s.empty:
        x = ndmi_s.copy()
        x["month"] = x["date"].dt.to_period("M").dt.to_timestamp()
        monthly_parts.append(x.groupby("month", as_index=False)["ndmi"].mean())
    if monthly_parts:
        m = monthly_parts[0].rename(columns={"ndvi": "NDVI"})
        if len(monthly_parts) > 1:
            m2 = monthly_parts[1].rename(columns={"ndmi": "NDMI"})
            m = pd.merge(m, m2, on="month", how="outer")
        fig = go.Figure()
        if "NDVI" in m: fig.add_scatter(x=m["month"], y=m["NDVI"], mode="lines+markers", name="NDVI")
        if "NDMI" in m: fig.add_scatter(x=m["month"], y=m["NDMI"], mode="lines+markers", name="NDMI")
        fig.update_layout(height=330, margin=dict(l=10,r=10,t=15,b=10), yaxis_title="Index", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.caption("Monthly values are calculated from the available scene-level zonal observations; months without valid observations are not interpolated.")

with tab_stress:
    st.markdown("#### 🚨 Vegetation Stress Screening")
    st.caption("Thresholds: 30-day decline ≥10% in one index = Moderate; both NDVI and NDMI ≥10% decline = High.")

    if not ndvi_p.empty or not ndmi_p.empty:
        stress = pd.merge(
            ndvi_p[["date", "ndvi"]], ndmi_p[["date", "ndmi"]], on="date", how="outer"
        ).sort_values("date")
        stress["ndvi_change_pct"] = stress["ndvi"].pct_change() * 100
        stress["ndmi_change_pct"] = stress["ndmi"].pct_change() * 100
        stress["stress"] = "Stable"
        stress.loc[(stress["ndvi_change_pct"] <= -10) | (stress["ndmi_change_pct"] <= -10), "stress"] = "Moderate"
        stress.loc[(stress["ndvi_change_pct"] <= -10) & (stress["ndmi_change_pct"] <= -10), "stress"] = "High"

        fig = go.Figure()
        for level in ["High", "Moderate", "Stable"]:
            d = stress[stress["stress"] == level]
            if not d.empty:
                fig.add_scatter(x=d["date"], y=d["ndvi"], mode="markers", name=level)
        fig.update_layout(height=320, margin=dict(l=10,r=10,t=15,b=10), yaxis_title="NDVI", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        st.markdown("#### Recommended follow-up")
        if stress_level == "HIGH":
            st.error("FIELD REVIEW · cek hotspot/fire layer, perubahan tutupan lahan, akses lapangan, dan kondisi hidrologi di area yang mengalami penurunan.")
        elif stress_level == "MODERATE":
            st.warning("REVIEW · cek tren lanjutan dan konteks musiman sebelum menetapkan field priority.")
        else:
            st.success("MONITOR · tidak ada combined stress signal yang memenuhi threshold.")
    else:
        st.info("Data belum cukup untuk stress analysis.")

with tab_data:
    st.markdown("#### 📋 Monitoring Records")
    records = pd.merge(
        ndvi_p[["date", "ndvi", "cloudy_pixel_percentage", "source"]] if not ndvi_p.empty else pd.DataFrame(columns=["date","ndvi","cloudy_pixel_percentage","source"]),
        ndmi_p[["date", "ndmi"]] if not ndmi_p.empty else pd.DataFrame(columns=["date","ndmi"]),
        on="date", how="outer"
    ).sort_values("date", ascending=False)
    if not records.empty:
        st.dataframe(records, use_container_width=True, hide_index=True)
    else:
        st.info("Tidak ada records pada periode terpilih.")

    st.markdown("#### ✅ Data Quality")
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("NDVI observations", f"{len(ndvi_s):,}")
    q2.metric("NDMI observations", f"{len(ndmi_s):,}")
    q3.metric("NDVI valid in period", f"{len(ndvi_p):,}")
    q4.metric("NDMI valid in period", f"{len(ndmi_p):,}")
    st.caption("Cloudy-pixel percentage is retained from the processing pipeline and should be reviewed when interpreting individual observations.")

st.markdown("---")
st.markdown("### 📌 Interpretation & Limitations")
st.markdown(
    "- **NDVI** = (B8 − B4) / (B8 + B4), indikator vigor/kehijauan vegetasi.\n"
    "- **NDMI** = (B8 − B11) / (B8 + B11), indikator kelembapan vegetasi/canopy moisture.\n"
    "- Penurunan NDVI dapat dipengaruhi fenologi, panen, pembukaan lahan, gangguan, awan residual, atau perubahan kondisi vegetasi lainnya.\n"
    "- Penurunan NDMI menunjukkan indikasi moisture stress, tetapi harus dibaca bersama rainfall, fire, hydrology, dan kondisi lapangan.\n"
    "- **Combined vegetation stress** pada dashboard adalah screening operasional dan belum menjadi komponen final integrated carbon-risk/accounting model."
)
st.caption("Source: Copernicus Sentinel-2 SR Harmonized. Current pipeline uses scene cloud filtering + SCL masking. Annual NDVI: 2015–2025 where available.")
