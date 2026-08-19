"""Authentication and role-based access control for SERPRO MRV."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

import streamlit as st
import streamlit_authenticator as stauth

ROLES = {
    "guest": "Guest",
    "management": "Management",
    "gis_specialist": "GIS Specialist",
    "forestry_planner": "Forestry Planner",
    "mrv_specialist": "MRV Specialist",
}

ROLE_PERMISSIONS = {
    "guest": {"climate_monitoring"},
    "management": {"climate_monitoring"},
    "gis_specialist": {"climate_monitoring", "vegetation_monitoring", "fire_monitoring", "climate_risk"},
    "forestry_planner": {"climate_monitoring", "vegetation_monitoring", "fire_monitoring", "climate_risk"},
    "mrv_specialist": {"climate_monitoring", "vegetation_monitoring", "fire_monitoring", "climate_risk"},
}


def _secrets_config() -> dict[str, Any]:
    if "auth" not in st.secrets:
        raise RuntimeError("Authentication is not configured. Add [auth] to Streamlit Secrets.")
    config = deepcopy(dict(st.secrets["auth"]))
    credentials = config.get("credentials")
    cookie = config.get("cookie")
    if not isinstance(credentials, dict) or not isinstance(cookie, dict):
        raise RuntimeError("Authentication requires [auth.credentials] and [auth.cookie].")
    usernames = credentials.get("usernames")
    if not isinstance(usernames, dict) or not usernames:
        raise RuntimeError("Use [auth.credentials.usernames.<username>] for each account.")
    for username, user in usernames.items():
        if not isinstance(user, dict) or not user.get("name") or not user.get("password"):
            raise RuntimeError(f"Invalid RBAC user entry: {username!r}.")
        roles = user.get("roles", [])
        if isinstance(roles, str):
            roles = [roles]
        if not roles:
            raise RuntimeError(f"User {username!r} must have at least one role.")
        unknown = sorted(set(str(r).lower() for r in roles) - set(ROLES))
        if unknown:
            raise RuntimeError(f"User {username!r} has unknown role(s): {', '.join(unknown)}.")
    for field in ("name", "key"):
        if not cookie.get(field):
            raise RuntimeError(f"Missing auth.cookie.{field} in Streamlit Secrets.")
    return config


def get_authenticator() -> stauth.Authenticate:
    if "serpro_authenticator" not in st.session_state:
        config = _secrets_config()
        cookie = dict(config["cookie"])
        st.session_state.serpro_authenticator = stauth.Authenticate(
            credentials=dict(config["credentials"]),
            cookie_name=str(cookie["name"]),
            cookie_key=str(cookie["key"]),
            cookie_expiry_days=float(cookie.get("expiry_days", 30)),
            auto_hash=True,
        )
    return st.session_state.serpro_authenticator


def require_authentication() -> tuple[stauth.Authenticate, str, str, list[str]]:
    authenticator = get_authenticator()
    try:
        authenticator.login(location="unrendered")
    except Exception:
        pass
    if st.session_state.get("authentication_status") is not True:
        st.markdown("## 🔐 SERPRO Climate & Carbon Monitoring")
        st.caption("Silakan masuk menggunakan username dan password.")
        authenticator.login(location="main", key="serpro-login")
        status = st.session_state.get("authentication_status")
        if status is False:
            st.error("Username atau password tidak valid.")
        else:
            st.info("Masukkan username dan password untuk melanjutkan.")
        st.stop()
    username = str(st.session_state.get("username", ""))
    name = str(st.session_state.get("name", username))
    user = dict(authenticator.credentials.get("usernames", {}).get(username, {}))
    roles = user.get("roles", st.session_state.get("roles", []))
    if isinstance(roles, str):
        roles = [roles]
    roles = [str(r).lower() for r in roles]
    st.session_state.update(serpro_user=username, serpro_name=name, serpro_roles=roles)
    return authenticator, username, name, roles


def has_permission(page_key: str, roles: list[str] | None = None) -> bool:
    roles = roles if roles is not None else st.session_state.get("serpro_roles", [])
    return any(page_key in ROLE_PERMISSIONS.get(role, set()) for role in roles)


def render_user_sidebar(authenticator: stauth.Authenticate, name: str, roles: list[str]) -> None:
    with st.sidebar:
        st.markdown(f"**User:** {name}")
        labels = [ROLES.get(r, r.replace("_", " ").title()) for r in roles]
        st.caption(f"Role: {', '.join(labels)}")
        authenticator.logout(button_name="Logout", location="sidebar")
