# Phase 9.9 — Production Testing

This phase validates the production-oriented system without changing business data or requiring a real external AI provider.

## Scope

1. Backend
2. Dashboard
3. Authentication
4. Database
5. AI
6. End-to-end
7. Production-like testing

## Validation performed

- FastAPI health/liveness/version and protected API boundary.
- Production dashboard build validation and same-origin serving.
- Admin authentication, JWT-protected identity, and permission retrieval.
- SQLite integrity, foreign keys, and protected master data.
- AI status, hotel context, tool registry, and guardrail registry.
- End-to-end login → dashboard → authenticated API → AI → monitoring flow.
- Isolated production-like process using production environment variables, explicit CORS/trusted hosts, HTTPS, disabled API docs, isolated SQLite database, configured AI readiness, and authenticated request verification.

## Production-like test guarantees

- No real provider API key is required.
- No production database is modified.
- The isolated database is copied from the current clean project database.
- Production documentation endpoints remain disabled when configured.
- Authentication and hotel context are verified in the isolated process.
- Dashboard remains available while protected APIs require authentication.
