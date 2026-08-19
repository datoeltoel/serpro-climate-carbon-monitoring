# Phase 1 RBAC Acceptance

## Roles

| Role | Executive Summary | MRV Carbon Tracker | Climate Monitoring | Spatial Data Catalog |
|---|---:|---:|---:|---:|
| Management | Yes | No | Yes | No |
| GIS Specialist | Yes | Yes | Yes | Yes |
| Forestry Planner | Yes | Yes | Yes | No |
| MRV Specialist | Yes | Yes | Yes | Yes |

## Authentication requirements

- Credentials are stored only in Streamlit Cloud Secrets.
- Passwords must be bcrypt hashes.
- Cookie name/key are supplied through the `auth.cookie` section.
- Credentials must use `auth.credentials.usernames.<username>` so they match the `streamlit-authenticator` 0.4.2 configuration contract.
- No real credentials or cookie secrets may be committed to Git.

## Acceptance checks

1. Unauthenticated users receive the login screen.
2. Valid users are authenticated and their roles are stored in session state.
3. Users see only pages permitted by their role.
4. Direct access to a restricted enterprise page is rejected by `require_role()`.
5. Logout clears the authentication session.
6. BMKG Local Weather Forecast remains available as a hidden transition route and is not mixed into the enterprise navigation group.
7. Existing analytical modules remain intact while the enterprise shell is being migrated.

## Exit criteria

Phase 1 is considered complete when the CI acceptance workflow passes and the same four role scenarios are manually verified once in Streamlit Cloud.
