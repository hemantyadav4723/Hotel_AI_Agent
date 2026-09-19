"""Build the production admin dashboard artifact.

The dashboard is intentionally framework-free. This build step validates the
static entrypoints, copies only production assets into ``dashboard/dist`` and
writes a SHA-256 manifest so deployment can verify exactly what was built.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "dashboard"
DIST = SOURCE / "dist"
ASSETS = ("index.html", "config.js", "app.js", "styles.css")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_source() -> None:
    missing = [name for name in ASSETS if not (SOURCE / name).is_file()]
    if missing:
        raise RuntimeError(f"Dashboard build assets missing: {', '.join(missing)}")

    html = (SOURCE / "index.html").read_text(encoding="utf-8")
    required_refs = (
        'href="/dashboard/styles.css"',
        'src="/dashboard/config.js"',
        'src="/dashboard/app.js"',
    )
    for marker in required_refs:
        if marker not in html:
            raise RuntimeError(f"Dashboard index is missing required asset reference: {marker}")

    js = (SOURCE / "app.js").read_text(encoding="utf-8")
    config = (SOURCE / "config.js").read_text(encoding="utf-8")
    for marker in ("Authorization", "Bearer", "hasPermission", "isActionAllowed"):
        if marker not in js:
            raise RuntimeError(f"Dashboard authentication/authorization marker missing: {marker}")
    for marker in ("YH_API_BASE", "YH_DASHBOARD_CONFIG", "requestTimeoutMs"):
        if marker not in config:
            raise RuntimeError(f"Dashboard runtime configuration marker missing: {marker}")


def build() -> dict[str, object]:
    validate_source()
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    manifest: dict[str, object] = {"version": 1, "assets": {}}
    for name in ASSETS:
        source = SOURCE / name
        target = DIST / name
        shutil.copy2(source, target)
        manifest["assets"][name] = {
            "sha256": _sha256(target),
            "size": target.stat().st_size,
        }

    manifest_path = DIST / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the YADAV HOTEL production dashboard")
    parser.add_argument("--check", action="store_true", help="Validate dashboard production inputs without creating dist")
    args = parser.parse_args()

    validate_source()
    if args.check:
        print("Dashboard production build check: PASS")
        return 0

    manifest = build()
    print(f"Dashboard production build: PASS ({len(manifest['assets'])} assets)")
    print(f"Output: {DIST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
