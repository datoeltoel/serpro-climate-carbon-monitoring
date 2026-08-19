import pandas as pd
import streamlit as st
import plotly.express as px

from utils.climate.rainfall import load_rainfall
from utils.climate.anomaly import load_anomaly
from utils.climate.spi import load_spi
from utils.climate.risk import load_risk
from utils.climate.bmkg import load_bmkg_forecast
from utils.ui import setup_page

setup_page()

st.markdown(
    """
    <style>
    :root {
        --serpro-deep:#156064; --serpro-green:#00C49A; --serpro-yellow:#F8E16C;
        --serpro-coral:#FFC2B4; --serpro-orange:#FB8F67; --serpro-ink:#16383A;
        --serpro-muted:#5E7779; --serpro-line:#DDE9E7; --serpro-soft:#F5FAF9;
    }
    .climate-hero{background:linear-gradient(135deg,#F5FAF9 0%,#FFF 72%);border:1px solid var(--serpro-line);border-radius:18px;padding:22px 24px;margin-bottom:16px}
    .climate-eyebrow{color:var(--serpro-deep);font-size:.72rem;font-weight:800;letter-spacing:.13em;text-transform:uppercase}
    .climate-title{color:var(--serpro-ink);font-size:2rem;font-weight:850;margin:2px 0 4px}
    .climate-subtitle{color:var(--serpro-muted);font-size:.92rem;margin:0}
    .section-title{color:var(--serpro-ink);font-size:1.18rem;font-weight:800;margin:22px 0 8px}
    .section-note{color:var(--serpro-muted);font-size:.78rem;margin:-3px 0 10px}
    .kpi,.status-card,.spi-card{border:1px solid var(--serpro-line);border-radius:15px}
    .kpi{padding:15px 16px;min-height:112px;box-shadow:0 2px 10px rgba(21,96,100,.06)}
    .kpi-green{background:#E8FBF5;border-color:#BCEFE1}.kpi-deep{background:#EAF5F5;border-color:#C6E2E2}
    .kpi-yellow{background:#FFF9D9;border-color:#F3E7A1}.kpi-coral{background:#FFF0EC;border-color:#FFD1C7}
    .kpi-label,.status-label,.spi-label{color:var(--serpro-muted);font-size:.72rem;font-weight:800;text-transform:uppercase;letter-spacing:.05em}
    .kpi-value{color:var(--serpro-ink);font-size:1.65rem;font-weight:850;line-height:1.15;margin-top:7px}
    .kpi-note,.status-desc{color:var(--serpro-muted);font-size:.72rem;margin-top:6px}
    .kpi-green .kpi-value{color:#087A65}.kpi-deep .kpi-value{color:var(--serpro-deep)}
    .kpi-yellow .kpi-value{color:#8A6B00}.kpi-coral .kpi-value{color:#D94F35}
    .status-card{padding:17px 18px;min-height:126px}.status-drought{background:#FFF0EC;border-color:#FFD1C7}
    .status-risk{background:#FFF3E8;border-color:#FFD2B8}.status-observation{background:#E8FBF5;border-color:#BCEFE1}
    .status-value{color:var(--serpro-ink);font-size:1.55rem;font-weight:850;margin-top:5px;line-height:1.15}
    .status-drought .status-value{color:#D94F35;font-size:1.28rem}.status-risk .status-value{color:#D96822;font-size:1.35rem}
    .status-observation .status-value{color:#087A65;font-size:1.35rem}
    .spi-card{padding:15px 16px;min-height:100px}.spi-blue{background:#EAF5F5;border-color:#C6E2E2}.spi-yellow{background:#FFF9D9;border-color:#F3E7A1}
    .spi-value{color:var(--serpro-ink);font-size:1.35rem;font-weight:800;margin-top:6px;line-height:1.1}
    .info-strip{background:#F5FAF9;border:1px solid var(--serpro-line);border-radius:14px;padding:13px 16px;color:var(--serpro-muted);font-size:.78rem}
    .legend-row{display:flex;gap:10px;flex-wrap:wrap;margin-top:8px}.legend-item{display:flex;align-items:center;gap:6px;font-size:.74rem;color:var(--serpro-muted)}
    .dot{width:10px;height:10px;border-radius:50%;display:inline-block}
    </style>
    """,
    unsafe_allow_html=True,
)

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

st.markdown('<div class="section-title">Monitoring area & period</div>', unsafe_allow_html=True)
fc1, fc2, fc3 = st.columns([1.3, 1, .9])
with fc1:
    scope = st.selectbox(
        "Monitoring area", valid_scopes,
        format_func=lambda x: {"project_area":"🟢 SERPRO Project Area · analysis","carbon_project_zone":"🟣 Carbon Project Zone · reference"}.get(x, x.replace("_"," ").title()),
    )
