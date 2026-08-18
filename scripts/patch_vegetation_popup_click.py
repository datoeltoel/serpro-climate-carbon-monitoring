from pathlib import Path

path = Path('pages/2_🌿_Vegetation_Monitoring.py')
text = path.read_text(encoding='utf-8')

start_marker = '    # Clickable information layer for the rendered vegetation web map.'
end_marker = '    if bounds: m.fit_bounds(bounds, padding=(10, 10))\n'
if start_marker in text:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    text = text[:start] + text[end:]

anchor = '    if bounds: m.fit_bounds(bounds, padding=(10, 10))\n'
if anchor not in text:
    raise SystemExit('Map fit-bounds anchor not found')

block = '''    # Transparent click-capture layer. It is excluded from LayerControl so\n    # NDVI/NDMI/Stress remain the only thematic layers shown to the user.\n    interaction_data = safe_spatial_features()\n    if interaction_data.get("features"):\n        popup_fields = [\n            "ndvi", "ndmi", "stress", "analysis_year", "analysis_start", "analysis_end",\n            "observed_pct", "temporal_fallback_pct", "spatial_interpolation_pct",\n        ]\n        popup_aliases = [\n            "🌿 NDVI", "💧 NDMI", "⚠️ Vegetation Stress", "Analysis Year", "Analysis Start", "Analysis End",\n            "Directly Observed (%)", "Temporal Fallback (%)", "Spatial Interpolation (%)",\n        ]\n        popup = folium.GeoJsonPopup(\n            fields=popup_fields, aliases=popup_aliases, localize=True, labels=True,\n            sticky=False, max_width=380,\n        )\n        folium.GeoJson(\n            interaction_data,\n            name="Vegetation click information",\n            control=False, show=True,\n            style_function=lambda _: {\n                "fillColor": "#ffffff", "fillOpacity": 0.001,\n                "color": "#ffffff", "weight": 0, "opacity": 0,\n            },\n            highlight_function=lambda _: {\n                "fillColor": "#ffffff", "fillOpacity": 0.08,\n                "color": "#ffffff", "weight": 1, "opacity": 0.25,\n            },\n            popup=popup,\n        ).add_to(m)\n\n'''
text = text.replace(anchor, block + anchor, 1)
path.write_text(text, encoding='utf-8')
print('Applied transparent click-capture popup layer.')
