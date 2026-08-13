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
    st.info("No NDVI/NDMI data is currently available. Run the **Update SERPRO NDVI** and **Update SERPRO NDMI** GitHub Actions workflows.")
    st.stop()

scope_keys = sorted(set(ndmi.get("scope", pd.Series(dtype=str)).dropna().astype(str)) | set(ndvi.get("scope", pd.Series(dtype=str)).dropna().astype(str)))
if not scope_keys:
    st.info("No vegetation monitoring scope is currently available.")
    st.stop()

scope_labels = {"carbon_project_zone": "🟣 Carbon Project Zone", "project_area": "🟢 Project Area"}

c_scope, c_period = st.columns([1.25, 1])
with c_scope:
    scope = st.selectbox("Monitoring scope", scope_keys, format_func=lambda x: scope_labels.get(x, x.replace("_", " ").title()))

ndvi_s = ndvi[ndvi["scope"].astype(str) == scope].copy() if not ndvi.empty else pd.DataFrame()
ndmi_s = ndmi[ndmi["scope"].astype(str) == scope].copy() if not ndmi.empty else pd.DataFrame()
all_dates = pd.concat([x["date"] for x in (ndvi_s, ndmi_s) if not x.empty], ignore_index=True).dropna()

with c_period:
    if not all_dates.empty:
        min_date, max_date = all_dates.min().date(), all_dates.max().date()
        date_range = st.date_input("Monitoring period", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    else:
        date_range = None

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
    ndvi_p = ndvi_s[(ndvi_s["date"] >= start_date) & (ndvi_s["date"] <= end_date)].copy()
    ndmi_p = ndmi_s[(ndmi_s["date"] >= start_date) & (ndmi_s["date"] <= end_date)].copy()
else:
    ndvi_p, ndmi_p = ndvi_s.copy(), ndmi_s.copy()

ndvi_p, ndmi_p = ndvi_p.sort_values("date"), ndmi_p.sort_values("date")


def pct_change(df, col, days):
    if df.empty or len(df) < 2:
        return None
    latest = df["date"].max()
    w = df[df["date"] >= latest - pd.Timedelta(days=days)]
    if len(w) < 2:
        return None
    first, last = float(w.iloc[0][col]), float(w.iloc[-1][col])
    return None if first == 0 else (last - first) / abs(first) * 100


def index_status(value):
    if value is None or pd.isna(value): return "No data", "#718096"
    value = float(value)
    if value >= 0.70: return "Good vigor", "#18864B"
    if value >= 0.50: return "Moderate vigor", "#B26A00"
    if value >= 0.30: return "Low vigor", "#D97706"
    return "Very low vigor", "#C62828"


def moisture_status(value):
    if value is None or pd.isna(value): return "No data", "#718096"
    value = float(value)
    if value >= 0.40: return "Moist", "#18864B"
    if value >= 0.20: return "Moderate", "#B26A00"
    if value >= 0.00: return "Drying", "#D97706"
    return "Low moisture", "#C62828"

latest_ndvi = float(ndvi_p.iloc[-1]["ndvi"]) if not ndvi_p.empty else None
latest_ndmi = float(ndmi_p.iloc[-1]["ndmi"]) if not ndmi_p.empty else None
ndvi_30, ndmi_30 = pct_change(ndvi_p, "ndvi", 30), pct_change(ndmi_p, "ndmi", 30)
ndvi_90, ndmi_90 = pct_change(ndvi_p, "ndvi", 90), pct_change(ndmi_p, "ndmi", 90)
ndvi_label, ndvi_color = index_status(latest_ndvi)
ndmi_label, ndmi_color = moisture_status(latest_ndmi)

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
        st.markdown(f'<div class="kpi-card"><div class="kpi-top"><span class="kpi-icon">{icon}</span><span>{title}</span></div><div class="kpi-value">{value}</div><div class="kpi-sub" style="color:{color}"><b>{sub}</b></div></div>', unsafe_allow_html=True)

if stress_level == "HIGH":
    st.error("🚨 High vegetation stress detected: both NDVI and NDMI declined by at least 10% over the last 30 days. Prioritize field verification and review land-cover, phenology, fire, and hydrological context.")
elif stress_level == "MODERATE":
    st.warning("⚠️ Moderate vegetation stress detected: at least one vegetation indicator declined by 10% or more over the last 30 days. Review the spatial context and recent trend before field follow-up.")
elif stress_level == "LOW":
    st.info("ℹ️ Low vegetation stress signal: a recent decline is present, but the moderate-stress threshold has not been reached.")
else:
    st.success("✅ No combined vegetation stress signal detected under the current screening rules.")

tab_overview, tab_trend, tab_stress, tab_data = st.tabs(["Overview", "Trends", "Stress Analysis", "Data & Quality"])

with tab_overview:
    left, right = st.columns([1.5, 1])
    with left:
        st.markdown("#### 📈 Recent Vegetation Trend")
        if not ndvi_p.empty or not ndmi_p.empty:
            fig = go.Figure()
            if not ndvi_p.empty: fig.add_scatter(x=ndvi_p["date"], y=ndvi_p["ndvi"], mode="lines+markers", name="NDVI · vegetation vigor")
            if not ndmi_p.empty: fig.add_scatter(x=ndmi_p["date"], y=ndmi_p["ndmi"], mode="lines+markers", name="NDMI · vegetation moisture")
            fig.update_layout(height=350, margin=dict(l=10,r=10,t=15,b=10), yaxis_title="Index", hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else: st.info("No observations are available for the selected period.")
    with right:
        st.markdown("#### 🧭 Current Interpretation")
        st.markdown(f"**NDVI:** {ndvi_label}")
        st.caption("NDVI represents vegetation greenness and relative vegetation vigor.")
        st.markdown(f"**NDMI:** {ndmi_label}")
        st.caption("NDMI represents vegetation/canopy moisture conditions.")
        st.markdown(f"**Combined stress:** {stress_level}")
        st.caption("Conservative screening indicator; not standalone evidence of degradation or damage.")
        st.metric("NDVI · 90-day change", f"{ndvi_90:+.1f}%" if ndvi_90 is not None else "—")
        st.metric("NDMI · 90-day change", f"{ndmi_90:+.1f}%" if ndmi_90 is not None else "—")

with tab_trend:
    st.markdown("#### 📅 Annual NDVI Trend · 2015–2025")
    if annual.empty:
        st.warning("The annual NDVI dataset is not available. Run the **Update SERPRO NDVI** workflow.")
    else:
        annual_s = annual[annual["scope"].astype(str) == scope].copy()
        if annual_s.empty:
            st.info("No annual NDVI records are available for this scope.")
        else:
            annual_s["year"] = annual_s["year"].astype(int)
            annual_s = annual_s.sort_values("year")
            fig = go.Figure()
            fig.add_scatter(x=annual_s["year"], y=annual_s["ndvi_mean"], mode="lines+markers", name="Annual NDVI")
            fig.update_layout(height=360, margin=dict(l=10,r=10,t=15,b=10), xaxis=dict(dtick=1), yaxis_title="Mean NDVI", xaxis_title="Year", hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.caption("The annual series supports long-term vegetation monitoring and is not a carbon-accounting output.")
            a1, a2, a3 = st.columns(3)
            latest_a, first_a = annual_s.iloc[-1], annual_s.iloc[0]
            a1.metric("Latest annual NDVI", f"{float(latest_a['ndvi_mean']):.3f}", str(int(latest_a["year"])))
            a2.metric("Change vs. first year", f"{float(latest_a['ndvi_mean'] - first_a['ndvi_mean']):+.3f}")
            a3.metric("Annual observations", f"{int(annual_s['observation_count'].sum()):,}")

    st.markdown("#### 📆 Monthly Vegetation Trend")
    monthly = []
    if not ndvi_s.empty:
        x = ndvi_s.copy(); x["month"] = x["date"].dt.to_period("M").dt.to_timestamp()
        monthly.append(x.groupby("month", as_index=False)["ndvi"].mean().rename(columns={"ndvi":"NDVI"}))
    if not ndmi_s.empty:
        x = ndmi_s.copy(); x["month"] = x["date"].dt.to_period("M").dt.to_timestamp()
        monthly.append(x.groupby("month", as_index=False)["ndmi"].mean().rename(columns={"ndmi":"NDMI"}))
    if monthly:
        m = monthly[0]
        if len(monthly) > 1: m = pd.merge(m, monthly[1], on="month", how="outer")
        fig = go.Figure()
        if "NDVI" in m: fig.add_scatter(x=m["month"], y=m["NDVI"], mode="lines+markers", name="NDVI")
        if "NDMI" in m: fig.add_scatter(x=m["month"], y=m["NDMI"], mode="lines+markers", name="NDMI")
        fig.update_layout(height=330, margin=dict(l=10,r=10,t=15,b=10), yaxis_title="Index", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.caption("Monthly values use available scene-level zonal observations. Months without valid observations are not interpolated.")

with tab_stress:
    st.markdown("#### 🚨 Vegetation Stress Screening")
    st.caption("Screening rule: a 30-day decline of ≥10% in one index indicates Moderate stress; a ≥10% decline in both NDVI and NDMI indicates High stress.")
    if not ndvi_p.empty or not ndmi_p.empty:
        stress = pd.merge(ndvi_p[["date","ndvi"]], ndmi_p[["date","ndmi"]], on="date", how="outer").sort_values("date")
        stress["ndvi_change_pct"] = stress["ndvi"].pct_change() * 100
        stress["ndmi_change_pct"] = stress["ndmi"].pct_change() * 100
        stress["stress"] = "Stable"
        stress.loc[(stress["ndvi_change_pct"] <= -10) | (stress["ndmi_change_pct"] <= -10), "stress"] = "Moderate"
        stress.loc[(stress["ndvi_change_pct"] <= -10) & (stress["ndmi_change_pct"] <= -10), "stress"] = "High"
        fig = go.Figure()
        for level in ["High", "Moderate", "Stable"]:
            d = stress[stress["stress"] == level]
            if not d.empty: fig.add_scatter(x=d["date"], y=d["ndvi"], mode="markers", name=level)
        fig.update_layout(height=320, margin=dict(l=10,r=10,t=15,b=10), yaxis_title="NDVI", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown("#### Recommended Follow-up")
        if stress_level == "HIGH":
            st.error("FIELD REVIEW · Check the fire/hotspot layer, land-cover change, hydrological conditions, access, and field observations for the affected area.")
        elif stress_level == "MODERATE":
            st.warning("REVIEW · Check the recent trend, seasonal conditions, cloud quality, land-cover context, and nearby fire/hydrological signals before assigning field priority.")
        elif stress_level == "LOW":
            st.info("MONITOR · Continue observation and compare the next valid scenes before escalating the response.")
        else:
            st.success("NO ACTION · Continue routine monitoring.")

with tab_data:
    st.markdown("#### 📋 Observation Data")
    left_cols = ["date", "ndvi", "cloudy_pixel_percentage", "source"]
    left_cols = [c for c in left_cols if c in ndvi_p.columns]
    right_cols = ["date", "ndmi"]
    right_cols = [c for c in right_cols if c in ndmi_p.columns]
    combined = pd.merge(ndvi_p[left_cols] if not ndvi_p.empty else pd.DataFrame(columns=left_cols), ndmi_p[right_cols] if not ndmi_p.empty else pd.DataFrame(columns=right_cols), on="date", how="outer").sort_values("date")
    if combined.empty:
        st.info("No observation records are available for the selected period.")
    else:
        st.dataframe(combined, use_container_width=True, hide_index=True)
        d1, d2, d3 = st.columns(3)
        d1.metric("NDVI observations", f"{len(ndvi_p):,}")
        d2.metric("NDMI observations", f"{len(ndmi_p):,}")
        d3.metric("Valid combined dates", f"{len(combined.dropna(subset=[c for c in ['ndvi','ndmi'] if c in combined.columns])):,}" if all(c in combined.columns for c in ['ndvi','ndmi']) else "—")

st.markdown("### 📖 Interpretation Guide")
st.markdown("""
- **NDVI (Normalized Difference Vegetation Index):** indicates vegetation greenness and relative vigor.
- **NDMI (Normalized Difference Moisture Index):** indicates vegetation/canopy moisture conditions.
- **NDVI + NDMI:** using both indicators helps distinguish vegetation-vigor changes from moisture-related stress.
- **Important:** thresholds are screening rules and should be interpreted together with land cover, seasonality, cloud quality, rainfall, fire activity, hydrology, and field observations.
""")

st.caption("Data source: Copernicus Sentinel-2 Surface Reflectance Harmonized. NDVI = (B8 − B4) / (B8 + B4). NDMI = (B8 − B11) / (B8 + B11).")
