# Phase 9.5 — AI Agent Production Setup

## Scope

- AI configuration is environment-driven and provider-neutral.
- Provider API key/secret values are supplied only through deployment secrets.
- Production readiness validates provider, model, API key, tool registry, hotel scope, and AI guardrails.
- AI business tools remain registered through the existing controlled tool layer; direct SQLite access is not introduced.
- Existing Phase 8 safety guardrails remain authoritative for prompt-injection detection, permissions, hotel scope, confirmation, human approval, and sensitive-data protection.
- Dedicated AI operational logging uses bounded rotating files and standard output. Credentials and raw secret values are not logged.

## Required production settings

- `AI_AGENT_ENABLED=true`
- `AI_AGENT_PROVIDER=<provider>`
- `AI_AGENT_MODEL=<model>`
- `AI_AGENT_API_KEY=<secret-manager value>`
- `AI_AGENT_API_SECRET=<optional provider secret when required>`
- `AI_FILE_LOGGING=true|false`
- `AI_LOG_DIR=<persistent log directory>`

Never commit real provider credentials to source control.
