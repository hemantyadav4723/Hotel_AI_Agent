from fastapi import APIRouter, Depends, HTTPException

from api.common import row_dict, rows_dict
from api.dependencies import get_current_user, require_permission
from database.database import get_connection
from database.hotel_information_db import get_hotel_information
from database.maps_navigation_db import get_map_configuration, get_hotel_map_url, get_nearby_places, get_navigation_routes
from database.media_db import get_media_items
from api.schemas import MapConfigurationUpdate, NearbyPlaceCreate, NearbyPlaceStatusUpdate, NavigationRouteCreate, MediaCreate, StatusUpdate
from database.maps_navigation_db import save_map_configuration, add_nearby_place, set_nearby_place_status, create_navigation_route
from database.media_db import MEDIA_CATEGORIES, MEDIA_TYPES, SOURCE_TYPES, add_media, update_media, set_media_status, delete_media, search_media

router = APIRouter(tags=["Hotel"])


@router.get("/hotel/profile")
def hotel_profile(user=Depends(get_current_user)):
    return {"data": row_dict(get_hotel_information())}


@router.get("/hotel/context")
def hotel_context(user=Depends(get_current_user)):
    connection = get_connection()
    try:
        row = connection.execute("SELECT * FROM hotels WHERE hotel_id = ? AND is_active = 1", (user["hotel_id"],)).fetchone()
    finally:
        connection.close()
    return {"data": row_dict(row)}


@router.get("/hotel/maps")
def maps(user=Depends(get_current_user)):
    return {"data": {"configuration": row_dict(get_map_configuration(user["hotel_id"])), "map_url": get_hotel_map_url(user["hotel_id"])}}


@router.get("/hotel/nearby-places")
def nearby_places(user=Depends(get_current_user), category: str | None = None):
    return {"data": rows_dict(get_nearby_places(category=category, hotel_id=user["hotel_id"]))}


@router.get("/hotel/navigation-routes")
def navigation_routes(user=Depends(get_current_user), limit: int = 50):
    return {"data": rows_dict(get_navigation_routes(user["hotel_id"], limit=max(1, min(limit, 200))))}


@router.get("/hotel/media")
def hotel_media(user=Depends(get_current_user), category: str | None = None, guest_visible_only: bool = False):
    return {"data": rows_dict(get_media_items(category=category, active_only=True, guest_visible_only=guest_visible_only, hotel_id=user["hotel_id"]))}



@router.put("/hotel/maps/configuration")
def update_maps_configuration(payload: MapConfigurationUpdate, user=Depends(require_permission("Hotel", "Update"))):
    try:
        row = save_map_configuration(
            payload.provider, payload.latitude, payload.longitude, payload.default_zoom,
            payload.api_enabled, payload.integration_status, hotel_id=user["hotel_id"]
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": row_dict(row), "message": "Map configuration updated."}


@router.post("/hotel/nearby-places", status_code=201)
def create_nearby_place(payload: NearbyPlaceCreate, user=Depends(require_permission("Hotel", "Create"))):
    try:
        place_id = add_nearby_place(**payload.model_dump(), hotel_id=user["hotel_id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": {"place_id": place_id}, "message": "Nearby place created."}


@router.patch("/hotel/nearby-places/{place_id}/status")
def nearby_place_status(place_id: int, payload: NearbyPlaceStatusUpdate, user=Depends(require_permission("Hotel", "Update"))):
    try:
        set_nearby_place_status(place_id, payload.is_active, hotel_id=user["hotel_id"])
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"message": "Nearby place status updated."}


@router.post("/hotel/navigation-routes", status_code=201)
def create_route(payload: NavigationRouteCreate, user=Depends(require_permission("Hotel", "Create"))):
    try:
        route_id, directions_url = create_navigation_route(**payload.model_dump(), hotel_id=user["hotel_id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": {"route_id": route_id, "directions_url": directions_url}, "message": "Navigation route created."}


@router.get("/hotel/media/search")
def search_hotel_media(term: str = "", category: str | None = None, user=Depends(require_permission("Hotel", "View"))):
    try:
        rows = search_media(term, category, hotel_id=user["hotel_id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": rows_dict(rows)}


@router.post("/hotel/media", status_code=201)
def create_hotel_media(payload: MediaCreate, user=Depends(require_permission("Hotel", "Create"))):
    try:
        media_id = add_media(
            payload.category, payload.media_type, payload.title, payload.description or "",
            payload.file_url, "URL", "", max(1, payload.display_order), payload.guest_visible,
            hotel_id=user["hotel_id"]
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": {"media_id": media_id}, "message": "Media added."}


@router.put("/hotel/media/{media_id}")
def update_hotel_media(media_id: str, payload: MediaCreate, user=Depends(require_permission("Hotel", "Update"))):
    try:
        update_media(
            media_id, payload.category, payload.media_type, payload.title, payload.description or "",
            payload.file_url, "URL", "", max(1, payload.display_order), payload.guest_visible, hotel_id=user["hotel_id"]
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"message": "Media updated."}


@router.patch("/hotel/media/{media_id}/status")
def hotel_media_status(media_id: str, payload: StatusUpdate, user=Depends(require_permission("Hotel", "Update"))):
    status = str(payload.status).strip().lower()
    if status not in {"active", "inactive"}:
        raise HTTPException(status_code=400, detail="Status must be Active or Inactive.")
    try:
        set_media_status(media_id, status == "active", hotel_id=user["hotel_id"])
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"message": "Media status updated."}

@router.get("/hotel/settings")
def hotel_settings(user=Depends(get_current_user)):
    connection = get_connection()
    try:
        rows = connection.execute("SELECT * FROM settings ORDER BY id").fetchall()
    finally:
        connection.close()
    return {"data": rows_dict(rows)}
