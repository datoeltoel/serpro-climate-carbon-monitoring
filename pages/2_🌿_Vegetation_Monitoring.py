import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from utils.climate.vegetation import load_ndmi, load_ndvi, load_ndvi_annual
from utils.ui import setup_page

setup_page()

# -----------------------------------------------------------------------------
# Page styling
# -----------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .veg-kpi {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        padding: 14px 15px;
        min-height: 118px;
        box-shadow: 0 2px 8px rgba(15,23,42,.05);
    }
    .veg-kpi-label {font-size:.76rem;color:#64748b;font-weight:700;text-transform:uppercase;letter-spacing:.04em}
    .veg-kpi-value {font-size:1.65rem;font-weight:800;line-height:1.15;margin-top:7px;color:#0f172a}
    .veg-kpi-sub {font-size:.78rem;margin-top:7px;font-weight:700}
    .veg-note {font-size:.82rem;color:#64748b}
    .interpret-card {
        border:1px solid #e5e7eb;border-radius:14px;padding:16px;background:#fff;margin-bottom:10px;
    }
    @media (max-width: 768px) {
      .veg-kpi {min-height:105px;padding:12px}
      .veg-kpi-value {font-size:1.35rem}
      .veg-kpi-label {font-size:.68rem}
      .veg-kpi-sub {font-size:.72rem}
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("# 🌿 Vegetation Monitoring")
st.caption("SERPRO Project · Sentinel-2 vegetation health, vigor and canopy moisture monitoring")

ndmi = load_ndmi()
ndvi = load_ndvi()
annual = load_ndvi_annual()

for df in (ndmi, ndvi):
    if not df.empty and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

if ndmi.empty and ndvi.empty:
    st.info("No NDVI/NDMI data is currently available. Run the Update SERPRO NDVI and Update SERPRO NDMI workflows.")
    st.stop()

scope_keys = sorted(
    set(ndmi.get("scope", pd.Series(dtype=str)).dropna().astype(str))
    | set(ndvi.get("scope", pd.Series(dtype=str)).dropna().astype(str))
)
if not scope_keys:
    st.info("No vegetation monitoring scope is currently available.")
    st.stop()

scope_labels = {
    "carbon_project_zone": "🟣 Carbon Project Zone",
    "project_area": "🟢 Project Area",
}

# -----------------------------------------------------------------------------
# Filters
# -----------------------------------------------------------------------------
c_scope, c_period = st.columns([1.15, 1], gap="medium")
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
        min_date, max_date = all_dates.min().date(), all_dates.max().date()
        date_range = st.date_input(
            "Monitoring period",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )
    else:
        date_range = None

if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    start_date = pd.Timestamp(date_range[0])
    end_date = pd.Timestamp(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    ndvi_p = ndvi_s[(ndvi_s["date"] >= start_date) & (ndvi_s["date"] <= end_date)].copy()
    ndmi_p = ndmi_s[(ndmi_s["date"] >= start_date) & (ndmi_s["date"] <= end_date)].copy()
else:
    ndvi_p, ndmi_p = ndvi_s.copy(), ndmi_s.copy()

ndvi_p = ndvi_p.sort_values("date") if not ndvi_p.empty else ndvi_p
ndmi_p = ndmi_p.sort_values("date") if not ndmi_p.empty else ndmi_p


def pct_change(df, col, days):
    if df.empty or col not in df.columns or len(df) < 2:
        return None
    latest = df["date"].max()
    w = df[df["date"] >= latest - pd.Timedelta(days=days)]
    if len(w) < 2:
        return None
    first, last = float(w.iloc[0][col]), float(w.iloc[-1][col])
    return None if first == 0 else (last - first) / abs(first) * 100


def index_status(value):
    if value is None or pd.isna(value):
        return "No data", "#64748b"
    value = float(value)
    if value >= 0.70:
        return "Good vigor", "#15803d"
    if value >= 0.50:
        return "Moderate vigor", "#b45309"
    if value >= 0.30:
        return "Low vigor", "#c2410c"
    return "Very low vigor", "#b91c1c"


def moisture_status(value):
    if value is None or pd.isna(value):
        return "No data", "#64748b"
    value = float(value)
    if value >= 0.40:
        return "Moist", "#15803d"
    if value >= 0.20:
        return "Moderate", "#b45309"
    if value >= 0.00:
        return "Drying", "#c2410c"
    return "Low moisture", "#b91c1c"


latest_ndvi = float(ndvi_p.iloc[-1]["ndvi"]) if not ndvi_p.empty and "ndvi" in ndvi_p.columns else None
latest_ndmi = float(ndmi_p.iloc[-1]["ndmi"]) if not ndmi_p.empty and "ndmi" in ndmi_p.columns else None
ndvi_30 = pct_change(ndvi_p, "ndvi", 30)
ndmi_30 = pct_change(ndmi_p, "ndmi", 30)
ndvi_90 = pct_change(ndvi_p, "ndvi", 90)
ndmi_90 = pct_change(ndmi_p, "ndmi", 90)
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

stress_color = {
    "HIGH": "#b91c1c",
    "MODERATE": "#b45309",
    "LOW": "#2563eb",
    "STABLE": "#15803d",
}[stress_level]

# -----------------------------------------------------------------------------
# KPI cards - responsive: 2 columns on mobile / 5 columns on wide screens
# -----------------------------------------------------------------------------
st.markdown("### 🌱 Vegetation Condition Overview")
kpis = [
    ("🌿", "NDVI", f"{latest_ndvi:.3f}" if latest_ndvi is not None else "—", ndvi_label, ndvi_color),
    ("💧", "NDMI", f"{latest_ndmi:.3f}" if latest_ndmi is not None else "—", ndmi_label, ndmi_color),
    ("📉", "NDVI · 30D", f"{ndvi_30:+.1f}%" if ndvi_30 is not None else "—", "vs. 30 days", "#b91c1c" if ndvi_30 is not None and ndvi_30 < 0 else "#15803d"),
    ("💦", "NDMI · 30D", f"{ndmi_30:+.1f}%" if ndmi_30 is not None else "—", "vs. 30 days", "#b91c1c" if ndmi_30 is not None and ndmi_30 < 0 else "#15803d"),
    ("⚠️", "VEGETATION STRESS", stress_level, "NDVI + NDMI screening", stress_color),
]

cols = st.columns(5, gap="small")
for col, (icon, title, value, sub, color) in zip(cols, kpis):
    with col:
        st.markdown(
            f'<div class="veg-kpi">'
            f'<div class="veg-kpi-label">{icon} {title}</div>'
            f'<div class="veg-kpi-value">{value}</div>'
            f'<div class="veg-kpi-sub" style="color:{color}">{sub}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

if stress_level == "HIGH":
    st.error("🚨 High vegetation stress: both NDVI and NDMI declined by at least 10% over the last 30 days. Prioritize field verification and review fire, land-cover and hydrological context.")
elif stress_level == "MODERATE":
    st.warning("⚠️ Moderate vegetation stress: at least one indicator declined by 10% or more over the last 30 days. Review spatial context and recent environmental conditions.")
elif stress_level == "LOW":
    st.info("ℹ️ Low vegetation stress signal: a recent decline is present, but the moderate-stress threshold has not been reached.")
else:
    st.success("✅ No vegetation stress signal detected under the current screening rules.")

# -----------------------------------------------------------------------------
# Tabs
# -----------------------------------------------------------------------------
tab_overview, tab_trend, tab_stress, tab_data = st.tabs(
    ["Overview", "Trends", "Stress Analysis", "Data & Quality"]
)

with tab_overview:
    left, right = st.columns([1.55, 1], gap="large")
    with left:
        st.markdown("#### 📈 Recent Vegetation Trend")
        if not ndvi_p.empty or not ndmi_p.empty:
            fig = go.Figure()
            if not ndvi_p.empty:
                fig.add_scatter(
                    x=ndvi_p["date"], y=ndvi_p["ndvi"], mode="lines+markers",
                    name="NDVI · vegetation vigor"
                )
            if not ndmi_p.empty:
                fig.add_scatter(
                    x=ndmi_p["date"], y=ndmi_p["ndmi"], mode="lines+markers",
                    name="NDMI · canopy moisture"
                )
            fig.update_layout(
                height=360, margin=dict(l=10, r=10, t=15, b=10),
                yaxis_title="Index", hovermode="x unified", legend=dict(orientation="h")
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No observations are available for the selected period.")

    with right:
        st.markdown("#### 🧭 Current Interpretation")
        st.markdown(f"**Vegetation vigor** · {ndvi_label}")
        st.caption(f"NDVI = {latest_ndvi:.3f}" if latest_ndvi is not None else "NDVI = no data")
        st.markdown(f"**Canopy moisture** · {ndmi_label}")
        st.caption(f"NDMI = {latest_ndmi:.3f}" if latest_ndmi is not None else "NDMI = no data")
        st.markdown(f"**Combined stress** · {stress_level}")
        st.caption("Conservative screening indicator; not standalone evidence of degradation or damage.")
        st.metric("NDVI · 90-day change", f"{ndvi_90:+.1f}%" if ndvi_90 is not None else "—")
        st.metric("NDMI · 90-day change", f"{ndmi_90:+.1f}%" if ndmi_90 is not None else "—")

        if stress_level == "HIGH":
            st.error("Priority: field verification")
        elif stress_level == "MODERATE":
            st.warning("Priority: environmental review")
        else:
            st.success("Priority: routine monitoring")

with tab_trend:
    st.markdown("#### 📅 Annual NDVI Trend · 2015–2025")
    if annual.empty:
        st.warning("The annual NDVI dataset is not available. Run the Update SERPRO NDVI workflow.")
    else:
        annual_s = annual[annual["scope"].astype(str) == scope].copy()
        if annual_s.empty:
            st.info("No annual NDVI records are available for this scope.")
        else:
            annual_s["year"] = pd.to_numeric(annual_s["year"], errors="coerce")
            annual_s["ndvi_mean"] = pd.to_numeric(annual_s["ndvi_mean"], errors="coerce")
            annual_s = annual_s.dropna(subset=["year", "ndvi_mean"]).sort_values("year")
            annual_s = annual_s[(annual_s["year"] >= 2015) & (annual_s["year"] <= 2025)]

            fig = go.Figure()
            fig.add_scatter(
                x=annual_s["year"], y=annual_s["ndvi_mean"], mode="lines+markers",
                name="Annual NDVI"
            )
            fig.update_layout(
                height=370, margin=dict(l=10, r=10, t=15, b=10),
                xaxis=dict(dtick=1), yaxis_title="Mean NDVI", xaxis_title="Year",
                hovermode="x unified"
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.caption("Annual NDVI supports long-term vegetation monitoring. It is not a carbon-accounting output.")

            if not annual_s.empty:
                latest_a, first_a = annual_s.iloc[-1], annual_s.iloc[0]
                a1, a2, a3 = st.columns(3)
                with a1:
                    st.metric("Latest annual NDVI", f"{float(latest_a['ndvi_mean']):.3f}", str(int(latest_a["year"])))
                with a2:
                    st.metric("Change vs. first year", f"{float(latest_a['ndvi_mean'] - first_a['ndvi_mean']):+.3f}")
                with a3:
                    obs = pd.to_numeric(annual_s.get("observation_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
                    st.metric("Annual observations", f"{int(obs):,}")

    st.markdown("#### 📆 Monthly Vegetation Trend")
    monthly_frames = []
    if not ndvi_s.empty and "ndvi" in ndvi_s.columns:
        x = ndvi_s.copy()
        x["month"] = x["date"].dt.to_period("M").dt.to_timestamp()
        monthly_frames.append(x.groupby("month", as_index=False)["ndvi"].mean().rename(columns={"ndvi": "NDVI"}))
    if not ndmi_s.empty and "ndmi" in ndmi_s.columns:
        x = ndmi_s.copy()
        x["month"] = x["date"].dt.to_period("M").dt.to_timestamp()
        monthly_frames.append(x.groupby("month", as_index=False)["ndmi"].mean().rename(columns={"ndmi": "NDMI"}))

    if monthly_frames:
        m = monthly_frames[0]
        if len(monthly_frames) > 1:
            m = pd.merge(m, monthly_frames[1], on="month", how="outer")
        fig = go.Figure()
        if "NDVI" in m:
            fig.add_scatter(x=m["month"], y=m["NDVI"], mode="lines+markers", name="NDVI")
        if "NDMI" in m:
            fig.add_scatter(x=m["month"], y=m["NDMI"], mode="lines+markers", name="NDMI")
        fig.update_layout(height=330, margin=dict(l=10, r=10, t=15, b=10), yaxis_title="Index", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.caption("Monthly values use available scene-level zonal observations. Missing months are not interpolated.")

with tab_stress:
    st.markdown("#### 🚨 Vegetation Stress Screening")
    st.caption("Screening rule: ≥10% decline in one index over 30 days = Moderate; ≥10% decline in both NDVI and NDMI = High.")

    if not ndvi_p.empty or not ndmi_p.empty:
        stress = pd.merge(
            ndvi_p[["date", "ndvi"]] if not ndvi_p.empty else pd.DataFrame(columns=["date", "ndvi"]),
            ndmi_p[["date", "ndmi"]] if not ndmi_p.empty else pd.DataFrame(columns=["date", "ndmi"]),
            on="date", how="outer"
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
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=15, b=10), yaxis_title="NDVI", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        st.markdown("#### Recommended Follow-up")
        if stress_level == "HIGH":
            st.error("FIELD REVIEW · Check fire/hotspot activity, land-cover change, hydrological conditions, access and field observations.")
        elif stress_level == "MODERATE":
            st.warning("REVIEW · Check recent trend, seasonality, cloud quality, land-cover context and nearby fire/hydrological signals.")
        elif stress_level == "LOW":
            st.info("MONITOR · Continue observation and compare the next valid scenes before escalating field priority.")
        else:
            st.success("NO ACTION · Continue routine monitoring.")

with tab_data:
    st.markdown("#### 📋 Observation Data")
    ndvi_cols = [c for c in ["date", "ndvi", "cloudy_pixel_percentage", "source"] if c in ndvi_p.columns]
    ndmi_cols = [c for c in ["date", "ndmi", "cloudy_pixel_percentage", "source"] if c in ndmi_p.columns]

    if not ndvi_p.empty:
        st.markdown("**NDVI observations**")
        st.dataframe(ndvi_p[ndvi_cols].sort_values("date", ascending=False), use_container_width=True, hide_index=True)
    if not ndmi_p.empty:
        st.markdown("**NDMI observations**")
        st.dataframe(ndmi_p[ndmi_cols].sort_values("date", ascending=False), use_container_width=True, hide_index=True)

    st.markdown("#### ℹ️ Interpretation Guide")
    st.markdown(
        "- **NDVI (Normalized Difference Vegetation Index):** vegetation greenness and relative vigor.\n"
        "- **NDMI (Normalized Difference Moisture Index):** vegetation/canopy moisture conditions.\n"
        "- **Combined stress:** conservative screening using both indicators; it is not standalone evidence of degradation.\n"
        "- Interpret vegetation signals together with rainfall, fire activity, hydrology, land-cover change, cloud quality and field observations."
    )
    st.caption("Data source: Copernicus Sentinel-2 Surface Reflectance Harmonized. NDVI = (B8 − B4) / (B8 + B4); NDMI = (B8 − B11) / (B8 + B11).")
