import os
import sqlite3
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _fresh_database_module(tmp_path):
    db_path = tmp_path / "production" / "hotel.db"
    backup_dir = tmp_path / "production" / "backups"
    env = os.environ.copy()
    env.update({
        "HOTEL_DATABASE_PATH": str(db_path),
        "HOTEL_DATABASE_BACKUP_DIR": str(backup_dir),
        "SQLITE_BUSY_TIMEOUT_MS": "45000",
        "SQLITE_JOURNAL_MODE": "WAL",
        "SQLITE_SYNCHRONOUS": "NORMAL",
    })
    code = '''
from database.database import configure_database, initialize_database, get_connection, DATABASE_PATH, DATABASE_BACKUP_DIR
from database.database_admin import run_database_health_check, is_database_healthy, backup_database, restore_database

configure_database()
initialize_database()
report = run_database_health_check()
print(DATABASE_PATH)
print(DATABASE_BACKUP_DIR)
print(report["journal_mode"])
print(report["busy_timeout_ms"])
print(report["schema_migrations"])
print(is_database_healthy(report))
path = backup_database(backup_type="TEST")
print(path)
with get_connection() as c:
    c.execute("CREATE TABLE IF NOT EXISTS phase9_2_probe(value TEXT)")
    c.execute("DELETE FROM phase9_2_probe")
    c.execute("INSERT INTO phase9_2_probe(value) VALUES ('after-backup')")
    c.commit()
restore_database(path)
with get_connection() as c:
    row = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='phase9_2_probe'").fetchone()
    history = c.execute("SELECT COUNT(*) FROM database_backup_history").fetchone()[0]
    print("MISSING" if row is None else "PRESENT")
    print(f"HISTORY={history}")
'''
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout, db_path, backup_dir


def test_phase9_2_production_database_configuration_and_health(tmp_path):
    stdout, db_path, backup_dir = _fresh_database_module(tmp_path)
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    assert str(db_path) in lines
    assert str(backup_dir) in lines
    assert "wal" in lines
    assert "45000" in lines
    assert "True" in lines
    assert db_path.exists()
    assert backup_dir.exists()


def test_phase9_2_backup_restore_round_trip(tmp_path):
    stdout, db_path, backup_dir = _fresh_database_module(tmp_path)
    assert "MISSING" in stdout
    assert "HISTORY=" in stdout
    backups = list(backup_dir.glob("hotel_backup_*.db"))
    assert backups
    with sqlite3.connect(backups[0]) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='database_backup_history'").fetchone() is not None
