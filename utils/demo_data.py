import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def load_demo_data():
    dates = pd.date_range("2026-08-06", periods=7, freq="D")
    rainfall = pd.DataFrame({"date": dates, "rainfall_mm": [58, 132, 98, 21, 83, 31, 84]})
    rainfall["cum_30d"] = rainfall["rainfall_mm"].cumsum()
    fire = pd.DataFrame({"date": dates, "High": [6, 6, 7, 8, 5, 5, 7], "Medium": [8, 10, 7, 11, 8, 6, 8], "Low": [9, 14, 11, 11, 8, 20, 10]})
    ndvi = pd.DataFrame({"date": dates, "ndvi": [0.62, 0.64, 0.63, 0.67, 0.69, 0.71, 0.71]})

    rainfall_chart = go.Figure()
    rainfall_chart.add_bar(x=rainfall["date"], y=rainfall["rainfall_mm"], name="Daily rainfall")
    rainfall_chart.add_scatter(x=rainfall["date"], y=rainfall["cum_30d"], name="Cumulative", yaxis="y2")
    rainfall_chart.update_layout(title="Rainfall Trend", height=285, margin=dict(l=20, r=20, t=45, b=20), legend=dict(orientation="h", y=1.02), yaxis2=dict(overlaying="y", side="right"))

    fire_chart = px.bar(fire, x="date", y=["High", "Medium", "Low"], title="Fire Hotspot Trend")
    fire_chart.update_layout(barmode="stack", height=285, margin=dict(l=20, r=20, t=45, b=20))
    ndvi_chart = px.line(ndvi, x="date", y="ndvi", markers=True, title="Vegetation (NDVI) Trend")
    ndvi_chart.update_yaxes(range=[0.4, 0.85])
    ndvi_chart.update_layout(height=285, margin=dict(l=20, r=20, t=45, b=20))

    hotspots = pd.DataFrame({"lat": [-2.46, -2.49, -2.51, -2.54, -2.57, -2.60, -2.47, -2.55], "lon": [112.55, 112.68, 112.76, 112.62, 112.80, 112.71, 112.88, 112.91], "confidence": [91, 84, 72, 88, 95, 69, 83, 77]})
    monitoring_points = pd.DataFrame({"id": ["MP-001", "MP-002", "MP-003", "MP-004", "MP-005"], "lat": [-2.48, -2.52, -2.56, -2.59, -2.50], "lon": [112.60, 112.72, 112.83, 112.66, 112.90]})
    risk_inputs = {"rainfall_anomaly": 0.62, "temperature_anomaly": 0.48, "fire_activity": 0.75, "vegetation_stress": 0.56, "hydrological_stress": 0.42}
    alerts = pd.DataFrame([
        {"Priority": "HIGH", "Type": "🔥 Fire risk", "Location": "Demo buffer zone", "Date": "12 Aug 2026 14:32"},
        {"Priority": "MEDIUM", "Type": "🌧 Rainfall anomaly", "Location": "Project area", "Date": "12 Aug 2026 09:15"},
        {"Priority": "MEDIUM", "Type": "🌿 Vegetation decline", "Location": "Demo area", "Date": "11 Aug 2026 16:40"},
        {"Priority": "LOW", "Type": "💧 Hydrological stress", "Location": "Demo monitoring point", "Date": "11 Aug 2026 10:20"},
        {"Priority": "INFO", "Type": "✅ Data update", "Location": "All demo datasets", "Date": "12 Aug 2026 20:00"},
    ])
    return {"rainfall": rainfall, "fire": fire, "ndvi": ndvi, "rainfall_chart": rainfall_chart, "fire_chart": fire_chart, "ndvi_chart": ndvi_chart, "hotspots": hotspots, "monitoring_points": monitoring_points, "risk_inputs": risk_inputs, "alerts": alerts}
