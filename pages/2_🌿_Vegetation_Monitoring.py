import pandas as pd
import streamlit as st
import plotly.express as px

from utils.climate.vegetation import load_ndmi, load_ndvi
from utils.ui import setup_page

setup_page()

st.title("🌿 Vegetation Monitoring")
st.caption("SERPRO Project · Sentinel-2 NDVI + NDMI")

ndmi = load_ndmi()
ndvi = load_ndvi()

if ndmi.empty and ndvi.empty:
    st.info("Belum ada data NDVI/NDMI. Jalankan **Update SERPRO NDVI** dan **Update SERPRO NDMI** di GitHub Actions.")
    st.stop()

scopes = ["carbon_project_zone", "project_area"]
valid = [s for s in scopes if s in set(ndmi.get("scope", pd.Series(dtype=str)).unique()).union(set(ndvi.get("scope", pd.Series(dtype=str)).unique()))]
if not valid:
    st.info("Belum ada scope vegetation yang tersedia.")
    st.stop()

scope = st.selectbox(
    "Monitoring scope",
    valid,
    format_func=lambda x: {
        "carbon_project_zone": "Carbon Project Zone",
        "project_area": "Project Area",
    }.get(x, x.replace("_", " ").title()),
)

ndmi_scoped = ndmi[ndmi["scope"] == scope].sort_values("date") if not ndmi.empty else pd.DataFrame()
ndvi_scoped = ndvi[ndvi["scope"] == scope].sort_values("date") if not ndvi.empty else pd.DataFrame()

latest_ndmi = ndmi_scoped.iloc[-1] if not ndmi_scoped.empty else None
latest_ndvi = ndvi_scoped.iloc[-1] if not ndvi_scoped.empty else None

# Current vegetation condition analysis.
def condition_label(value: float | None) -> str:
    if value is None:
        return "No data"
    if value >= 0.70:
        return "High vegetation vigor"
    if value >= 0.50:
        return "Moderate vegetation vigor"
    if value >= 0.30:
        return "Low vegetation vigor"
    return "Very low vegetation vigor"


def stress_label(change_pct: float | None) -> str:
    if change_pct is None:
        return "Insufficient history"
    if change_pct <= -20:
        return "Strong decline"
    if change_pct <= -10:
        return "Moderate decline"
    if change_pct < 0:
        return "Slight decline"
    return "Stable / improving"

ndvi_change_30d = None
if not ndvi_scoped.empty:
    latest_date = ndvi_scoped["date"].max()
    window = ndvi_scoped[ndvi_scoped["date"] >= latest_date - pd.Timedelta(days=30)]
    if len(window) >= 2 and float(window.iloc[0]["ndvi"]) != 0:
        ndvi_change_30d = (float(window.iloc[-1]["ndvi"]) - float(window.iloc[0]["ndvi"])) / abs(float(window.iloc[0]["ndvi"])) * 100

ndmi_change_30d = None
if not ndmi_scoped.empty:
    latest_date_nm = ndmi_scoped["date"].max()
    window_nm = ndmi_scoped[ndmi_scoped["date"] >= latest_date_nm - pd.Timedelta(days=30)]
    if len(window_nm) >= 2 and float(window_nm.iloc[0]["ndmi"]) != 0:
        ndmi_change_30d = (float(window_nm.iloc[-1]["ndmi"]) - float(window_nm.iloc[0]["ndmi"])) / abs(float(window_nm.iloc[0]["ndmi"])) * 100

st.subheader("Current Vegetation Condition")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Latest NDVI", f"{float(latest_ndvi['ndvi']):.3f}" if latest_ndvi is not None else "—")
c2.metric("NDVI 30-day change", f"{ndvi_change_30d:+.1f}%" if ndvi_change_30d is not None else "—")
c3.metric("Latest NDMI", f"{float(latest_ndmi['ndmi']):.3f}" if latest_ndmi is not None else "—")
c4.metric("NDMI 30-day change", f"{ndmi_change_30d:+.1f}%" if ndmi_change_30d is not None else "—")

