from pathlib import Path

PAGE = Path("pages/2_🌿_Vegetation_Monitoring.py")


def main():
    text = PAGE.read_text(encoding="utf-8")

    # UI-only patch. The dashboard page uses an f-string for its main CSS,
    # therefore literal CSS braces must be doubled before insertion.
    css = r'''

/* Vegetation dashboard readability guard: UI only. */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"],
[data-testid="stVerticalBlock"],
[data-testid="stMarkdownContainer"] {{
  color: var(--vm-ink) !important;
}}
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] span,
[data-testid="stMarkdownContainer"] label,
[data-testid="stMarkdownContainer"] div {{
  color: inherit;
}}
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] span {{
  color: var(--vm-ink) !important;
  font-weight: 700 !important;
}}
[data-baseweb="select"] *,
[data-baseweb="input"] * {{
  color: var(--vm-ink) !important;
}}
[data-testid="stExpander"] {{
  background: #ffffff !important;
  border: 1px solid var(--vm-border) !important;
  border-radius: 14px !important;
}}
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary p,
[data-testid="stExpander"] summary span {{
  color: var(--vm-ink) !important;
  font-weight: 850 !important;
}}
[data-testid="stDataFrame"] {{
  border: 1px solid var(--vm-border) !important;
  border-radius: 12px !important;
  overflow: hidden !important;
  background: #ffffff !important;
}}
[data-testid="stDataFrame"] iframe {{
  background: #ffffff !important;
}}
.stPlotlyChart {{
  border: 1px solid var(--vm-border);
  border-radius: 14px;
  overflow: hidden;
  background: #ffffff;
}}
.vm-stress-card {{
  background:linear-gradient(135deg,#ffffff 0%,#f7faf9 100%);
  border:1px solid var(--vm-border); border-radius:16px; padding:15px;
}}
.vm-stress-label {{ color:var(--vm-muted); font-size:.68rem; font-weight:900; text-transform:uppercase; letter-spacing:.06em; }}
.vm-stress-value {{ color:var(--vm-ink); font-size:1.55rem; font-weight:950; margin-top:5px; }}
.vm-stress-note {{ color:var(--vm-muted); font-size:.73rem; line-height:1.45; margin-top:6px; }}
.vm-download {{ background:#f7faf9; border:1px solid var(--vm-border); border-radius:14px; padding:12px 14px; margin-bottom:10px; }}
'''

    marker = "/* Vegetation dashboard readability guard: UI only. */"
    style_end = text.find("</style>")
    if style_end < 0:
        raise RuntimeError("Vegetation dashboard style block not found")

    if marker in text:
        start = text.index(marker)
        text = text[:start] + css.strip("\n") + "\n\n" + text[style_end:]
    else:
        text = text[:style_end] + css + text[style_end:]

    # Replace the interpretation area with a single, unambiguous stress-status card.
    start_marker = "with interpretation_col:\n"
    end_marker = "\nst.markdown('<div class=\"vm-section-title\">📋 Monitoring details</div>'"
    start = text.find(start_marker)
    end = text.find(end_marker, start) if start >= 0 else -1
    if start < 0 or end < 0:
        raise RuntimeError("Current interpretation block not found")

    stress_block = '''with interpretation_col:\n    st.markdown('<div class="vm-card"><div class="vm-card-title">🚨 Vegetation Stress Status</div><div class="vm-card-caption">A simple screening status based on recent NDVI and NDMI change.</div>', unsafe_allow_html=True)\n    stress_note = {\n        "HIGH": "Both NDVI and NDMI declined by at least 10% in the last 30 days. Field verification is recommended.",\n        "MODERATE": "At least one indicator declined by at least 10% in the last 30 days. Review the spatial pattern.",\n        "LOW": "A recent decline is present, but the moderate threshold has not been reached.",\n        "STABLE": "No negative NDVI/NDMI trend signal was detected under the current screening rules.",\n    }[stress_level]\n    stress_class = {"HIGH": "vm-high", "MODERATE": "vm-medium", "LOW": "vm-low", "STABLE": "vm-low"}[stress_level]\n    st.markdown(f'<div class="vm-stress-card"><div class="vm-stress-label">Screening status</div><div class="vm-stress-value">{stress_level}</div><div class="vm-badge {stress_class}">{stress_level.title()} stress</div><div class="vm-stress-note">{stress_note}</div></div></div>', unsafe_allow_html=True)\n'''
    text = text[:start] + stress_block + text[end:]

    # Replace observation expander with a visible observation section and downloads.
    obs_start_marker = 'with st.expander("🗃️ Observation data", expanded=False):\n'
    obs_end_marker = '\nif spatial.get("features"):\n'
    obs_start = text.find(obs_start_marker)
    obs_end = text.find(obs_end_marker, obs_start) if obs_start >= 0 else -1
    if obs_start < 0 or obs_end < 0:
        raise RuntimeError("Observation data block not found")

    obs_block = '''st.markdown('<div class="vm-section-title">📋 Observation Data</div>', unsafe_allow_html=True)\nst.markdown('<div class="vm-section-caption">Latest available NDVI and NDMI observations for the selected monitoring area and period.</div>', unsafe_allow_html=True)\n\n# Prepare export tables without changing the source data or analytical pipeline.\nndvi_export = ndvi_p.sort_values("date", ascending=False).copy()\nndmi_export = ndmi_p.sort_values("date", ascending=False).copy()\ncombined_export = pd.concat(\n    [\n        ndvi_export.assign(indicator="NDVI", value=ndvi_export.get("ndvi")),\n        ndmi_export.assign(indicator="NDMI", value=ndmi_export.get("ndmi")),\n    ],\n    ignore_index=True,\n)\n\nexport_csv = combined_export.to_csv(index=False).encode("utf-8-sig")\nfrom io import BytesIO\nexcel_buffer = BytesIO()\nwith pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:\n    ndvi_export.to_excel(writer, sheet_name="NDVI", index=False)\n    ndmi_export.to_excel(writer, sheet_name="NDMI", index=False)\n    combined_export.to_excel(writer, sheet_name="Combined", index=False)\nexcel_buffer.seek(0)\n\nbutton_col, csv_col, excel_col = st.columns([2.2, 1, 1], gap="small")\nwith button_col:\n    st.markdown('<div class="vm-download"><strong>Download observation data</strong><br><span class="vm-note">Excel contains NDVI, NDMI and Combined sheets.</span></div>', unsafe_allow_html=True)\nwith csv_col:\n    st.download_button("⬇️ CSV", data=export_csv, file_name="SERPRO_Vegetation_Observations.csv", mime="text/csv", use_container_width=True)\nwith excel_col:\n    st.download_button("⬇️ Excel", data=excel_buffer.getvalue(), file_name="SERPRO_Vegetation_Observations.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)\n\nobs1, obs2 = st.tabs(["NDVI observations", "NDMI observations"])\nwith obs1:\n    st.dataframe(ndvi_export, use_container_width=True, hide_index=True)\nwith obs2:\n    st.dataframe(ndmi_export, use_container_width=True, hide_index=True)\n'''
    text = text[:obs_start] + obs_block + text[obs_end:]

    # Keep the dashboard marker while making clear that the map/analysis pipeline is unchanged.
    old = '<span class="vm-meta">10 m analysis · 100 m web display · 250 m spatial overview</span>'
    new = '<span class="vm-meta">10 m analysis · 100 m web display · 250 m spatial overview · stress status · data download</span>'
    if old in text:
        text = text.replace(old, new, 1)
    elif 'dashboard v2</span>' in text:
        text = text.replace('dashboard v2</span>', 'stress status · data download</span>', 1)

    PAGE.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()

# UI-only patch marker: analytical vegetation pipeline remains untouched.
'''
