from fastapi.testclient import TestClient
from api.app import app


def test_transportation_routes_require_authentication():
    client = TestClient(app)
    for path in (
        '/api/v1/transportation/requests',
        '/api/v1/transportation/vehicles',
        '/api/v1/transportation/drivers',
    ):
        assert client.get(path).status_code == 401


def test_transportation_mutations_require_authentication():
    client = TestClient(app)
    assert client.patch('/api/v1/transportation/requests/TRN-TEST', json={'status': 'Confirmed'}).status_code == 401
    assert client.patch('/api/v1/transportation/vehicles/VEH-TEST/status', json={'status': 'Inactive'}).status_code == 401
    assert client.patch('/api/v1/transportation/drivers/DRV-TEST/status', json={'status': 'Inactive'}).status_code == 401


def test_transportation_dashboard_scope_and_actions_present():
    client = TestClient(app)
    js = client.get('/dashboard/app.js').text
    assert 'transport:["Hotel","View"]' in js
    assert 'transport:["Hotel","Create"]' in js
    assert 'transport_update:["Hotel","Update"]' in js
    for marker in ('Requests / History', 'Vehicles', 'Drivers', 'Provider', 'Integration Status', 'Pickup location', 'drop_location'):
        assert marker in js
