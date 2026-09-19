from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from api.common import row_dict, rows_dict
from api.dependencies import get_current_user, require_permission
from api.schemas import CustomerCreate, CustomerUpdate
from database.customer_db import (
    get_customer_by_id, search_customers, get_hotel_guests,
    get_guest_stay_summary, get_guest_booking_summary, get_guest_restaurant_summary,
    get_customer_lifecycle, get_guest_booking_history, get_guest_restaurant_history,
    get_guest_hotels, save_customer, update_customer_record, get_next_customer_id,
    ensure_guest_hotel_relationship, validate_guest_hotel_relationship,
)
from database.database import get_connection

router = APIRouter(tags=["Guests"])


@router.get("/customers")
def list_customers(search: str | None = None, search_field: str = "all", guest_status: str | None = None, user=Depends(get_current_user)):
    if search or guest_status:
        rows = search_customers(search, search_field, guest_status, hotel_id=user["hotel_id"])
    else:
        rows = get_hotel_guests(user["hotel_id"])
    return {"data": rows_dict(rows)}


@router.get("/customers/{customer_id}")
def customer_detail(customer_id: str, user=Depends(get_current_user)):
    cid = customer_id.strip().upper()
    customer = get_customer_by_id(cid)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found.")
    try:
        validate_guest_hotel_relationship(cid, user["hotel_id"])
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    connection = get_connection()
    try:
        feedback_rows = connection.execute(
            "SELECT * FROM feedback WHERE customer_id=? AND hotel_id=? ORDER BY feedback_date DESC, feedback_time DESC, feedback_id DESC",
            (cid, user["hotel_id"]),
        ).fetchall()
    finally:
        connection.close()
    return {"data": {
        "customer": row_dict(customer),
        "stay_summary": get_guest_stay_summary(cid, user["hotel_id"]),
        "booking_summary": get_guest_booking_summary(cid, user["hotel_id"]),
        "restaurant_summary": get_guest_restaurant_summary(cid, user["hotel_id"]),
        "lifecycle": get_customer_lifecycle(cid, user["hotel_id"]),
        "booking_history": rows_dict(get_guest_booking_history(cid, user["hotel_id"])),
        "order_history": rows_dict(get_guest_restaurant_history(cid, user["hotel_id"])),
        "feedback_history": rows_dict(feedback_rows),
        "hotel_relationships": rows_dict(get_guest_hotels(cid)),
    }}


@router.post("/customers", status_code=201)
def create_customer(payload: CustomerCreate, user=Depends(require_permission("Customers", "Create"))):
    customer_id = payload.customer_id or get_next_customer_id()
    save_customer(customer_id, payload.customer_name, payload.customer_mobile, payload.customer_email, payload.customer_address, datetime.now(), payload.customer_city, payload.customer_state, payload.customer_country, payload.customer_pincode, payload.guest_status, 1, payload.preferences, payload.special_requests, payload.guest_notes)
    try:
        ensure_guest_hotel_relationship(customer_id, user["hotel_id"])
    except Exception:
        raise
    return {"data": row_dict(get_customer_by_id(customer_id)), "message": "Customer created successfully."}


@router.put("/customers/{customer_id}")
def update_customer(customer_id: str, payload: CustomerUpdate, user=Depends(require_permission("Customers", "Update"))):
    update_customer_record(customer_id, payload.customer_name, payload.customer_mobile, payload.customer_email, payload.customer_address, payload.customer_city, payload.customer_state, payload.customer_country, payload.customer_pincode, payload.guest_status, payload.is_active, payload.preferences, payload.special_requests, payload.guest_notes, user["hotel_id"])
    return {"data": row_dict(get_customer_by_id(customer_id)), "message": "Customer updated successfully."}
