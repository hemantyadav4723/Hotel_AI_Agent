from fastapi import APIRouter, Depends, HTTPException

from api.common import row_dict, rows_dict
from api.dependencies import get_current_user, require_permission
from api.schemas import FeedbackCreate, FeedbackUpdate, TransportationCreate, TransportationUpdate, VehicleCreate, DriverCreate, StatusUpdate
from database.database import get_connection
from database.feedback_db import save_feedback, update_feedback_record, get_guest_satisfaction_report, FEEDBACK_CATEGORIES, FEEDBACK_STATUSES, FOLLOW_UP_METHODS, FOLLOW_UP_STATUSES
from database.notification_db import get_notifications, search_notifications, mark_notification_read, get_notification_channels
from database.transportation_db import (
    create_transportation_request, get_transportation_requests, search_transportation_requests,
    add_vehicle, get_vehicles, update_vehicle_status, add_driver, get_drivers, update_driver_status,
    update_transportation_request,
)

router = APIRouter(tags=["Experience & Communication"])


@router.get("/feedback")
def feedback(
    user=Depends(require_permission("Customers", "View")), customer_id: str | None = None,
    search: str | None = None, category: str | None = None, rating: int | None = None,
    status: str | None = None, complaint_only: bool = False, follow_up_required: bool | None = None,
    follow_up_status: str | None = None, start_date: str | None = None, end_date: str | None = None,
    limit: int = 500
):
    connection = get_connection()
    try:
        sql = "SELECT * FROM feedback WHERE hotel_id = ?"
        params = [user["hotel_id"]]
        if customer_id:
            sql += " AND customer_id = ?"; params.append(customer_id.strip().upper())
        if search:
            like = f"%{search.strip()}%"
            sql += " AND (feedback_id LIKE ? OR customer_name LIKE ? OR customer_mobile LIKE ? OR feedback LIKE ? OR complaint LIKE ? OR issue LIKE ? OR resolution LIKE ?)"
            params.extend([like] * 7)
        if category:
            sql += " AND category = ?"; params.append(category)
        if rating is not None:
            sql += " AND rating = ?"; params.append(rating)
        if status:
            sql += " AND status = ?"; params.append(status)
        if complaint_only:
            sql += " AND complaint IS NOT NULL AND TRIM(complaint) <> ''"
        if follow_up_required is not None:
            sql += " AND follow_up_required = ?"; params.append(1 if follow_up_required else 0)
        if follow_up_status:
            sql += " AND follow_up_status = ?"; params.append(follow_up_status)
        date_expr = "substr(feedback_date,7,4)||'-'||substr(feedback_date,4,2)||'-'||substr(feedback_date,1,2)"
        if start_date:
            sql += f" AND {date_expr} >= ?"; params.append(start_date)
        if end_date:
            sql += f" AND {date_expr} <= ?"; params.append(end_date)
        sql += " ORDER BY feedback_date DESC, feedback_time DESC, feedback_id DESC LIMIT ?"
        params.append(max(1, min(limit, 1000)))
        rows = connection.execute(sql, params).fetchall()
    finally:
        connection.close()
    return {"data": rows_dict(rows)}


@router.get("/feedback/options")
def feedback_options(user=Depends(require_permission("Customers", "View"))):
    return {"data": {"categories": FEEDBACK_CATEGORIES, "statuses": FEEDBACK_STATUSES, "follow_up_methods": FOLLOW_UP_METHODS, "follow_up_statuses": FOLLOW_UP_STATUSES}}


@router.post("/feedback", status_code=201)
def create_feedback(payload: FeedbackCreate, user=Depends(require_permission("Customers", "Create"))):
    feedback_id = save_feedback(payload.feedback_id, payload.customer_name, payload.mobile, payload.rating, payload.review, payload.customer_id, payload.category, payload.complaint, allow_pending_complaint=payload.allow_pending_complaint, hotel_id=user["hotel_id"])
    return {"data": {"feedback_id": feedback_id}, "message": "Feedback recorded successfully."}


