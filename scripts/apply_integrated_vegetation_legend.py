from pathlib import Path
import re

path = Path('pages/2_🌿_Vegetation_Monitoring.py')
text = path.read_text(encoding='utf-8')

start = text.find('    # Clickable information layers for NDVI and NDMI.')
end = text.find('    if bounds: m.fit_bounds(bounds, padding=(10, 10))', start)
if start < 0 or end < 0:
    raise SystemExit('Could not locate existing vegetation popup block')

new_block = '''    # Integrated vegetation map interaction: one hidden click layer serves the
    # NDVI, NDMI and Stress raster layers, so LayerControl contains only the
    # actual web-map data layers (no duplicate "click for value" entries).
    info_data = safe_spatial_features()
    if info_data.get("features"):
        popup = folium.GeoJsonPopup(
            fields=[
                "ndvi", "ndmi", "stress", "analysis_year", "analysis_start", "analysis_end",
                "observed_pct", "temporal_fallback_pct", "spatial_interpolation_pct",
            ],
            aliases=[
                "🌿 NDVI", "💧 NDMI", "⚠️ Vegetation Stress", "Analysis Year", "Analysis Start", "Analysis End",
                "Directly Observed (%)", "Temporal Fallback (%)", "Spatial Interpolation (%)",
            ],
            localize=True, labels=True, sticky=False, max_width=380,
            style="background-color: white;",
        )
        click_layer = folium.GeoJson(
            info_data,
            name="__vegetation_click_info__",
            control=False,
            show=True,
            style_function=lambda _: {
                "fillColor": "#ffffff", "fillOpacity": 0.001,
                "color": "#ffffff", "weight": 0, "opacity": 0,
            },
            highlight_function=lambda _: {
                "fillColor": "#ffffff", "fillOpacity": 0.10,
                "color": "#ffffff", "weight": 1, "opacity": 0.35,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=["ndvi", "ndmi", "stress"],
                aliases=["NDVI", "NDMI", "Stress"],
                localize=True, sticky=False, labels=True,
            ),
        )
        click_layer.add_child(popup).add_to(m)

        # Auto-integrated map legend. It follows the actual raster layer names
        # and is updated when a user toggles NDVI, NDMI or Stress in LayerControl.
        legend_html = """
        <div id="vegetation-legend" style="position: fixed; z-index: 9999; bottom: 18px; left: 18px; background: rgba(255,255,255,.96); border:1px solid #cbd5e1; border-radius:10px; padding:10px 12px; box-shadow:0 2px 8px rgba(15,23,42,.18); font-family:Arial,sans-serif; font-size:12px; min-width:180px;">
          <div style="font-weight:800; margin-bottom:7px;">Vegetation Map Legend</div>
          <div data-legend="ndvi" style="display:block;"><b>🌿 NDVI · YTD vigor</b><br><span style="color:#b91c1c">■</span> &lt; 0.30 &nbsp; <span style="color:#f59e0b">■</span> 0.30–0.49 &nbsp; <span style="color:#84cc16">■</span> 0.50–0.69 &nbsp; <span style="color:#15803d">■</span> ≥ 0.70</div>
          <div data-legend="ndmi" style="display:none; margin-top:7px;"><b>💧 NDMI · YTD moisture</b><br><span style="color:#b91c1c">■</span> &lt; 0 &nbsp; <span style="color:#f59e0b">■</span> 0–0.19 &nbsp; <span style="color:#84cc16">■</span> 0.20–0.39 &nbsp; <span style="color:#15803d">■</span> ≥ 0.40</div>
          <div data-legend="stress" style="display:none; margin-top:7px;"><b>⚠️ Vegetation Stress</b><br><span style="color:#16a34a">■</span> Stable &nbsp; <span style="color:#2563eb">■</span> Low &nbsp; <span style="color:#f59e0b">■</span> Moderate &nbsp; <span style="color:#b91c1c">■</span> High</div>
          <div style="margin-top:7px;color:#64748b;font-size:10px;">Click the mapped Project Area to open NDVI + NDMI + Stress details.</div>
        </div>
        """
        folium.Element(legend_html).add_to(m)
        map_name = m.get_name()
        legend_js = f"""
        <script>
        (function() {{
          var map = {map_name};
          function setLegend(name, visible) {{
            var box = document.getElementById('vegetation-legend');
            if (!box) return;
            var key = name === '🌿 NDVI · YTD vigor' ? 'ndvi' : (name === '💧 NDMI · YTD moisture' ? 'ndmi' : (name === '⚠️ Vegetation stress · YTD' ? 'stress' : null));
            if (!key) return;
            var el = box.querySelector('[data-legend="' + key + '"]');
            if (el) el.style.display = visible ? 'block' : 'none';
          }}
          map.on('overlayadd', function(e) {{ setLegend(e.name, true); }});
          map.on('overlayremove', function(e) {{ setLegend(e.name, false); }});
        }})();
        </script>
        """
        folium.Element(legend_js).add_to(m)

'''

text = text[:start] + new_block + text[end:]
path.write_text(text, encoding='utf-8')
print('Integrated vegetation legend/popup patch applied.')
