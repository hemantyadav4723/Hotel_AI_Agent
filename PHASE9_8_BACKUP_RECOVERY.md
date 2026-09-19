# Phase 9.8 — Backup & Recovery

This phase provides the production backup and recovery foundation.

## Database backup
- `database.database_admin.backup_database()` creates a consistent SQLite backup using the SQLite backup API.
- Every database backup is integrity-checked and foreign-key checked before promotion.
- Backup history is recorded in `database_backup_history`.

## Configuration backup
- `database.database_admin.backup_configuration()` creates a ZIP containing safe deployment/configuration artifacts and a recovery manifest.
- Real `.env` files and credential values are never copied.
- Secret environment variables are represented only as `<REDACTED>` in the manifest.
- The archive is verified before it is promoted to the configured backup directory.

## Recovery procedure
1. Stop application/API workers before a production restore.
2. Identify a verified database backup from `data/backups/` or the configured backup volume.
3. Validate the backup with the application's database validation/restore mechanism.
4. Run `restore_database(<backup_path>)`; it creates a verified pre-restore backup first.
5. Restart the application and run database/health checks.
6. Validate authentication, hotel scope, permissions, dashboard, and AI health before returning traffic.
7. Restore configuration artifacts only after review; inject production secrets separately through the deployment environment/secret manager.

## Restore testing
The Phase 9.8 regression test creates an isolated production-style database, creates a verified backup, mutates the database, restores the backup, and verifies that the post-backup mutation is removed. It also verifies that configuration backups contain no real `.env` file or secret values.

## Safety rules
- Never place `API_SECRET_KEY`, `AI_AGENT_API_KEY`, `AI_AGENT_API_SECRET`, or other credential values in a configuration backup.
- Never restore an unverified SQLite file into the active production database.
- Backups from an older schema must be migrated/validated against the target application schema before promotion.
