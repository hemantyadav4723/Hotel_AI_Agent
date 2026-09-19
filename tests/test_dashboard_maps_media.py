from pathlib import Path


def test_maps_media_dashboard_page_and_routes_present():
    root = Path(__file__).resolve().parents[1]
    app = (root / "dashboard" / "app.js").read_text(encoding="utf-8")
    hotel = (root / "api" / "routes" / "hotel.py").read_text(encoding="utf-8")
    assert '"mapsmedia"' in app
    for path in (
        '/hotel/maps/configuration',
        '/hotel/nearby-places',
        '/hotel/navigation-routes',
        '/hotel/media',
    ):
        assert path in hotel


def test_maps_media_schemas_are_strict_and_validatable():
    from api.schemas import MapConfigurationUpdate, MediaCreate, NearbyPlaceCreate, NavigationRouteCreate

    assert MapConfigurationUpdate(provider="Google Maps").default_zoom == 16
    assert NearbyPlaceCreate(place_name="Railway Station", category="Transport").place_name == "Railway Station"
    assert NavigationRouteCreate(origin="Hotel", destination="Station").destination == "Station"
    assert MediaCreate(media_type="Image", title="Lobby", file_url="https://example.com/lobby.jpg").guest_visible is True


def test_maps_media_route_module_imports_http_exception():
    import api.routes.hotel as hotel
    assert hotel.HTTPException is not None