scoped_all = rainfall[rainfall["scope"] == scope].copy().sort_values("date")
if scoped_all.empty:
    st.warning("Belum ada data rainfall untuk scope yang dipilih.")
    st.stop()
min_date, max_date = scoped_all["date"].min().date(), scoped_all["date"].max().date()
with fc2:
    start_date = st.date_input("Start date", value=max(min_date, max_date-pd.Timedelta(days=29)), min_value=min_date, max_value=max_date)
with fc3:
    end_date = st.date_input("End date", value=max_date, min_value=min_date, max_value=max_date)
preset = st.selectbox("Quick range", ["Custom","Latest 7D","Latest 30D","Latest 90D","Year to date"], index=2)
if preset != "Custom":
    start_date = {
        "Latest 7D": max(min_date,max_date-pd.Timedelta(days=6)),
        "Latest 30D": max(min_date,max_date-pd.Timedelta(days=29)),
        "Latest 90D": max(min_date,max_date-pd.Timedelta(days=89)),
        "Year to date": max(min_date,pd.Timestamp(max_date.year,1,1).date()),
    }[preset]
    end_date = max_date
if start_date > end_date:
    st.error("Start date harus lebih kecil atau sama dengan End date.")
    st.stop()
scoped = scoped_all[(scoped_all["date"].dt.date >= start_date) & (scoped_all["date"].dt.date <= end_date)].copy()
if scoped.empty:
    st.warning("Tidak ada data pada periode yang dipilih.")
    st.stop()

# -------------------------------------------------------------------------
# 1. BMKG local weather forecast — operational forecast comes first.
# -------------------------------------------------------------------------
bmkg_df, bmkg_meta = load_bmkg_forecast()
st.markdown('<div class="section-title">📡 BMKG Local Weather Forecast</div>', unsafe_allow_html=True)
st.markdown('<div class="section-note">Operational 3-day BMKG forecast for five pilot monitoring locations. Forecast information is separate from historical rainfall, anomaly, SPI and climate-risk calculations.</div>', unsafe_allow_html=True)
if bmkg_df.empty:
    st.warning("BMKG forecast is temporarily unavailable. Existing historical climate analytics remain unchanged.")
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
        forecast_cols = ["location","local_datetime","temperature_c","humidity_pct","precipitation_mm","wind_speed_ms","wind_direction","cloud_cover_pct","weather_desc_en"]
        available = [c for c in forecast_cols if c in view.columns]
        forecast = view[available].sort_values(["location","local_datetime"]).copy()
        forecast = forecast.rename(columns={
            "local_datetime":"Local time","temperature_c":"Temp (°C)","humidity_pct":"RH (%)",
            "precipitation_mm":"Precipitation (mm)","wind_speed_ms":"Wind (m/s)",
            "wind_direction":"Wind direction","cloud_cover_pct":"Cloud (%)","weather_desc_en":"Weather"
        })
        st.dataframe(forecast, use_container_width=True, hide_index=True)
        st.caption("Source: BMKG Open Data · 3-day forecast · 3-hour interval · Forecast data is not historical climate data and is not included in Climate Risk.")
        q = bmkg_meta.get("quality")
        if q is not None and not q.empty:
            with st.expander("BMKG data quality & provenance"):
                st.dataframe(q, use_container_width=True, hide_index=True)
                st.write(f"Fetched (UTC): {bmkg_meta.get('fetched_at_utc','—')}")

latest_row = scoped.iloc[-1]
latest_date = latest_row["date"]
latest_value = float(latest_row["rainfall_mm"])
selected_30d = float(scoped.tail(30)["rainfall_mm"].sum())
source = str(latest_row.get("source","—"))
processed_at = str(latest_row.get("processing_time_utc","—"))
source_label = {"NASA/GPM_L3/IMERG_V07":"NASA GPM IMERG V07"}.get(source, source)

# -------------------------------------------------------------------------
# 2. Historical rainfall snapshot / climate KPIs
# -------------------------------------------------------------------------
st.markdown('<div class="section-title">Climate snapshot</div>', unsafe_allow_html=True)
k1,k2,k3,k4 = st.columns(4)
def kpi_html(label,value,note,variant):
    return f'<div class="kpi {variant}"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div><div class="kpi-note">{note}</div></div>'
with k1:
    st.markdown(kpi_html("Latest rainfall",f"{latest_value:.2f} mm",f"Observation · {latest_date.date()}","kpi-green"),unsafe_allow_html=True)
