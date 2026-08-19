from io import BytesIO
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.climate.anomaly import load_anomaly
from utils.climate.rainfall import load_rainfall
from utils.climate.risk import load_risk
from utils.climate.spi import load_spi
from utils.ui import setup_page

setup_page()

st.markdown(
    """
    <div class="hero">
      <div class="eyebrow">SERPRO PROJECT · CLIMATE MONITORING</div>
      <div class="title">📊 Historical Climate</div>
      <div class="subtitle">Historical climate evidence for monitoring, anomaly analysis, drought/wetness assessment and climate-risk screening.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

rainfall = load_rainfall()
anomaly = load_anomaly()
spi = load_spi()
risk = load_risk()

if rainfall.empty:
    st.warning("Belum ada data rainfall otomatis. Jalankan workflow Update SERPRO Rainfall di GitHub Actions terlebih dahulu.")
    st.stop()

rainfall["date"] = pd.to_datetime(rainfall["date"], errors="coerce")
rainfall = rainfall.dropna(subset=["date"]).sort_values("date")
scopes = [s for s in ["project_area", "carbon_project_zone"] if s in rainfall["scope"].astype(str).unique()]
if not scopes:
    st.error("Tidak ditemukan monitoring scope yang valid pada data rainfall.")
    st.stop()

st.markdown('<div class="panel" style="margin-bottom:14px">', unsafe_allow_html=True)
c1, c2, c3 = st.columns([1.3, 1, 1])
with c1:
    scope = st.selectbox(
        "Monitoring area",
        scopes,
        format_func=lambda x: {
            "project_area": "🟢 SERPRO Project Area · analysis",
            "carbon_project_zone": "🟣 SERPRO Carbon Project Zone · reference",
        }.get(x, x.replace("_", " ").title()),
    )
scoped_all = rainfall[rainfall["scope"].astype(str) == scope].copy().sort_values("date")
min_date = scoped_all["date"].min().date()
max_date = scoped_all["date"].max().date()
with c2:
    start_date = st.date_input("Start date", value=max(min_date, max_date - pd.Timedelta(days=29)), min_value=min_date, max_value=max_date)
with c3:
    end_date = st.date_input("End date", value=max_date, min_value=min_date, max_value=max_date)
quick = st.selectbox("Quick range", ["Custom", "Latest 7D", "Latest 30D", "Latest 90D", "Year to date"], index=2)
if quick != "Custom":
    start_date = {
        "Latest 7D": max(min_date, max_date - pd.Timedelta(days=6)),
        "Latest 30D": max(min_date, max_date - pd.Timedelta(days=29)),
        "Latest 90D": max(min_date, max_date - pd.Timedelta(days=89)),
        "Year to date": max(min_date, pd.Timestamp(max_date.year, 1, 1).date()),
    }[quick]
    end_date = max_date
st.markdown('</div>', unsafe_allow_html=True)

if start_date > end_date:
    st.error("Start date harus lebih kecil atau sama dengan End date.")
    st.stop()

view = scoped_all[(scoped_all["date"].dt.date >= start_date) & (scoped_all["date"].dt.date <= end_date)].copy()

with st.expander("ℹ️ Data Quality & Information", expanded=True):
    st.markdown("### Data sources & processing")
    q1, q2, q3 = st.columns(3)
    with q1:
        st.markdown("**Historical rainfall**")
        st.write("CHIRPS v2 Final")
        st.caption("Monthly rainfall derived from daily CHIRPS precipitation and spatially averaged over the selected SERPRO boundary.")
    with q2:
        st.markdown("**Rainfall anomaly baseline**")
        st.write("CHIRPS v2 Final · 1991–2020")
        st.caption("Current rainfall is compared with the climatological mean for the corresponding baseline period.")
    with q3:
        st.markdown("**Drought / wetness indicator**")
        st.write("SPI-3 & SPI-6")
        st.caption("Standardized wetness/dryness indicators based on the historical rainfall distribution.")

    st.markdown("### Methodology at a glance")
    st.markdown(
        """
        1. **Historical rainfall:** CHIRPS daily precipitation is summed to monthly rainfall and spatially averaged over each SERPRO scope.
        2. **30-year historical window:** the dashboard uses the latest complete 30-year period available in the CHIRPS series, **1996–2025**.
        3. **Rainfall anomaly:** the operational rainfall product is compared with the CHIRPS 1991–2020 climatological baseline.
        4. **SPI:** SPI-3 and SPI-6 represent standardized wetness/dryness relative to the historical rainfall distribution.
        5. **Coordinates:** downloaded historical observations include representative scope centroid longitude/latitude in **EPSG:4326**.
        """
    )

    st.markdown("### Current data quality")
    selected_days = int(view["date"].dt.normalize().nunique()) if not view.empty else 0
    expected_days = int((pd.Timestamp(end_date) - pd.Timestamp(start_date)).days + 1)
    missing_days = max(expected_days - selected_days, 0)
    latest_processing = "—"
    if "processing_time_utc" in scoped_all.columns:
        times = pd.to_datetime(scoped_all["processing_time_utc"], errors="coerce", utc=True).dropna()
        if not times.empty:
            latest_processing = times.max().strftime("%Y-%m-%d %H:%M UTC")
    qc1, qc2, qc3, qc4 = st.columns(4)
    qc1.metric("Observations in period", selected_days)
    qc2.metric("Expected calendar days", expected_days)
    qc3.metric("Missing days", missing_days)
    qc4.metric("Latest processing", latest_processing)

    st.info(
        "Historical climate products are analytical evidence and are not weather forecasts. "
        "BMKG Local Weather Forecast remains on its own sub-page and is excluded from historical rainfall, anomaly, SPI and climate-risk calculations."
    )

tab_snapshot, tab_rain, tab_anom, tab_spi, tab_trend = st.tabs(
    ["Climate Snapshot", "Historical Rainfall", "Rainfall Anomaly", "SPI-3 / SPI-6", "Climate Trend"]
)

with tab_snapshot:
    if view.empty:
        st.info("Tidak ada data pada periode yang dipilih.")
    else:
        latest = view.iloc[-1]
        latest_rain = float(latest["rainfall_mm"])
        total_30d = float(view.tail(30)["rainfall_mm"].sum())
        anomaly_latest = None
        if not anomaly.empty:
            a = anomaly.copy()
            a["date"] = pd.to_datetime(a["date"], errors="coerce")
            a = a[(a["scope"].astype(str) == scope) & (a["date"] >= pd.Timestamp(start_date)) & (a["date"] <= pd.Timestamp(end_date))].sort_values("date")
            if not a.empty and "anomaly_30d_pct" in a.columns and pd.notna(a.iloc[-1]["anomaly_30d_pct"]):
                anomaly_latest = float(a.iloc[-1]["anomaly_30d_pct"])
        risk_latest = None
        risk_level = "—"
        if not risk.empty and "scope" in risk.columns:
            rr = risk[risk["scope"].astype(str) == scope].copy().sort_values("date")
            if not rr.empty:
                risk_latest = rr.iloc[-1].get("integrated_risk_score", rr.iloc[-1].get("risk_score"))
                risk_level = str(rr.iloc[-1].get("risk_level", "—")).replace("_", " ").upper()
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Latest rainfall", f"{latest_rain:.2f} mm", latest["date"].strftime("%d %b %Y"))
        k2.metric("Rainfall · 30 days", f"{total_30d:.1f} mm")
        k3.metric("30-day anomaly", f"{anomaly_latest:+.1f}%" if anomaly_latest is not None else "—")
        k4.metric("Climate risk", f"{float(risk_latest):.1f}" if pd.notna(risk_latest) else "—", risk_level)

        st.markdown("### Monitoring summary")
        st.dataframe(
            view[[c for c in ["date", "scope", "rainfall_mm", "source", "processing_time_utc"] if c in view.columns]].tail(30),
            use_container_width=True,
            hide_index=True,
        )

with tab_rain:
    historical_path = Path("data/processed/climate/rainfall/chirps_monthly_1981_2025.csv")
    if not historical_path.exists():
        st.warning("Data historical CHIRPS belum tersedia. Jalankan workflow Build CHIRPS Baseline terlebih dahulu.")
    else:
        hist = pd.read_csv(historical_path)
        hist["year"] = pd.to_numeric(hist["year"], errors="coerce")
        hist["month"] = pd.to_numeric(hist["month"], errors="coerce")
        hist["rainfall_mm"] = pd.to_numeric(hist["rainfall_mm"], errors="coerce")
        hist = hist.dropna(subset=["year", "month", "rainfall_mm"])
        hist = hist[(hist["year"] >= 1996) & (hist["year"] <= 2025)].copy()
        hist = hist[hist["scope"].astype(str) == scope].sort_values(["year", "month"])

        if hist.empty:
            st.info("Tidak ada observasi CHIRPS 1996–2025 untuk scope yang dipilih.")
        else:
            hist["year"] = hist["year"].astype(int)
            hist["month"] = hist["month"].astype(int)
            if "longitude" not in hist.columns or "latitude" not in hist.columns:
                st.warning("Kolom longitude/latitude belum tersedia pada dataset CHIRPS. Jalankan ulang workflow Build CHIRPS Baseline untuk memperbarui metadata koordinat.")
                hist["longitude"] = pd.NA
                hist["latitude"] = pd.NA

            hist["date"] = pd.to_datetime(
                hist["year"].astype(str) + "-" + hist["month"].astype(str).str.zfill(2) + "-01",
                errors="coerce",
            )

            annual = hist.groupby("year", as_index=False)["rainfall_mm"].sum()
            monthly = hist.groupby("month", as_index=False)["rainfall_mm"].mean()
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Period", "1996–2025")
            s2.metric("Years", f"{hist['year'].nunique()}")
            s3.metric("Observations", f"{len(hist):,}")
            s4.metric("30-year mean", f"{hist['rainfall_mm'].mean():.1f} mm/month")

            st.markdown("### Monthly historical rainfall")
            fig = go.Figure()
            fig.add_scatter(x=hist["date"], y=hist["rainfall_mm"], mode="lines", name="Monthly rainfall")
            fig.update_layout(height=420, margin=dict(l=10, r=10, t=20, b=10), yaxis_title="Rainfall (mm/month)", xaxis_title="Year")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            st.markdown("### Annual rainfall · 1996–2025")
            fig2 = go.Figure()
            fig2.add_bar(x=annual["year"], y=annual["rainfall_mm"], name="Annual rainfall")
            fig2.update_layout(height=360, margin=dict(l=10, r=10, t=20, b=10), yaxis_title="Rainfall (mm/year)", xaxis_title="Year")
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

            st.markdown("### Observation metadata & download")
            st.caption("Each record contains the observation year/month, monitoring scope, representative centroid longitude/latitude (EPSG:4326), rainfall, and source dataset.")
            export_cols = ["year", "month", "scope", "longitude", "latitude", "rainfall_mm", "source"]
            export_df = hist[[c for c in export_cols if c in hist.columns]].copy()
            st.dataframe(export_df, use_container_width=True, hide_index=True)

            csv_bytes = export_df.to_csv(index=False).encode("utf-8")
            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                export_df.to_excel(writer, index=False, sheet_name="Observation")
            excel_bytes = excel_buffer.getvalue()

            d1, d2 = st.columns(2)
            with d1:
                st.download_button(
                    "⬇️ Download Observation CSV",
                    data=csv_bytes,
                    file_name=f"SERPRO_Historical_Rainfall_1996_2025_{scope}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with d2:
                st.download_button(
                    "⬇️ Download Observation XLSX",
                    data=excel_bytes,
                    file_name=f"SERPRO_Historical_Rainfall_1996_2025_{scope}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

            with st.expander("Metadata definition"):
                st.markdown(
                    """
                    - **year / month** — observation period.
                    - **scope** — `project_area` or `carbon_project_zone`.
                    - **longitude / latitude** — representative centroid of the selected SERPRO scope, EPSG:4326.
                    - **rainfall_mm** — monthly rainfall, calculated from the sum of daily CHIRPS precipitation and spatially averaged over the scope.
                    - **source** — CHIRPS Earth Engine collection identifier.
                    """
                )

with tab_anom:
    if anomaly.empty:
        st.info("Rainfall anomaly output belum tersedia.")
    else:
        a = anomaly.copy()
        a["date"] = pd.to_datetime(a["date"], errors="coerce")
        a = a[(a["scope"].astype(str) == scope) & (a["date"] >= pd.Timestamp(start_date)) & (a["date"] <= pd.Timestamp(end_date))].sort_values("date")
        if a.empty:
            st.info("Tidak ada anomaly data pada periode yang dipilih.")
        else:
            fig = go.Figure()
            if "anomaly_30d_pct" in a.columns:
                fig.add_scatter(x=a["date"], y=a["anomaly_30d_pct"], mode="lines+markers", name="30-day anomaly (%)")
            fig.add_hline(y=0, line_dash="dash")
            fig.update_layout(height=430, margin=dict(l=10, r=10, t=20, b=10), yaxis_title="Anomaly (%)", xaxis_title="Date")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.dataframe(a, use_container_width=True, hide_index=True)

with tab_spi:
    if spi.empty:
        st.info("SPI-3 / SPI-6 output belum tersedia.")
    else:
        s = spi.copy()
        if "date" in s.columns:
            s["date"] = pd.to_datetime(s["date"], errors="coerce")
        if "scope" in s.columns:
            s = s[s["scope"].astype(str) == scope]
        s = s[(s["date"] >= pd.Timestamp(start_date)) & (s["date"] <= pd.Timestamp(end_date))].sort_values("date")
        if s.empty:
            st.info("Tidak ada SPI data pada periode yang dipilih.")
        else:
            fig = go.Figure()
            for col, label in [("spi_3", "SPI-3"), ("spi_6", "SPI-6")]:
                if col in s.columns:
                    fig.add_scatter(x=s["date"], y=s[col], mode="lines+markers", name=label)
            fig.add_hline(y=0, line_dash="dash")
            fig.update_layout(height=430, margin=dict(l=10, r=10, t=20, b=10), yaxis_title="SPI", xaxis_title="Date")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.dataframe(s, use_container_width=True, hide_index=True)

with tab_trend:
    if view.empty:
        st.info("Tidak ada data trend pada periode yang dipilih.")
    else:
        fig = go.Figure()
        fig.add_scatter(x=view["date"], y=view["rainfall_mm"], mode="lines+markers", name="Rainfall")
        fig.update_layout(height=430, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="Rainfall (mm)", xaxis_title="Date")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown("### Climate risk history")
        if not risk.empty and "scope" in risk.columns:
            rr = risk[risk["scope"].astype(str) == scope].copy().sort_values("date")
            if not rr.empty:
                score_col = "integrated_risk_score" if "integrated_risk_score" in rr.columns else "risk_score" if "risk_score" in rr.columns else None
                if score_col:
                    rf = go.Figure()
                    rf.add_scatter(x=rr["date"], y=rr[score_col], mode="lines+markers", name="Climate Risk")
                    rf.update_layout(height=330, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="Risk index")
                    st.plotly_chart(rf, use_container_width=True, config={"displayModeBar": False})
                st.dataframe(rr, use_container_width=True, hide_index=True)
            else:
                st.info("Belum ada climate risk output untuk scope ini.")
