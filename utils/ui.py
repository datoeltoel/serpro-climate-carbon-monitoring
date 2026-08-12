import streamlit as st


def setup_page():
    st.set_page_config(page_title="SERPRO Climate & Carbon Monitoring", page_icon="🌿", layout="wide", initial_sidebar_state="expanded")
    st.markdown("""
    <style>
    .block-container {padding-top: 2.2rem; padding-bottom: 2rem; max-width: 1500px;}
    [data-testid="stSidebar"] {background: #09231A;}
    [data-testid="stSidebar"] * {color: #F4F7F5;}

    /* Brand / header: prevent clipping at the top of the viewport */
    .brand {
        display:block;
        width:100%;
        overflow:visible !important;
        position:relative;
        z-index:2;
        font-size:1.55rem;
        line-height:1.35;
        font-weight:700;
        color:#0B5D3B;
        margin:0 0 2px 0;
        padding:0;
    }
    .subtitle {
        display:block;
        width:100%;
        overflow:visible !important;
        font-size:.92rem;
        line-height:1.45;
        color:#66756E;
        margin:0 0 1rem 0;
        padding:0;
    }
    .status {font-size:0.82rem; line-height:1.4; color:#4E665B; text-align:right; margin-bottom:8px;}

    .metric-card {background:#FFFFFF; border:1px solid #E4EAE7; border-radius:14px; padding:16px 18px; min-height:105px; box-shadow:0 1px 3px rgba(0,0,0,.04);}
    .metric-label {font-size:.78rem; color:#66756E; text-transform:uppercase; letter-spacing:.04em;}
    .metric-value {font-size:1.7rem; font-weight:700; color:#12382A; margin-top:5px;}
    .metric-delta {font-size:.78rem; color:#4B7A64; margin-top:3px;}
    .section-title {font-size:1.1rem; font-weight:700; color:#173D2D; margin:12px 0 6px;}
    .landscape-summary {background:#FFFFFF; border:1px solid #E1E8E4; border-radius:16px; padding:18px 20px; box-shadow:0 1px 3px rgba(0,0,0,.035); margin-bottom:12px;}
    .landscape-intro {color:#53665D; font-size:.9rem; line-height:1.5; margin-bottom:14px;}
    .landscape-grid {display:grid; grid-template-columns:1fr 120px 1fr; align-items:center; gap:14px;}
    .landscape-card {border-radius:13px; padding:15px 17px; min-height:118px; border:1px solid #E2E8E5;}
    .area-card {background:#F5FAF7; border-left:5px solid #146B43;}
    .zone-card {background:#F8F6FC; border-left:5px solid #6A4C93;}
    .landscape-icon {font-size:1.1rem; margin-bottom:4px;}
    .landscape-label {font-size:.82rem; font-weight:700; color:#40574C; text-transform:uppercase; letter-spacing:.03em;}
    .landscape-value {font-size:1.75rem; font-weight:800; color:#173D2D; margin-top:4px;}
    .landscape-meta {font-size:.74rem; color:#728079; margin-top:3px; line-height:1.35;}
    .landscape-connector {text-align:center; color:#6A4C93; font-size:2rem; font-weight:700; line-height:1;}
    .landscape-connector span {display:block; color:#68776F; font-size:.62rem; letter-spacing:.07em; line-height:1.25; margin-top:5px;}
    .landscape-note {font-size:.72rem; color:#7A8781; margin-top:12px; padding-top:10px; border-top:1px solid #EDF1EF;}
    .relationship-card {background:#12382A; color:white; border-radius:16px; padding:18px 20px; min-height:430px; box-shadow:0 1px 3px rgba(0,0,0,.08);}
    .relationship-title {font-size:.78rem; font-weight:800; letter-spacing:.08em; opacity:.86;}
    .relationship-hero {font-size:3rem; font-weight:800; line-height:1; margin:12px 0 3px;}
    .relationship-sub {font-size:.78rem; font-weight:700; letter-spacing:.05em; opacity:.9;}
    .relationship-row {display:flex; justify-content:space-between; gap:10px; font-size:.83rem; margin:8px 0;}
    .relationship-row span {opacity:.8;}
    .relationship-divider {border-top:1px solid rgba(255,255,255,.18); margin:12px 0;}
    .relationship-note {font-size:.74rem; line-height:1.45; margin-top:12px; padding:9px 10px; border-radius:8px; background:rgba(255,255,255,.08);}
    .relationship-footnote {font-size:.65rem; line-height:1.4; opacity:.68; margin-top:10px;}
    .scope-engine {background:#F8FAF9; border:1px solid #E0E7E3; border-radius:14px; padding:16px 18px; margin-bottom:10px;}
    .scope-node {display:flex; flex-direction:column; padding:12px 14px; border-radius:10px; border-left:5px solid; max-width:620px;}
    .scope-node b {font-size:.95rem; color:#173D2D;}
    .scope-node span {font-size:.75rem; color:#708078; margin-top:2px;}
    .scope-node.root {background:#EEF6F2; border-left-color:#173D2D;}
    .scope-node.zone {background:#F5F0FB; border-left-color:#6A4C93; margin-left:28px;}
    .scope-node.area {background:#F0F8F4; border-left-color:#146B43; margin-left:56px;}
    .scope-line {margin:3px 0 3px 31px; color:#6A4C93; font-size:1.1rem; line-height:1;}
    .risk-card {background:#12382A; color:white; border-radius:16px; padding:20px; min-height:260px;}
    .risk-number {font-size:3.1rem; font-weight:800; line-height:1; margin:12px 0 3px;}
    .risk-label {font-size:1rem; font-weight:700; letter-spacing:.04em;}
    .alert-high {border-left:5px solid #D32F2F; background:#FFF7F7; padding:9px 12px; border-radius:6px; margin:5px 0;}
    .alert-medium {border-left:5px solid #F9A825; background:#FFFCF2; padding:9px 12px; border-radius:6px; margin:5px 0;}
    .alert-low {border-left:5px solid #4C8BF5; background:#F5F9FF; padding:9px 12px; border-radius:6px; margin:5px 0;}
    @media (max-width: 800px) {
      .block-container {padding-top:1.5rem;}
      .brand {font-size:1.25rem; line-height:1.35;}
      .subtitle {font-size:.84rem;}
      .landscape-grid {grid-template-columns:1fr; gap:8px;}
      .landscape-connector {font-size:1.5rem;}
      .landscape-connector span {display:inline; margin-left:6px;}
      .relationship-card {min-height:auto;}
      .scope-node.zone {margin-left:14px;}
      .scope-node.area {margin-left:28px;}
      .scope-line {margin-left:15px;}
    }
    </style>
    """, unsafe_allow_html=True)
