"""Small in-process API monitoring counters for operational health visibility."""
from threading import Lock

_metrics = {"requests": 0, "errors": 0, "status_4xx": 0, "status_5xx": 0, "total_duration_ms": 0.0}
_lock = Lock()


def record_request(status_code: int, duration_ms: float, error: bool = False) -> None:
    with _lock:
        _metrics["requests"] += 1
        _metrics["total_duration_ms"] += duration_ms
        if error:
            _metrics["errors"] += 1
        if 400 <= status_code < 500:
            _metrics["status_4xx"] += 1
        elif status_code >= 500:
            _metrics["status_5xx"] += 1


def snapshot() -> dict:
    with _lock:
        data = dict(_metrics)
    requests = data["requests"]
    data["average_duration_ms"] = round(data["total_duration_ms"] / requests, 2) if requests else 0.0
    data["total_duration_ms"] = round(data["total_duration_ms"], 2)
    return data


def reset() -> None:
    with _lock:
        for key in _metrics:
            _metrics[key] = 0 if key != "total_duration_ms" else 0.0
