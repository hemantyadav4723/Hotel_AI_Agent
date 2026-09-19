# Phase 9.7 — Logging & Monitoring

Implemented operational logging and monitoring foundations for production.

## Components
- Application logs: `logs/application.log`
- API request logs: `logs/api.log`
- Error logs: `logs/error.log`
- AI logs: `logs/ai.log`
- Existing SQLite audit activity remains the authoritative business/audit trail.
- `/api/v1/health`, `/api/v1/health/live`, `/api/v1/health/ready`, and `/api/v1/health/ai` provide health monitoring.
- `/api/v1/monitoring` exposes bounded in-process request counters and timing metrics only; it does not expose request bodies, credentials, tokens, or secrets.

All file logs rotate at 5 MB with five backups. Logging is disabled from source-code secrets and request bodies by design.
