
def test_production_logging_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("APP_FILE_LOGGING", "true")
    from utils import production_logging
    production_logging._CONFIGURED = False
    production_logging.configure_production_logging()
    log_dir = tmp_path / "logs"
    assert log_dir.is_dir()
    assert (log_dir / "application.log").exists()
    assert (log_dir / "api.log").exists()
    assert (log_dir / "error.log").exists()


def test_monitoring_snapshot_is_bounded_and_secret_free():
    from api.monitoring import record_request, snapshot, reset
    reset()
    record_request(200, 10.5)
    record_request(500, 20.0, error=True)
    data = snapshot()
    assert data["requests"] == 2
    assert data["status_5xx"] == 1
    assert data["errors"] == 1
    assert data["average_duration_ms"] == 15.25
    assert "token" not in data
    reset()


def test_monitoring_route_contract():
    from fastapi.testclient import TestClient
    from api.app import app
    with TestClient(app) as client:
        response = client.get("/api/v1/monitoring")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "requests" in payload["metrics"]


def test_rate_limited_requests_are_recorded_in_monitoring():
    from collections import deque
    import time
    from fastapi.testclient import TestClient
    from api.app import app, _rate_windows
    from api import monitoring
    monitoring.reset()
    _rate_windows["testclient"] = deque([time.monotonic()] * 120)
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 429
    data = monitoring.snapshot()
    assert data["requests"] == 1
    assert data["status_4xx"] == 1
    _rate_windows.pop("testclient", None)
    monitoring.reset()

def test_non_blocking_logger_uses_application_log(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("APP_FILE_LOGGING", "true")
    import logging
    from utils import production_logging
    production_logging._CONFIGURED = False
    production_logging.configure_production_logging()
    logger = logging.getLogger("hotel_ai_agent")
    assert any(getattr(h, "baseFilename", "").endswith("application.log") for h in logger.handlers)
