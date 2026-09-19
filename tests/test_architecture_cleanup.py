from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_legacy_root_data_module_removed():
    assert not (ROOT / "data.py").exists()


def test_legacy_root_validator_module_removed():
    assert not (ROOT / "validators.py").exists()


def test_restaurant_menu_has_no_legacy_data_import():
    source = (ROOT / "database" / "restaurant_menu_db.py").read_text(encoding="utf-8")
    assert "from data import food_menu" not in source
    assert "DEFAULT_RESTAURANT_MENU" in source


def test_single_validator_source():
    assert (ROOT / "utils" / "validators.py").exists()


def test_non_blocking_error_logging_helper_exists():
    helper = ROOT / "utils" / "error_logging.py"
    assert helper.exists()
    assert "log_non_blocking_error" in helper.read_text(encoding="utf-8")


def test_no_silent_bare_exception_pass_in_application():
    offenders = []
    for path in ROOT.rglob("*.py"):
        if any(part in {".git", "__pycache__"} for part in path.parts):
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines[:-1]):
            if line.strip() == "except Exception:" and lines[index + 1].strip() == "pass":
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []

def test_audit_request_id_migration_is_schema_guarded():
    source = (ROOT / "database" / "audit_db.py").read_text(encoding="utf-8")
    assert 'PRAGMA table_info(audit_activity_log)' in source
    assert 'if "request_id" not in columns:' in source
    assert 'ALTER TABLE audit_activity_log ADD COLUMN request_id TEXT' in source

