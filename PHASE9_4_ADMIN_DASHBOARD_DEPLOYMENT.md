# Phase 9.4 — Admin Dashboard Deployment

The admin dashboard is a same-origin, API-backed static application. The
production deployment flow is:

1. Build/validate the dashboard from the project root:
   - `python dashboard/build.py --check`
   - `python dashboard/build.py`
2. Set production API configuration/secrets through the environment.
3. Start the FastAPI service with `APP_ENV=production` and the production
   `API_HOST`, `API_PORT`, `API_WORKERS`, CORS and secret settings.
4. In production, FastAPI serves `dashboard/dist` when that build artifact is
   present; development/test runs continue to serve `dashboard/`.

The dashboard keeps the existing authentication flow (Bearer access token in
session storage), exact module/action permission checks, and same-origin API
default (`/api/v1`). A deployment can inject `window.YH_API_BASE` before
`app.js` when the API is intentionally hosted at another origin.

The build writes `dashboard/dist/manifest.json` containing SHA-256 hashes and
sizes for the four production assets. `dashboard/dist/` is ignored by Git and
should be generated as part of deployment rather than committed as source.