st.markdown(
    f"**NDVI condition:** {condition_label(float(latest_ndvi['ndvi']) if latest_ndvi is not None else None)}  
"
    f"**NDVI trend:** {stress_label(ndvi_change_30d)}  
"
    f"**NDMI trend:** {stress_label(ndmi_change_30d)}"
)

st.subheader("NDVI Trend")
if ndvi_scoped.empty:
    st.info("Belum ada data NDVI untuk scope ini. Jalankan workflow Update SERPRO NDVI.")
else:
    fig_ndvi = px.line(
        ndvi_scoped,
        x="date",
        y="ndvi",
        markers=True,
        title=f"Sentinel-2 NDVI · {scope.replace('_', ' ').title()}",
        labels={"date": "Date", "ndvi": "NDVI"},
    )
    fig_ndvi.add_hline(y=0, line_dash="dash")
    fig_ndvi.update_layout(height=360, margin=dict(l=20, r=20, t=50, b=20), hovermode="x unified")
    st.plotly_chart(fig_ndvi, use_container_width=True, config={"displayModeBar": False})

st.subheader("NDVI vs NDMI")
combined = pd.merge(
    ndvi_scoped[["date", "ndvi"]],
    ndmi_scoped[["date", "ndmi"]],
    on="date",
    how="outer",
).sort_values("date")
if not combined.empty:
    long = combined.melt(id_vars="date", value_vars=[c for c in ["ndvi", "ndmi"] if c in combined.columns], var_name="Index", value_name="Value")
    long["Index"] = long["Index"].map({"ndvi": "NDVI · vegetation vigor", "ndmi": "NDMI · vegetation moisture"})
    fig_compare = px.line(long, x="date", y="Value", color="Index", markers=True, title="Vegetation condition and moisture")
    fig_compare.update_layout(height=360, margin=dict(l=20, r=20, t=50, b=20), hovermode="x unified")
    st.plotly_chart(fig_compare, use_container_width=True, config={"displayModeBar": False})
else:
    st.info("Belum ada data gabungan NDVI/NDMI.")

st.subheader("Scope Comparison")
rows = []
for scope_key in scopes:
    n = ndvi[ndvi["scope"] == scope_key].sort_values("date") if not ndvi.empty else pd.DataFrame()
    m = ndmi[ndmi["scope"] == scope_key].sort_values("date") if not ndmi.empty else pd.DataFrame()
    row = {"Scope": {"carbon_project_zone": "Carbon Project Zone", "project_area": "Project Area"}.get(scope_key, scope_key)}
    if not n.empty:
        row["Latest NDVI"] = float(n.iloc[-1]["ndvi"])
        row["NDVI Date"] = n.iloc[-1]["date"].date().isoformat()
    else:
        row["Latest NDVI"] = None
        row["NDVI Date"] = None
    if not m.empty:
        row["Latest NDMI"] = float(m.iloc[-1]["ndmi"])
        row["NDMI Date"] = m.iloc[-1]["date"].date().isoformat()
    else:
        row["Latest NDMI"] = None
        row["NDMI Date"] = None
    rows.append(row)
comparison = pd.DataFrame(rows)
st.dataframe(comparison, use_container_width=True, hide_index=True)

st.markdown("### Interpretation")
st.markdown(
    "- **NDVI** menggambarkan kondisi kehijauan/vigor vegetasi. Penurunan berkelanjutan dapat menjadi indikasi penurunan kondisi vegetasi, tetapi perlu dibaca bersama tutupan lahan, fenologi, dan kualitas observasi.\n"
    "- **NDMI** menggambarkan kelembapan vegetasi/canopy moisture. Penurunan NDMI dapat menunjukkan peningkatan kekeringan atau water stress pada vegetasi.\n"
    "- **Kombinasi NDVI + NDMI** dipakai untuk membedakan penurunan vigor vegetasi dari tekanan kelembapan. Keduanya menjadi indikator pendukung, bukan bukti tunggal adanya degradasi atau kerusakan." 
)

st.caption("Sources: COPERNICUS/S2_SR_HARMONIZED. NDVI = (B8 − B4) / (B8 + B4). NDMI = (B8 − B11) / (B8 + B11). Current pipeline uses scene cloud filtering + SCL masking and 90-day lookback.")
