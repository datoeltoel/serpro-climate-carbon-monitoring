# Phase 1 RBAC migration note

The enterprise authentication code now rejects the legacy role-section format and requires the `streamlit-authenticator` 0.4.2 username mapping.

Use this structure in Streamlit Cloud Secrets:

```toml
[auth.credentials.usernames.management]
email = "management@example.com"
name = "Management User"
password = "<bcrypt hash>"
roles = ["management"]
```

Repeat for `gis`, `forestry`, and `mrv` with their corresponding roles. Never commit the actual hashes or cookie key.
