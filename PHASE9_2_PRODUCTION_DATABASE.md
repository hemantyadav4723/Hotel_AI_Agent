# Phase 9.2 — Production Database

This point hardens the existing SQLite foundation for a production runtime.
It does not replace the existing database architecture or introduce a second
database layer.

## 9.2.1 Production SQLite configuration

- `HOTEL_DATABASE_PATH` selects the active SQLite file.
- `HOTEL_DATABASE_BACKUP_DIR` selects the default backup directory.
- `SQLITE_BUSY_TIMEOUT_MS` controls write contention waiting.
- `SQLITE_JOURNAL_MODE` defaults to `WAL`.
- `SQLITE_SYNCHRONOUS` defaults to `NORMAL`.
- The application creates the configured database/backup directories when needed.
- Existing business modules continue using the same `get_connection()` API.

## 9.2.2 Database initialization

`initialize_database()` now configures the SQLite runtime before any table
creation or migration work. Existing idempotent table creation, seed and
migration functions remain the source of truth for the schema.

## 9.2.3 Migration handling

The existing schema metadata and migration registry remain in use.
`get_schema_migration_status()` exposes applied migrations in deterministic
order without creating a second migration system. The foundation registry is
idempotent and is initialized only after business-table migrations complete.

## 9.2.4 Backup / restore foundation

- Backups use SQLite's online backup API.
- WAL is checkpointed before backup.
- Backup files are integrity-checked and foreign-key checked before promotion.
- Backup history is recorded in `database_backup_history`.
- Restore validates the source backup first.
- A verified pre-restore backup is retained before replacement.
- Temporary restore files are promoted atomically.
- Stale `-wal` / `-shm` sidecars are removed after restore.
- A backup must contain both business tables and database foundation tables.

## 9.2.5 Database safety

Health checks now report configured vs active SQLite runtime settings, schema
migrations, integrity, foreign keys, hotel scope, and legacy TXT references.
A database is healthy only when the configured journal mode and minimum busy
timeout are active in addition to the existing integrity/scope checks.

Production deployments should place the database and backup directory on
persistent storage and should not commit runtime `.db` files to source control.
