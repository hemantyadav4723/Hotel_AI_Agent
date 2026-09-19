from pathlib import Path

from api.config import SECRET_PLACEHOLDER, settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_phase9_1_environment_template_exists_without_real_secret():
    env_example = PROJECT_ROOT / ".env.example"
    text = env_example.read_text(encoding="utf-8")
    assert "API_SECRET_KEY=" in text
    assert SECRET_PLACEHOLDER not in text
    assert ".env" in (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")


def test_phase9_1_runtime_defaults_are_safe_for_development():
    assert settings.environment in {"development", "prod", "production"}
    assert 1 <= settings.port <= 65535
    assert settings.workers >= 1
    assert settings.debug is False
    assert settings.secret_key == SECRET_PLACEHOLDER


def test_phase9_1_dev_dependency_file_reuses_runtime_dependencies():
    text = (PROJECT_ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    assert "-r requirements.txt" in text
    assert "pytest" in text