with k2:
    st.markdown(kpi_html("Rainfall · 30 days",f"{selected_30d:.1f} mm","Accumulated selected period","kpi-deep"),unsafe_allow_html=True)
with k3:
    anom_latest=None
    if not anomaly.empty:
        anomaly["date"]=pd.to_datetime(anomaly["date"],errors="coerce")
        an=anomaly[(anomaly["scope"]==scope)&(anomaly["date"]<=pd.Timestamp(end_date))].sort_values("date")
        if not an.empty and pd.notna(an.iloc[-1].get("anomaly_30d_pct")): anom_latest=float(an.iloc[-1]["anomaly_30d_pct"])
    st.markdown(kpi_html("30-day anomaly",f"{anom_latest:+.1f}%" if anom_latest is not None else "—","vs CHIRPS 1991–2020 normal","kpi-coral"),unsafe_allow_html=True)
with k4:
    risk_level="—"
    if not risk.empty:
        risk["date"]=pd.to_datetime(risk["date"],errors="coerce")
        selected_risk=risk[(risk["scope"]==scope)&(risk["date"]<=pd.Timestamp(end_date))].sort_values("date")
        if not selected_risk.empty: risk_level=str(selected_risk.iloc[-1].get("risk_level","—")).replace("_"," ").title()
    risk_dot={"Low":"🟢","Moderate":"🟡","High":"🟠","Very High":"🔴"}.get(risk_level,"⚪")
    st.markdown(kpi_html("Climate risk",f"{risk_dot} {risk_level}","Latest available assessment","kpi-yellow"),unsafe_allow_html=True)

st.markdown('<div class="section-title">Climate condition</div>',unsafe_allow_html=True)
cc1,cc2,cc3=st.columns(3)
selected_anom=pd.DataFrame()
if not anomaly.empty:
    selected_anom=anomaly[(anomaly["scope"]==scope)&(anomaly["date"]>=pd.Timestamp(start_date))&(anomaly["date"]<=pd.Timestamp(end_date))].sort_values("date")
with cc1:
    if selected_anom.empty: status,icon,desc="Insufficient data","⚪","No anomaly observation available for this period."
    else:
        a=selected_anom.iloc[-1]; status=str(a.get("climate_status","Insufficient Data")).replace("_"," ").title()
        icon={"Very Wet":"🟣","Wet":"🔵","Normal":"🟢","Dry":"🟡","Drought":"🔴","Insufficient Data":"⚪"}.get(status,"⚪")
        desc="Latest 30-day rainfall condition against the historical baseline."
    st.markdown(f'<div class="status-card status-drought"><div class="status-label">Rainfall condition</div><div class="status-value">{icon} {status}</div><div class="status-desc">{desc}</div></div>',unsafe_allow_html=True)
with cc2:
    if selected_risk.empty: rlevel,ricon,rdesc="No assessment","⚪","Climate risk output is not available for this period."
    else:
        rr=selected_risk.iloc[-1]; rlevel=str(rr.get("risk_level","—")).replace("_"," ").title()
        ricon={"Low":"🟢","Moderate":"🟡","High":"🟠","Very High":"🔴"}.get(rlevel,"⚪"); rdesc=f"Assessment date: {rr['date'].date()}."
    st.markdown(f'<div class="status-card status-risk"><div class="status-label">Climate risk</div><div class="status-value">{ricon} {rlevel}</div><div class="status-desc">{rdesc}</div></div>',unsafe_allow_html=True)
with cc3:
    obs_text="—"
    if not selected_anom.empty:
        obs=selected_anom.iloc[-1].get("obs_count_30d"); obs_text=f"{int(obs)}/30 days" if pd.notna(obs) else "—"
    st.markdown(f'<div class="status-card status-observation"><div class="status-label">30-day observations</div><div class="status-value">{obs_text}</div><div class="status-desc">Observation availability in the latest anomaly calculation.</div></div>',unsafe_allow_html=True)

st.markdown('<div class="section-title">📈 Rainfall trend</div>',unsafe_allow_html=True)
st.markdown('<div class="section-note">Daily rainfall for the selected monitoring area and period.</div>',unsafe_allow_html=True)
fig=px.line(scoped,x="date",y="rainfall_mm",markers=True,labels={"date":"Date","rainfall_mm":"Rainfall (mm/day)"})
fig.update_traces(line=dict(color="#156064",width=3),marker=dict(color="#00C49A",size=6))
fig.update_layout(height=360,margin=dict(l=10,r=10,t=20,b=10),paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",font=dict(color="#16383A"),hovermode="x unified")
fig.update_xaxes(showgrid=False); fig.update_yaxes(gridcolor="#E7EFEE",rangemode="tozero")
st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})

