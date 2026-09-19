from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_guest_api_supports_hotel_scope_filters_and_update():
    route = read("api/routes/guests.py")
    assert '"/customers"' in route
    assert 'search_field: str = "all"' in route
    assert 'guest_status: str | None = None' in route
    assert 'get_hotel_guests(user["hotel_id"])' in route
    assert 'hotel_id=user["hotel_id"]' in route
    assert '@router.put("/customers/{customer_id}")' in route
    assert 'require_permission("Customers", "Update")' in route


def test_guest_detail_exposes_required_history_sources():
    route = read("api/routes/guests.py")
    for key in ("booking_history", "order_history", "feedback_history", "hotel_relationships", "lifecycle"):
        assert f'"{key}"' in route


def test_customer_update_model_contains_guest_profile_fields():
    schemas = read("api/schemas.py")
    start = schemas.index("class CustomerUpdate")
    end = schemas.index("class RoomBookingCreate")
    block = schemas[start:end]
    for field in ("customer_name", "customer_mobile", "customer_email", "customer_address", "customer_city", "customer_state", "customer_country", "customer_pincode", "guest_status", "preferences", "special_requests", "guest_notes"):
        assert field in block


def test_dashboard_guest_page_has_search_filters_history_and_edit():
    app = read("dashboard/app.js")
    start = app.index("async function guests()")
    end = app.index("async function rooms()")
    block = app[start:end]
    for marker in ("guest-search", "guest-search-field", "guest-status-filter", "data-guest-detail", "data-guest-edit", "async function guestDetail", "Booking History", "Order History", "Feedback History"):
        assert marker in block
    assert 'guest_update:["Customers","Update"]' in app


def test_guest_update_db_function_enforces_hotel_relationship_and_unique_mobile():
    db = read("database/customer_db.py")
    start = db.index("def update_customer_record")
    block = db[start:db.index("def _normalize_customer_id", start)]
    assert "guest_hotel_relationships" in block
    assert "customer_mobile" in block
    assert "Mobile number already belongs" in block
