# Cloudflare Access Policy (Required for Public Routes)

When exposing this stack via Cloudflare Tunnel, apply Access policy to every published route:
- API: `api.<your-domain>`
- UI: `ui.<your-domain>` or `/ui` path route
- Airflow: `airflow.<your-domain>`

Recommended baseline policy:
1. Action: `Allow`
2. Include: your identity provider group or allowlisted emails
3. Session duration: 8h
4. Enable one-time PIN or SSO login
5. Disable anonymous bypass

Validation checklist:
- Unauthenticated browser should be redirected to Cloudflare Access login.
- Authenticated user can open `/ui`, `/docs`, and Airflow routes.
- API route still requires `X-API-Key` after Access authentication.

Notes:
- Access policy protects the edge route; API key remains application-level auth.
- Rotate tunnel token and API keys if leaked.
