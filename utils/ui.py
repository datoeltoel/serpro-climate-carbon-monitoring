import streamlit as st


def setup_page():
    st.set_page_config(
        page_title="SERPRO Climate & Carbon Monitoring",
        page_icon="🌿",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
        :root { --green:#0B5D3B; --dark:#062A20; --mint:#EAF7F0; --ink:#13251F; --muted:#68776F; --line:#DCE6E1; }
        .stApp { background:#F6F8F7; color:var(--ink); }
        .block-container { padding-top:1.25rem; padding-bottom:1.5rem; max-width:1700px; }
        [data-testid="stSidebar"] { background:linear-gradient(180deg,#05251D 0%,#073126 100%); }
        [data-testid="stSidebar"] * { color:#F3F8F5; }
        [data-testid="stSidebar"] .stButton button { background:#1A6A45; border:none; color:white; }
        .app-header { display:flex; align-items:center; justify-content:space-between; gap:18px; margin-bottom:10px; }
        .brand { font-size:1.65rem; line-height:1.15; font-weight:800; color:#073A2B; margin:0; }
        .prototype-badge { display:inline-block; margin-left:10px; padding:4px 9px; border-radius:999px; background:#EEF8F2; color:#0B5D3B; border:1px solid #BFD8CC; font-size:.58rem; font-weight:800; letter-spacing:.09em; vertical-align:middle; }
        .subtitle { color:#718078; font-size:.88rem; margin-top:4px; }
        .top-status { display:flex; align-items:center; gap:10px; color:#384A43; font-size:.8rem; }
        .status-pill { background:#E7F6EC; color:#167447; padding:6px 10px; border-radius:999px; font-weight:700; }
        .kpi-card { background:#FFFFFF; border:1px solid var(--line); border-radius:16px; padding:14px 15px 11px; min-height:146px; box-shadow:0 3px 12px rgba(17,40,30,.05); }
        .kpi-top { display:flex; align-items:center; gap:9px; color:#4E625A; font-size:.72rem; text-transform:uppercase; letter-spacing:.05em; font-weight:700; }
        .kpi-icon { width:40px; height:40px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:1.15rem; background:#EEF5F2; }
        .kpi-value { font-size:1.65rem; font-weight:800; margin-top:8px; color:#13251F; }
        .kpi-sub { font-size:.72rem; color:#6C7A74; margin-top:1px; }
        .kpi-delta { font-size:.74rem; margin-top:8px; font-weight:700; }
        .delta-up { color:#12814F; } .delta-warn { color:#D97706; } .delta-bad { color:#C62828; }
        .panel { background:#FFFFFF; border:1px solid var(--line); border-radius:16px; padding:14px; box-shadow:0 3px 12px rgba(17,40,30,.05); }
        .panel-title { font-size:.95rem; font-weight:800; color:#13251F; margin-bottom:5px; }
        .panel-sub { font-size:.72rem; color:#75827D; margin-bottom:8px; }
        .map-panel { background:#FFFFFF; border:1px solid var(--line); border-radius:16px; overflow:hidden; box-shadow:0 3px 12px rgba(17,40,30,.05); }
        .map-title-badge { position:relative; z-index:10; margin:10px; padding:6px 9px; background:rgba(8,48,36,.84); color:white; border-radius:8px; display:inline-block; font-size:.72rem; font-weight:800; letter-spacing:.04em; }
        .risk-panel { background:linear-gradient(180deg,#F8FCFA 0%,#FFFFFF 100%); border:1px solid var(--line); border-radius:16px; padding:18px; min-height:100%; box-shadow:0 3px 12px rgba(17,40,30,.05); }
        .risk-score { font-size:3rem; font-weight:900; color:#12382A; line-height:1; margin-top:6px; }
        .risk-label { font-size:1rem; font-weight:800; color:#C62828; margin-top:4px; }
        .risk-track { height:12px; border-radius:99px; background:linear-gradient(90deg,#31A56B 0%,#F2C14E 48%,#F59E0B 70%,#E63B2E 100%); position:relative; margin:18px 0 12px; }
        .risk-marker { position:absolute; top:-6px; width:4px; height:24px; background:#7A1620; border-radius:4px; }
        .risk-row { display:flex; justify-content:space-between; font-size:.76rem; margin:8px 0; color:#5B6A63; }
        .risk-row strong { color:#1C2B25; }
        .trend-card { background:#FFFFFF; border:1px solid var(--line); border-radius:16px; padding:14px; box-shadow:0 3px 12px rgba(17,40,30,.05); }
        .trend-stat { display:grid; grid-template-columns:repeat(3,1fr); gap:1px; background:#E8EFEB; border-radius:10px; overflow:hidden; margin-top:8px; }
        .trend-stat > div { background:#FBFDFC; padding:8px 10px; } .trend-stat-label { font-size:.66rem; color:#7A8781; } .trend-stat-value { font-size:.9rem; font-weight:800; margin-top:2px; color:#173D2D; }
        .alert-list { background:#FFFFFF; border:1px solid var(--line); border-radius:16px; padding:14px; box-shadow:0 3px 12px rgba(17,40,30,.05); }
        .alert-item { display:flex; justify-content:space-between; gap:12px; align-items:center; padding:11px 0; border-bottom:1px solid #EEF2F0; }
        .alert-item:last-child { border-bottom:none; }
        .alert-title { font-size:.8rem; font-weight:800; color:#1F3029; } .alert-meta { font-size:.7rem; color:#738079; margin-top:2px; }
        .alert-badge { font-size:.64rem; font-weight:800; padding:5px 8px; border-radius:999px; }
        .badge-high { background:#FDEBEC; color:#C62828; } .badge-moderate { background:#FFF5D9; color:#B26A00; } .badge-low { background:#EAF3FF; color:#245B9B; }
        .side-project-card { background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.10); border-radius:14px; padding:14px; margin-top:14px; }
        .side-project-title { font-weight:800; font-size:.85rem; margin-bottom:9px; } .side-project-row { margin:7px 0; } .side-project-label { font-size:.65rem; opacity:.7; text-transform:uppercase; letter-spacing:.06em; } .side-project-value { font-size:.8rem; font-weight:700; margin-top:1px; }
        .footer-bar { background:#062A20; color:white; border-radius:14px; padding:12px 16px; font-size:.72rem; margin-top:10px; }
        .footer-grid { display:grid; grid-template-columns:1.4fr 1fr 1fr 1fr; gap:14px; align-items:center; } .footer-item span { opacity:.65; display:block; margin-bottom:3px; font-size:.63rem; text-transform:uppercase; letter-spacing:.06em; }
        div[data-testid="stMetric"] { background:#FFFFFF; border:1px solid var(--line); border-radius:14px; padding:10px; }
        @media(max-width:900px){ .app-header{display:block}.top-status{margin-top:8px}.footer-grid{grid-template-columns:1fr 1fr;} }
        </style>
        """,
        unsafe_allow_html=True,
    )
