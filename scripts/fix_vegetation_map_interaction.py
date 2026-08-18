from pathlib import Path

# Isolated dashboard UI patch: does not touch the Earth Engine data pipeline.
path = Path("pages/2_🌿_Vegetation_Monitoring.py")
text = path.read_text(encoding="utf-8")

start = text.find("    # Integrated vegetation map interaction:")
anchor = "    if bounds: m.fit_bounds(bounds, padding=(10, 10))\n"
end = text.find(anchor, start)
if start < 0 or end < 0:
    raise SystemExit("Vegetation interaction block markers not found")

block = '''    # Robust click interaction for the rendered vegetation raster.
    # ImageOverlay is intentionally non-interactive; this transparent vector
    # pane sits above it and uses the same spatial overview cells for popups.
    info_data = safe_spatial_features()
    if info_data.get("features"):
        folium.map.CustomPane("vegetationClickPane", z_index=650).add_to(m)
        popup = folium.GeoJsonPopup(
            fields=[
                "ndvi", "ndmi", "stress", "analysis_year", "analysis_start", "analysis_end",
                "observed_pct", "temporal_fallback_pct", "spatial_interpolation_pct",
            ],
            aliases=[
                "🌿 NDVI", "💧 NDMI", "⚠️ Vegetation Stress", "Analysis Year", "Analysis Start", "Analysis End",
                "Directly Observed (%)", "Temporal Fallback (%)", "Spatial Interpolation (%)",
            ],
            localize=True,
            labels=True,
            sticky=False,
            max_width=400,
        )
        click_layer = folium.GeoJson(
            info_data,
            name="__vegetation_click_info__",
            control=False,
            show=True,
            pane="vegetationClickPane",
            style_function=lambda _: {
                "fillColor": "#ffffff",
                "fillOpacity": 0.01,
                "color": "#ffffff",
                "weight": 0,
                "opacity": 0,
            },
            highlight_function=lambda _: {
                "fillColor": "#ffffff",
                "fillOpacity": 0.10,
                "color": "#ffffff",
                "weight": 1,
                "opacity": 0.35,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=["ndvi", "ndmi", "stress"],
                aliases=["🌿 NDVI", "💧 NDMI", "⚠️ Stress"],
                localize=True,
                sticky=False,
                labels=True,
            ),
            popup=popup,
        )
        click_layer.add_to(m)

        # Persistent map symbology legend. The values match the raster styling.
        legend_html = """
        <div style="position:fixed; z-index:9998; bottom:18px; left:18px; background:rgba(255,255,255,.97); border:1px solid #cbd5e1; border-radius:10px; padding:11px 13px; box-shadow:0 2px 9px rgba(15,23,42,.18); font-family:Arial,sans-serif; font-size:11px; line-height:1.55; min-width:250px; max-width:310px;">
          <div style="font-weight:800; font-size:12px; margin-bottom:7px;">🎨 Vegetation Map Symbology</div>
          <div style="font-weight:800; margin-top:3px;">🌿 NDVI · YTD vigor</div>
          <div><span style="color:#b91c1c">■</span> &lt; 0.30 Very low &nbsp; <span style="color:#f59e0b">■</span> 0.30–0.49 Low</div>
          <div><span style="color:#84cc16">■</span> 0.50–0.69 Moderate &nbsp; <span style="color:#15803d">■</span> ≥ 0.70 Good</div>
          <div style="font-weight:800; margin-top:7px;">💧 NDMI · YTD moisture</div>
          <div><span style="color:#b91c1c">■</span> &lt; 0 Low moisture &nbsp; <span style="color:#f59e0b">■</span> 0–0.19 Drying</div>
          <div><span style="color:#84cc16">■</span> 0.20–0.39 Moderate &nbsp; <span style="color:#15803d">■</span> ≥ 0.40 Moist</div>
          <div style="font-weight:800; margin-top:7px;">⚠️ Vegetation Stress</div>
          <div><span style="color:#16a34a">■</span> Stable &nbsp; <span style="color:#2563eb">■</span> Low &nbsp; <span style="color:#f59e0b">■</span> Moderate &nbsp; <span style="color:#b91c1c">■</span> High</div>
          <div style="margin-top:7px; color:#64748b; font-size:10px;">Klik area Project Area untuk membuka detail NDVI, NDMI, stress dan kualitas observasi.</div>
        </div>
        """
        folium.Element(legend_html).add_to(m)

'''

text = text[:start] + block + text[end:]
path.write_text(text, encoding="utf-8")
print("Applied robust vegetation popup and symbology legend.")
