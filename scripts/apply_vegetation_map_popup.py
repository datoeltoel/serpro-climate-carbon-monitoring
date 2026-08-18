from pathlib import Path

path = Path('pages/2_🌿_Vegetation_Monitoring.py')
text = path.read_text(encoding='utf-8')

old = '''        props = dict(feature.get("properties") or {})\n        props.setdefault("ndvi", None); props.setdefault("ndmi", None); props.setdefault("stress", "STABLE")\n        clean.append({"type":"Feature", "geometry":geom, "properties":props})'''
new = '''        props = dict(feature.get("properties") or {})\n        props.setdefault("ndvi", None); props.setdefault("ndmi", None); props.setdefault("stress", "STABLE")\n        props.setdefault("analysis_year", None); props.setdefault("analysis_start", None); props.setdefault("analysis_end", None)\n        props.setdefault("observed_pct", None); props.setdefault("temporal_fallback_pct", None); props.setdefault("spatial_interpolation_pct", None)\n        clean.append({"type":"Feature", "geometry":geom, "properties":props})'''
if old not in text:
    raise SystemExit('safe_spatial_features anchor not found')
text = text.replace(old, new, 1)

anchor = '''    if bounds: m.fit_bounds(bounds, padding=(10, 10))\n    folium.LayerControl(collapsed=False).add_to(m)'''
insert = '''    # Clickable information layer for the rendered vegetation web map.\n    # The raster remains the 100 m web display derived from the native 10 m analysis.\n    # Popup attributes intentionally come from the 250 m Spatial Overview summary.\n    info_data = safe_spatial_features()\n    if info_data.get("features"):\n        popup_fields = [\n            "ndvi", "ndmi", "stress", "analysis_year", "analysis_start", "analysis_end",\n            "observed_pct", "temporal_fallback_pct", "spatial_interpolation_pct",\n        ]\n        popup_aliases = [\n            "NDVI", "NDMI", "Vegetation Stress", "Analysis Year", "Analysis Start", "Analysis End",\n            "Directly Observed (%)", "Temporal Fallback (%)", "Spatial Interpolation (%)",\n        ]\n        popup = folium.GeoJsonPopup(\n            fields=popup_fields, aliases=popup_aliases, localize=True, labels=True, sticky=False,\n            max_width=360,\n            style="background-color: white;",\n        )\n        folium.GeoJson(\n            info_data,\n            name="📍 Vegetation cell info · click",\n            style_function=lambda _: {\n                "fillColor": "#ffffff", "fillOpacity": 0.001, "color": "#ffffff",\n                "weight": 0, "opacity": 0,\n            },\n            highlight_function=lambda _: {"fillColor": "#ffffff", "fillOpacity": 0.10, "weight": 1, "color": "#ffffff", "opacity": 0.35},\n            tooltip=folium.GeoJsonTooltip(\n                fields=["ndvi", "ndmi", "stress"],\n                aliases=["NDVI", "NDMI", "Stress"],\n                localize=True, sticky=False,\n                labels=True,\n            ),\n            show=True,\n        ).add_child(popup).add_to(m)\n\n    if bounds: m.fit_bounds(bounds, padding=(10, 10))\n    folium.LayerControl(collapsed=False).add_to(m)'''
if anchor not in text:
    raise SystemExit('map anchor not found')
text = text.replace(anchor, insert, 1)
path.write_text(text, encoding='utf-8')
print('Vegetation map popup patch applied.')
