# Phase 9.6 — Security Hardening

Implemented production security boundaries for authentication, secrets, API access, permissions, and deployment security.

## Authentication security
- JWT access tokens continue to use an explicit access-token type and expiration.
- Token claims now require user id, username, role, and a positive hotel id.
- Existing database-backed user status and hotel-scope validation remains authoritative.

## Secret protection
- Production startup fails closed when the API secret is missing/placeholder/too short.
- Production CORS and trusted-host wildcards are rejected by the production readiness validator.
- Real credentials remain environment/secret-manager configuration, not source code.

## API protection
- Trusted hosts are enforced through Starlette middleware.
- Production HTTPS redirect can be enabled with `API_FORCE_HTTPS=true` and is enabled by default in production.
- Existing request-size limits, rate limiting, security headers, request correlation, CORS and authentication boundaries remain active.
- Production API documentation can remain disabled with `API_DOCS_ENABLED=false`.

## Permission enforcement
- Existing backend `require_permission()` dependencies remain the authoritative authorization boundary.
- Frontend/dashboard permission filtering is not treated as a security boundary.
- Hotel scope remains enforced through authenticated user context and database queries.

## Production security audit
- Dedicated Phase 9.6 tests cover trusted-host enforcement, token claim validation, and fail-closed production secret validation.
- Full regression suite must remain green before Phase 9.6 final pass.
