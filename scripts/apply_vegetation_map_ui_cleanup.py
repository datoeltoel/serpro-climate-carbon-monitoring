from pathlib import Path
import re

path = Path('pages/2_🌿_Vegetation_Monitoring.py')
text = path.read_text(encoding='utf-8')

# Remove the small duplicate hover tooltip. The click popup remains the single
# interaction card for NDVI/NDMI/stress values.
text, n = re.subn(
    r'\n\s*tooltip=folium\.GeoJsonTooltip\(\n\s*fields=\["ndvi", "ndmi", "stress"\],\n\s*aliases=\["🌿 NDVI", "💧 NDMI", "⚠️ Stress"\],\n\s*localize=True,\n\s*sticky=False,\n\s*labels=True,\n\s*\),',
    '',
    text,
    count=1,
)
if n != 1:
    raise SystemExit(f'Expected one duplicate vegetation tooltip block, found {n}')

# Move the persistent symbology legend into the map, below the Layer Control
# area, so it remains visible without covering the bottom map controls.
old = 'position:fixed; z-index:9998; bottom:18px; left:18px;'
new = 'position:absolute; z-index:9998; top:170px; right:12px;'
if old not in text:
    raise SystemExit('Legend position anchor not found')
text = text.replace(old, new, 1)

# Make the legend slightly more compact for the map viewport.
text = text.replace('min-width:250px; max-width:310px;', 'min-width:230px; max-width:285px;', 1)

path.write_text(text, encoding='utf-8')
print('Vegetation map UI cleanup applied.')