@router.patch("/feedback/{feedback_id}")
def update_feedback(feedback_id: str, payload: FeedbackUpdate, user=Depends(require_permission("Customers", "Update"))):
    try:
        updated = update_feedback_record(feedback_id, hotel_id=user["hotel_id"], **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not updated:
        raise HTTPException(status_code=404, detail="Feedback not found.")
    return {"message": "Feedback updated successfully."}


@router.get("/feedback/satisfaction")
def feedback_satisfaction(user=Depends(require_permission("Customers", "View"))):
    return {"data": row_dict(get_guest_satisfaction_report(user["hotel_id"]))}


@router.get("/notifications")
def notifications(
    user=Depends(require_permission("Reports", "View")),
    event_type: str | None = None, channel: str | None = None, status: str | None = None,
    unread_only: bool = False, limit: int = 100,
):
    try:
        rows = get_notifications(
            hotel_id=user["hotel_id"], event_type=event_type, channel=channel,
            status=status, unread_only=unread_only, limit=max(1, min(limit, 500))
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": rows_dict(rows)}


@router.get("/notifications/search")
def notification_search(term: str, user=Depends(require_permission("Reports", "View"))):
    return {"data": rows_dict(search_notifications(term, user["hotel_id"]))}


@router.get("/notifications/channels")
def notification_channels(user=Depends(require_permission("Reports", "View"))):
    return {"data": rows_dict(get_notification_channels(user["hotel_id"]))}


@router.post("/notifications/{delivery_id}/read")
def notification_read(delivery_id: str, user=Depends(require_permission("Reports", "Update"))):
    if not mark_notification_read(delivery_id, user["hotel_id"]):
        raise HTTPException(status_code=404, detail="Notification not found.")
    return {"message": "Notification marked as read."}


@router.get("/transportation/requests")
def transportation_requests(
    user=Depends(require_permission("Hotel", "View")), search: str | None = None, status: str | None = None,
    provider: str | None = None, integration_status: str | None = None, limit: int = 200,
):
    rows = search_transportation_requests(search) if search else get_transportation_requests(limit=max(1, min(limit, 500)))
    if status or provider or integration_status:
        rows = [r for r in rows if (not status or r["status"] == status) and
                (not provider or str(r["provider_name"] or "").lower() == provider.lower()) and
                (not integration_status or r["integration_status"] == integration_status)]
    return {"data": rows_dict(rows)}


@router.patch("/transportation/requests/{request_id}")
def transportation_request_update(request_id: str, payload: TransportationUpdate, user=Depends(require_permission("Hotel", "Update"))):
    data = payload.model_dump(exclude_none=True)
    if not data.get("status"):
        data["status"] = "Requested"
    try:
        update_transportation_request(request_id, **data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": "Transportation request updated."}


@router.post("/transportation/requests", status_code=201)
def transportation_request(payload: TransportationCreate, user=Depends(require_permission("Hotel", "Create"))):
    request_id = create_transportation_request(
        payload.customer_id, payload.guest_name, payload.guest_mobile, payload.guest_email,
        payload.transportation_type, payload.pickup_date.isoformat(), payload.pickup_time,
        payload.pickup_location, payload.drop_location, payload.vehicle_id, payload.vehicle_type,
        payload.driver_id, payload.fare, payload.special_request, payload.notes,
    )
    return {"data": {"request_id": request_id}, "message": "Transportation request created."}


@router.get("/transportation/vehicles")
def vehicles(user=Depends(require_permission("Hotel", "View"))):
    return {"data": rows_dict(get_vehicles())}


@router.post("/transportation/vehicles", status_code=201)
def vehicle(payload: VehicleCreate, user=Depends(require_permission("Hotel", "Create"))):
    return {"data": {"vehicle_id": add_vehicle(payload.vehicle_number, payload.vehicle_type, payload.capacity, payload.notes)}}


@router.get("/transportation/drivers")
def drivers(user=Depends(require_permission("Hotel", "View"))):
    return {"data": rows_dict(get_drivers())}


@router.post("/transportation/drivers", status_code=201)
def driver(payload: DriverCreate, user=Depends(require_permission("Hotel", "Create"))):
    return {"data": {"driver_id": add_driver(payload.driver_name, payload.driver_mobile, payload.license_number, payload.vehicle_type, payload.notes)}}


@router.patch("/transportation/vehicles/{vehicle_id}/status")
def vehicle_status(vehicle_id: str, payload: StatusUpdate, user=Depends(require_permission("Hotel", "Update"))):
    try:
        update_vehicle_status(vehicle_id, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": "Vehicle status updated."}


@router.patch("/transportation/drivers/{driver_id}/status")
def driver_status(driver_id: str, payload: StatusUpdate, user=Depends(require_permission("Hotel", "Update"))):
    try:
        update_driver_status(driver_id, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": "Driver status updated."}
