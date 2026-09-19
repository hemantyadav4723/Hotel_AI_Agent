"""Build a clean, runtime-only production deployment archive."""
from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT.parent / "Hotel_AI_Agent_PRODUCTION.zip"

EXCLUDED_DIRS = {
    ".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "logs", "data/backups", "tests", "deployment",
}
EXCLUDED_FILES = {
    ".env", "requirements-dev.txt", "hotel.db",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".pyd", ".log", ".tmp", ".temp"}
EXCLUDED_ROOT_DOCS = {
    "PHASE6_ROADMAP.md", "PHASE7_IMPLEMENTATION_MAP.md", "PHASE8_FINAL_VERIFICATION.md",
    "PHASE9_1_PRODUCTION_ENVIRONMENT.md", "PHASE9_2_PRODUCTION_DATABASE.md",
    "PHASE9_3_BACKEND_PRODUCTION_SETUP.md", "PHASE9_4_ADMIN_DASHBOARD_DEPLOYMENT.md",
    "PHASE9_5_AI_AGENT_PRODUCTION_SETUP.md", "PHASE9_6_SECURITY_HARDENING.md",
    "PHASE9_7_LOGGING_MONITORING.md", "PHASE9_8_BACKUP_RECOVERY.md",
    "PHASE9_9_PRODUCTION_TESTING.md",
}


def is_excluded(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    parts = set(path.relative_to(ROOT).parts)
    if any(part in {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "logs", "tests", "deployment"} for part in parts):
        return True
    if rel.startswith("data/backups/"):
        return True
    if path.name in EXCLUDED_FILES or path.name in EXCLUDED_ROOT_DOCS:
        return True
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return True
    if rel.startswith("data/") and path.suffix.lower() == ".db":
        return True
    if rel.startswith("dashboard/") and path.name != "dist" and path.parent.name == "dashboard" and path.name in {"build.py"}:
        return True
    return False


def collect_files() -> list[Path]:
    files = []
    for path in ROOT.rglob("*"):
        if path.is_file() and not is_excluded(path):
            files.append(path)
    return sorted(files, key=lambda p: p.relative_to(ROOT).as_posix())


def validate(files: list[Path]) -> None:
    rels = {p.relative_to(ROOT).as_posix() for p in files}
    required = {"requirements.txt", ".env.example", "run_api.py", "DEPLOYMENT.md"}
    missing = sorted(required - rels)
    if missing:
        raise RuntimeError(f"Production package missing required files: {missing}")
    dashboard_required = {"dashboard/dist/index.html", "dashboard/dist/config.js", "dashboard/dist/app.js", "dashboard/dist/styles.css", "dashboard/dist/manifest.json"}
    missing = sorted(dashboard_required - rels)
    if missing:
        raise RuntimeError(f"Production dashboard artifact missing: {missing}")
    forbidden = []
    for rel in rels:
        if rel == ".env" or rel.startswith(".git/") or rel.startswith("tests/") or rel.startswith("deployment/") or rel.startswith("data/backups/"):
            forbidden.append(rel)
        if rel.endswith((".db", ".pyc", ".pyo", ".pyd", ".log")):
            forbidden.append(rel)
    if forbidden:
        raise RuntimeError(f"Forbidden runtime/development artifacts found: {sorted(forbidden)}")


def build(output: Path) -> dict[str, object]:
    # Build the dashboard artifact first; its source build tooling is excluded from the release.
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from dashboard.build import build as build_dashboard
    build_dashboard()

    files = collect_files()
    validate(files)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    manifest = {
        "format": 1,
        "application": "YADAV HOTEL AI AGENT PRO",
        "environment": "production",
        "runtime_requirements": "requirements.txt",
        "file_count": len(files),
        "excluded": sorted(EXCLUDED_ROOT_DOCS | EXCLUDED_FILES | {"tests/", ".git/", "deployment/", "data/backups/", "runtime databases", "Python caches", "logs"}),
        "files": [p.relative_to(ROOT).as_posix() for p in files],
    }
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT).as_posix())
        archive.writestr("DEPLOYMENT_MANIFEST.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the clean YADAV HOTEL production package")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest = build(args.output.resolve())
    print(f"Production package: PASS ({manifest['file_count']} runtime files)")
    print(f"Output: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
