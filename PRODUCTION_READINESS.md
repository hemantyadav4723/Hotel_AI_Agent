# Phase 8.21 — AI Production Readiness

Production configuration is environment-driven. Secrets must be supplied through environment/secret management; credentials are not stored in AI modules.

## Runtime controls
- `APP_ENV` — `development` / `production`
- `LOG_LEVEL` — logging level
- `API_SECRET_KEY` — production JWT secret
- `API_CORS_ORIGINS` — explicit production origins
- `API_RATE_LIMIT_PER_MINUTE` — request rate limit
- `AI_AGENT_ENABLED`, `AI_AGENT_PROVIDER`, `AI_AGENT_MODEL` — AI provider configuration
- `AI_AGENT_TIMEOUT_SECONDS` — bounded AI timeout
- `AI_AGENT_MAX_RETRIES` / `AI_AGENT_RETRY_BACKOFF_SECONDS` — bounded retry policy
- `AI_MAX_CONCURRENT_REQUESTS` — concurrency readiness limit
- `HEALTH_CHECK_TIMEOUT_SECONDS` — health-check budget

## Health endpoints
- `/health` — database/application liveness
- `/health/ready` — database + production configuration readiness
- `/health/ai` — AI configuration readiness

## Deployment notes
Use HTTPS, a real secret manager/environment injection, explicit CORS origins, log collection, external monitoring, and the existing SQLite backup/restore mechanism before production deployment.

The implementation remains provider-neutral and does not add a second database or credential store.


## Phase 8 deep cleanup notes
- Runtime restaurant menu data is SQLite-backed and hotel-scoped. The former root `data.py` seed source has been removed; immutable default menu seed values live with the restaurant-menu database module and are used only when a hotel has no menu item yet.
- The unused root `validators.py` duplicate has been removed. `utils/validators.py` is the single validation utility source.
- Non-blocking audit/notification operations now emit structured warning logs instead of silently swallowing exceptions. Transactional exceptions that roll back and re-raise remain unchanged.
- Automation notification paths support idempotency keys; callers should provide a stable key for retry-safe repeated notification/reminder execution.
- Production database backups must be verified before restore. Backups created from an older schema must be migrated/validated against the target application schema before being promoted as the active database.
- Deployment artifacts should exclude `.git/`, Python cache directories, local development databases, and other source-control/runtime metadata.
