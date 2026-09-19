# Production Deployment Package

## Package contents

The production package contains runtime application code, the production dashboard artifact, `requirements.txt`, `.env.example`, and deployment/runtime documentation.

## Deliberately excluded

The package excludes `.git/`, tests, development-only requirements, Python caches, local SQLite databases, database backups, logs, `.env`, and development/roadmap documents.

## Installation

1. Extract the production package on the target server.
2. Create a production virtual environment.
3. Install runtime dependencies only:
   `python -m pip install -r requirements.txt`
4. Inject production environment variables from the deployment platform or secret manager. Never copy a real `.env` into the package.
5. Initialize/verify the production database using the application's database initialization flow.
6. Start the API with `python run_api.py` or the platform's process manager.

## Required production configuration

Use `.env.example` only as a variable reference. Set `APP_ENV=production`, a strong `API_SECRET_KEY`, explicit HTTPS CORS origins, trusted hosts, and the required AI provider settings through environment/secret management.

## Release verification

The package builder validates that required runtime files and the production dashboard artifact are present and that excluded development/runtime artifacts are absent. It also writes `DEPLOYMENT_MANIFEST.json` into the release archive.

## Database and recovery

Do not ship a local development database inside the application package. Use the Phase 9.2/9.8 database initialization, backup, and restore procedures against the target production environment.

## Security

Do not commit or package API keys, JWT secrets, provider secrets, passwords, `.env` files, or local credential stores. Keep HTTPS and the Phase 9.6 production security controls enabled.
