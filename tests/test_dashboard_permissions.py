from fastapi.testclient import TestClient
from api.app import app


def test_permission_endpoint_requires_authentication():
    client = TestClient(app)
    response = client.get('/api/v1/auth/permissions')
    assert response.status_code == 401


def test_admin_permission_endpoint_exists():
    client = TestClient(app)
    for path in ('/api/v1/admin/roles', '/api/v1/admin/permissions'):
        assert client.get(path).status_code == 401


def test_dashboard_permission_guard_present():
    client = TestClient(app)
    js = client.get('/dashboard/app.js').text
    assert 'hasPermission' in js
    assert 'isActionAllowed' in js
    assert 'Access Restricted' in js
    assert 'FastAPI backend remains the final authorization boundary' in js


def test_dashboard_permission_mapping_is_module_action_exact():
    client = TestClient(app)
    js = client.get('/dashboard/app.js').text
    assert 'permissionPairs()' in js
    assert 'p.module===moduleKey&&p.action===actionKey' in js
    assert 'customer:["Customers","Create"]' in js
    assert 'booking:["Rooms","Create"]' in js
    assert 'order:["Restaurant","Create"]' in js
    assert 'expense:["Expenses","Create"]' in js


def test_dashboard_module_permissions_are_explicit():
    client = TestClient(app)
    js = client.get('/dashboard/app.js').text
    assert 'procurement:null' in js
    assert 'transport:["Hotel","View"]' in js
    assert 'feedback:["Customers","View"]' in js
    assert 'notifications:["Reports","View"]' in js
    assert 'return isAdmin()' in js


def test_dashboard_permission_helpers_have_single_definitions_and_strict_nav_guard():
    client = TestClient(app)
    js = client.get('/dashboard/app.js').text
    assert js.count('function showAccessDenied(') == 1
    assert js.count('function buildNav(') == 1
    assert 'group.items.filter(([id])=>canOpenPage(id))' in js
    assert 'group.items.filter(([id])=>hasPermission(id))' not in js
