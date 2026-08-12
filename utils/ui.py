import streamlit as st


def setup_page():
    st.set_page_config(page_title="SERPRO Climate & Carbon Monitoring", page_icon="🌿", layout="wide", initial_sidebar_state="expanded")
    st.markdown("""
    <style>
    .block-container {padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1500px;}
    [data-testid="stSidebar"] {background: #09231A;}
    [data-testid="stSidebar"] * {color: #F4F7F5;}
    .brand {font-size: 1.55rem; font-weight: 700; color: #0B5D3B;}
    .subtitle {color: #66756E; margin-top: -0.6rem; margin-bottom: 1rem;}
    .status {font-size: 0.82rem; color: #4E665B; text-align: right;}
    .metric-card {background:#FFFFFF; border:1px solid #E4EAE7; border-radius:14px; padding:16px 18px; min-height:105px; box-shadow:0 1px 3px rgba(0,0,0,.04);}
    .metric-label {font-size:.78rem; color:#66756E; text-transform:uppercase; letter-spacing:.04em;}
    .metric-value {font-size:1.7rem; font-weight:700; color:#12382A; margin-top:5px;}
    .metric-delta {font-size:.78rem; color:#4B7A64; margin-top:3px;}
    .section-title {font-size:1.1rem; font-weight:700; color:#173D2D; margin:12px 0 6px;}
    .risk-card {background:#12382A; color:white; border-radius:16px; padding:20px; min-height:260px;}
    .risk-number {font-size:3.1rem; font-weight:800; line-height:1; margin:12px 0 3px;}
    .risk-label {font-size:1rem; font-weight:700; letter-spacing:.04em;}
    .alert-high {border-left:5px solid #D32F2F; background:#FFF7F7; padding:9px 12px; border-radius:6px; margin:5px 0;}
    .alert-medium {border-left:5px solid #F9A825; background:#FFFCF2; padding:9px 12px; border-radius:6px; margin:5px 0;}
    .alert-low {border-left:5px solid #4C8BF5; background:#F5F9FF; padding:9px 12px; border-radius:6px; margin:5px 0;}
    </style>
    """, unsafe_allow_html=True)