if not selected_anom.empty:
    st.markdown('<div class="section-title">📊 Rainfall anomaly</div>',unsafe_allow_html=True)
    st.markdown('<div class="section-note">30-day accumulated rainfall compared with the CHIRPS 1991–2020 climatological normal.</div>',unsafe_allow_html=True)
    fig2=px.line(selected_anom,x="date",y="anomaly_30d_pct",markers=True,labels={"date":"Date","anomaly_30d_pct":"30-day anomaly (%)"})
    fig2.update_traces(line=dict(color="#FB8F67",width=3),marker=dict(color="#FB8F67",size=6))
    fig2.add_hline(y=0,line_dash="dash",line_color="#8CA3A4")
    fig2.update_layout(height=310,margin=dict(l=10,r=10,t=20,b=10),paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",font=dict(color="#16383A"),hovermode="x unified")
    fig2.update_xaxes(showgrid=False); fig2.update_yaxes(gridcolor="#E7EFEE")
    st.plotly_chart(fig2,use_container_width=True,config={"displayModeBar":False})

st.markdown('<div class="section-title">💧 Drought / wetness indicators</div>',unsafe_allow_html=True)
if spi.empty:
    st.info("SPI-3/SPI-6 belum tersedia untuk periode ini.")
else:
    spi["date"]=pd.to_datetime(spi["date"],errors="coerce")
    current_spi=spi[(spi["scope"]==scope)&(spi["date"]<=pd.Timestamp(end_date))].sort_values("date")
    if current_spi.empty: st.info("SPI-3/SPI-6 belum tersedia untuk periode ini.")
    else:
        latest_spi_date=current_spi["date"].max(); latest_spi=current_spi[current_spi["date"]==latest_spi_date]
        s3=latest_spi[latest_spi["period"]=="SPI-3"]; s6=latest_spi[latest_spi["period"]=="SPI-6"]
        sp1,sp2,sp3,sp4=st.columns(4); vals=[]
        if not s3.empty and pd.notna(s3.iloc[0].get("spi")): vals.extend([f"{float(s3.iloc[0]['spi']):+.2f}",str(s3.iloc[0]["spi_status"]).replace("_"," ").title()])
        else: vals.extend(["—","Insufficient data"])
        if not s6.empty and pd.notna(s6.iloc[0].get("spi")): vals.extend([f"{float(s6.iloc[0]['spi']):+.2f}",str(s6.iloc[0]["spi_status"]).replace("_"," ").title()])
        else: vals.extend(["—","Insufficient data"])
        with sp1: st.markdown(f'<div class="spi-card spi-blue"><div class="spi-label">SPI-3</div><div class="spi-value">{vals[0]}</div></div>',unsafe_allow_html=True)
        with sp2: st.markdown(f'<div class="spi-card spi-yellow"><div class="spi-label">SPI-3 status</div><div class="spi-value">{vals[1]}</div></div>',unsafe_allow_html=True)
        with sp3: st.markdown(f'<div class="spi-card spi-blue"><div class="spi-label">SPI-6</div><div class="spi-value">{vals[2]}</div></div>',unsafe_allow_html=True)
        with sp4: st.markdown(f'<div class="spi-card spi-yellow"><div class="spi-label">SPI-6 status</div><div class="spi-value">{vals[3]}</div></div>',unsafe_allow_html=True)
        st.caption(f"Latest SPI calculation: {latest_spi_date.date()} · Values below zero indicate drier-than-normal conditions; values above zero indicate wetter-than-normal conditions.")

st.markdown('<div class="section-title">ℹ️ Data & quality</div>',unsafe_allow_html=True)
st.markdown(
    f"""
    <div class="info-strip">
      <b>Rainfall source:</b> {source_label} · <b>Monitoring area:</b> {scope.replace('_',' ').title()} ·
      <b>Selected period:</b> {start_date} → {end_date} · <b>Observations:</b> {len(scoped)} ·
      <b>Latest processing:</b> {processed_at}.
    </div>
    <div class="legend-row">
      <div class="legend-item"><span class="dot" style="background:#00C49A"></span> Normal / favourable</div>
      <div class="legend-item"><span class="dot" style="background:#F8E16C"></span> Dry / moderate concern</div>
      <div class="legend-item"><span class="dot" style="background:#FB8F67"></span> High concern</div>
      <div class="legend-item"><span class="dot" style="background:#156064"></span> Monitoring baseline</div>
    </div>
    """, unsafe_allow_html=True)
st.caption("Climate indicators are monitoring and screening products. Risk classifications should be interpreted together with rainfall history, SPI indicators and field information.")
