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

    # Keep a visible deployment marker without changing analytical behavior.
    old = '<span class="vm-meta">10 m analysis · 100 m web display · 250 m spatial overview</span>'
    new = '<span class="vm-meta">10 m analysis · 100 m web display · 250 m spatial overview · dashboard v2</span>'
    if old in text and new not in text:
        text = text.replace(old, new, 1)

    PAGE.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()

# UI redeploy marker: analytical vegetation pipeline remains untouched.
