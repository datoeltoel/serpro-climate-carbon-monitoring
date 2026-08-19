"""Authentication and role-based access control for SERPRO MRV.

Credentials and cookie secrets are read from Streamlit secrets. No user
credentials are committed to the repository.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

import streamlit as st
import streamlit_authenticator as stauth

ROLES = {
    "management": "Management",
    "gis_specialist": "GIS Specialist",
    "forestry_planner": "Forestry Planner",
    "mrv_specialist": "MRV Specialist",
}

ROLE_PERMISSIONS = {
    "management": {"executive_summary", "climate_monitoring"},
    "gis_specialist": {"executive_summary", "mrv_carbon_tracker", "climate_monitoring", "spatial_data_catalog"},
    "forestry_planner": {"executive_summary", "mrv_carbon_tracker", "climate_monitoring"},
    "mrv_specialist": {"executive_summary", "mrv_carbon_tracker", "climate_monitoring", "spatial_data_catalog"},
}


def _secrets_config() -> dict[str, Any]:
    if "auth" not in st.secrets:
        raise RuntimeError(
            "Authentication is not configured. Add the [auth] section to "
            "Streamlit Cloud Secrets before deploying the enterprise app."
        )
    return deepcopy(dict(st.secrets["auth"]))


def get_authenticator() -> stauth.Authenticate:
    """Create one authenticator per browser session."""
    if "serpro_authenticator" in st.session_state:
        return st.session_state.serpro_authenticator

    config = _secrets_config()
    credentials = dict(config["credentials"])
    cookie = dict(config["cookie"])

    authenticator = stauth.Authenticate(
        credentials=credentials,
        cookie_name=str(cookie["name"]),
        cookie_key=str(cookie["key"]),
        cookie_expiry_days=float(cookie.get("expiry_days", 30)),
        auto_hash=False,
    )
    st.session_state.serpro_authenticator = authenticator
    return authenticator


def _restore_cookie(authenticator: stauth.Authenticate) -> None:
    """Attempt silent cookie restoration on a hard refresh."""
    try:
        authenticator.login(location="unrendered")
    except Exception:
        # The visible login form below remains the source of truth.
        pass


def require_authentication() -> tuple[stauth.Authenticate, str, str, list[str]]:
    """Render login when needed and return authenticated user context."""
    authenticator = get_authenticator()
    _restore_cookie(authenticator)

    authenticated = st.session_state.get("authentication_status")
    if authenticated is not True:
        st.markdown("## 🔐 SERPRO MRV Carbon Monitoring")
        st.caption("Enterprise access control")
        authenticator.login(location="main", key="serpro-login")
        authenticated = st.session_state.get("authentication_status")

        if authenticated is False:
            st.error("Username atau password tidak valid.")
        elif authenticated is None:
            st.info("Silakan login untuk melanjutkan.")
        st.stop()

    username = str(st.session_state.get("username", ""))
    name = str(st.session_state.get("name", username))
    user = dict(get_authenticator().credentials.get("usernames", {}).get(username, {}))
    roles = user.get("roles", st.session_state.get("roles", []))
    if isinstance(roles, str):
        roles = [roles]
    roles = [str(role).lower() for role in roles]

    st.session_state["serpro_user"] = username
    st.session_state["serpro_name"] = name
    st.session_state["serpro_roles"] = roles
    return authenticator, username, name, roles


def has_permission(page_key: str, roles: list[str] | None = None) -> bool:
    roles = roles if roles is not None else st.session_state.get("serpro_roles", [])
    return any(page_key in ROLE_PERMISSIONS.get(role, set()) for role in roles)


def require_role(*allowed_roles: str) -> None:
    roles = st.session_state.get("serpro_roles", [])
    allowed = {role.lower() for role in allowed_roles}
    if not allowed.intersection(roles):
        st.error("Anda tidak memiliki akses ke modul ini.")
        st.stop()


def render_user_sidebar(authenticator: stauth.Authenticate, name: str, roles: list[str]) -> None:
    with st.sidebar:
        st.markdown("### 🌿 SERPRO")
        st.caption("Climate & Carbon Monitoring · MRV")
        st.markdown("---")
        st.markdown(f"**User**  \n{name}")
        role_labels = [ROLES.get(role, role.replace("_", " ").title()) for role in roles]
        st.markdown(f"**Role**  \n{', '.join(role_labels) if role_labels else 'Unassigned'}")
        st.markdown("---")
        authenticator.logout(button_name="Logout", location="sidebar")
