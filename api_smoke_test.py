"""FastAPI backend smoke test.

Run from the Hotel_AI_Agent directory:
    python api_smoke_test.py
"""

from fastapi.testclient import TestClient

from api.app import app


client = TestClient(app)
checks = [
    ("GET", "/api/v1/health", 200),
    ("GET", "/api/v1/version", 200),
    ("GET", "/openapi.json", 200),
    ("GET", "/api/v1/customers", 401),
]

for method, path, expected in checks:
    response = client.request(method, path)
    if response.status_code != expected:
        raise SystemExit(f"FAIL: {method} {path}: expected {expected}, got {response.status_code}")
    print(f"PASS: {method} {path} -> {response.status_code}")

print("FastAPI smoke test PASSED.")
