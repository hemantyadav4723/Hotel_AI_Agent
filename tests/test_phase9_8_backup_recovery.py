import json
import os
import sqlite3
import subprocess
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run_isolated(tmp_path):
    db_path = tmp_path / "production" / "hotel.db"
    backup_dir = tmp_path / "production" / "backups"
    env = os.environ.copy()
    env.update({
        "HOTEL_DATABASE_PATH": str(db_path),
        "HOTEL_DATABASE_BACKUP_DIR": str(backup_dir),
        "SQLITE_BUSY_TIMEOUT_MS": "45000",
        "SQLITE_JOURNAL_MODE": "WAL",
        "SQLITE_SYNCHRONOUS": "NORMAL",
        "API_SECRET_KEY": "SUPER-SECRET-TEST-VALUE-DO-NOT-ARCHIVE",
        "AI_AGENT_API_KEY": "AI-SECRET-TEST-VALUE-DO-NOT-ARCHIVE",
        "AI_AGENT_API_SECRET": "AI-SECOND-SECRET-DO-NOT-ARCHIVE",
    })
    code = r'''
import json, os, zipfile
from database.database import initialize_database, get_connection
from database.database_admin import backup_database, backup_configuration, restore_database
initialize_database()
config_path = backup_configuration()
db_backup = backup_database(backup_type="PHASE9_8_TEST")
with get_connection() as c:
    c.execute("CREATE TABLE IF NOT EXISTS phase9_8_probe(value TEXT)")
    c.execute("DELETE FROM phase9_8_probe")
    c.execute("INSERT INTO phase9_8_probe(value) VALUES ('after-backup')")
    c.commit()
restore_database(db_backup)
with get_connection() as c:
    restored = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='phase9_8_probe'").fetchone()
    history = c.execute("SELECT backup_type, status FROM database_backup_history ORDER BY backup_id").fetchall()
print(f"CONFIG={config_path}")
print(f"DBBACKUP={db_backup}")
print("PROBE_RESTORED=" + str(restored is None))
print("CONFIG_TYPES=" + ",".join(f"{row[0]}:{row[1]}" for row in history))
with zipfile.ZipFile(config_path) as z:
    names = set(z.namelist())
    print("CONFIG_FILES=" + ",".join(sorted(names)))
    print("HAS_ENV=" + str(any(n == '.env' or n.endswith('/.env') for n in names)))
    metadata = z.read("configuration_backup_metadata.json").decode()
    print("SECRET_LEAK=" + str(any(secret in metadata for secret in [
        "SUPER-SECRET-TEST-VALUE-DO-NOT-ARCHIVE",
        "AI-SECRET-TEST-VALUE-DO-NOT-ARCHIVE",
        "AI-SECOND-SECRET-DO-NOT-ARCHIVE",
    ])))
'''
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=PROJECT_ROOT, env=env,
        capture_output=True, text=True, check=True,
    )
    return result.stdout, db_path, backup_dir


def test_phase9_8_configuration_backup_is_secret_free(tmp_path):
    stdout, _, backup_dir = _run_isolated(tmp_path)
    assert "HAS_ENV=False" in stdout
    assert "SECRET_LEAK=False" in stdout
    assert "CONFIGURATION:SUCCESS" in stdout
    archives = list(backup_dir.glob("configuration_backup_*.zip"))
    assert len(archives) == 1
    with zipfile.ZipFile(archives[0]) as archive:
        assert "configuration_manifest.json" in archive.namelist()
        assert "configuration_backup_metadata.json" in archive.namelist()
        metadata = json.loads(archive.read("configuration_backup_metadata.json"))
        secret_items = [x for x in metadata["environment_variables"] if x["secret"]]
        assert secret_items
        assert all(x["value"] == "<REDACTED>" for x in secret_items)


def test_phase9_8_database_backup_restore_recovery(tmp_path):
    stdout, db_path, backup_dir = _run_isolated(tmp_path)
    assert "PROBE_RESTORED=True" in stdout
    assert "DBBACKUP=" in stdout
    assert db_path.exists()
    db_backups = list(backup_dir.glob("hotel_backup_*.db"))
    assert db_backups
    with sqlite3.connect(db_backups[0]) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
