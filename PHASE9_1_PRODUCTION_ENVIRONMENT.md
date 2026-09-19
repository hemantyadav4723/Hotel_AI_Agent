# Phase 9.1 — Production Environment Preparation

This project keeps application configuration in environment variables. Real
secrets are not stored in the repository. `.env.example` documents the
required deployment variables without containing real credentials.

## Runtime configuration

| Variable | Purpose | Development default | Production guidance |
|---|---|---|---|
| `APP_ENV` | Runtime environment | `development` | Set `production` |
| `LOG_LEVEL` | Application log level | `INFO` | Usually `INFO` or `WARNING` |
| `API_HOST` | API bind address | `127.0.0.1` | Usually `0.0.0.0` behind a reverse proxy |
| `API_PORT` | API port | `8000` | Set by deployment platform |
| `API_WORKERS` | Uvicorn worker count | `1` | Tune after production load testing |
| `API_DEBUG` | Debug mode | `false` | Must remain `false` |
| `API_SECRET_KEY` | JWT signing secret | Development placeholder | Required strong secret |
| `API_CORS_ORIGINS` | Browser origins | `*` | Explicit HTTPS origins only |
| `API_ACCESS_TOKEN_MINUTES` | JWT lifetime | `60` | Set according to security policy |
| `API_RATE_LIMIT_PER_MINUTE` | API request limit | `120` | Tune to deployment capacity |

AI variables are documented in `.env.example` and remain provider-neutral.

## Dependency management

- `requirements.txt` contains runtime dependencies.
- `requirements-dev.txt` extends runtime dependencies with test tooling.
- Production deployments should install only runtime dependencies.
- A deployment-specific lock/supply-chain verification step belongs in the
  later production packaging/deployment work; this point does not introduce
  a duplicate dependency list.

## Start commands

Development:

```text
python run_api.py
```

The launcher uses environment-driven host, port, worker and log settings and
never enables Uvicorn reload automatically.

## Secret rules

1. Never put real credentials in source files.
2. Never commit `.env`.
3. Inject production secrets through the deployment environment or secret
   manager.
4. Production readiness must reject the development JWT placeholder and
   wildcard CORS.

## Scope of 9.1

This point prepares the application for production configuration. It does
not yet perform the actual server deployment, domain/HTTPS setup, database
backup rollout, monitoring rollout, or final production release.
