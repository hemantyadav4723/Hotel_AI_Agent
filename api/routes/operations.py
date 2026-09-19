from datetime import datetime, time

from fastapi import APIRouter, Depends, HTTPException, Query

from api.common import row_dict, rows_dict
from api.dependencies import get_current_user, require_permission
from api.schemas import (RoomBookingCreate, ReservationModify, StayOptionsUpdate, CancellationRequest, NoShowRequest, TransferRoomRequest, RestaurantOrderCreate, TableBookingCreate, StatusUpdate)
from database.room_booking_db import (get_all_rooms, get_room_by_number, get_available_rooms_for_dates, get_room_booking_by_id, save_and_book_room, update_booking_status, modify_reservation, cancel_reservation, mark_booking_no_show, transfer_room, confirm_reservation, check_in_guest, check_out_guest, update_stay_options, get_reservation_rooms)
from database.order_db import get_orders, get_order, update_order_status, save_order, get_restaurant_operational_orders
from database.restaurant_menu_db import get_menu_items, get_menu_item
from database.table_booking_db import get_all_tables, get_available_restaurant_tables, create_table_booking

router = APIRouter(tags=["Operations"])


@router.get("/rooms")
def rooms(user=Depends(get_current_user), active_only: bool = True):
    rows = get_all_rooms()
    if active_only:
        rows = [r for r in rows if int(r["is_active"]) == 1]
    return {"data": rows_dict(rows)}


@router.get("/rooms/availability")
def room_availability(check_in_date: str, nights: int = Query(1, ge=1, le=365), user=Depends(get_current_user)):
    from datetime import datetime as _dt
    try:
        normalized_date = _dt.strptime(check_in_date, "%Y-%m-%d").strftime("%d-%m-%Y")
    except ValueError:
        normalized_date = check_in_date
    return {"data": rows_dict(get_available_rooms_for_dates(normalized_date, nights))}


@router.get("/rooms/{room_number}")
def room_detail(room_number: str, user=Depends(get_current_user)):
    row = get_room_by_number(room_number)
    if row is None:
        raise HTTPException(status_code=404, detail="Room not found.")
    return {"data": row_dict(row)}


@router.post("/room-bookings", status_code=201)
def create_room_booking(payload: RoomBookingCreate, user=Depends(require_permission("Rooms", "Create"))):
    booking_id = payload.booking_id or datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
    check_in = payload.check_in_date.isoformat() if payload.check_in_date else datetime.now().strftime("%d-%m-%Y")
    room = get_room_by_number(payload.room_number)
    if room is None:
        raise HTTPException(status_code=400, detail="Invalid room number.")
    total = float(room["room_price"]) * payload.days
    gst = round(total * 0.05, 2)
    grand_total = round(total + gst, 2)
    save_and_book_room(
        booking_id, datetime.now(), payload.customer_name, payload.customer_mobile,
        payload.room_number, room["room_type"], room["room_price"], payload.days,
        total, gst, grand_total, check_in, payload.advance_amount, payload.payment_method,
        payload.notes, payload.booking_status, payload.adults, payload.children,
        payload.customer_id, payload.customer_email, payload.customer_address,
    )
    return {"data": row_dict(get_room_booking_by_id(booking_id)), "message": "Room booking created successfully."}


def _frontdesk_date(value):
    if not value:
        return None
    value = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value[:10], fmt).date()
        except ValueError:
            continue
    return None


def _frontdesk_rows(hotel_id, search=None):
    connection = __import__("database.database", fromlist=["get_connection"]).get_connection()
    try:
        sql = "SELECT * FROM room_bookings WHERE hotel_id = ?"
        params = [hotel_id]
        if search:
            term = f"%{search.strip()}%"
            sql += " AND (booking_id LIKE ? OR customer_id LIKE ? OR customer_name LIKE ? OR customer_mobile LIKE ? OR room_number LIKE ?)"
            params.extend([term] * 5)
        sql += " ORDER BY created_at DESC LIMIT 500"
        return connection.execute(sql, params).fetchall()
    finally:
        connection.close()


@router.get("/frontdesk")
def frontdesk_summary(user=Depends(get_current_user), search: str | None = None):
    today = datetime.now().date()
    bookings = list(_frontdesk_rows(user["hotel_id"], search))
    arrivals = []
    departures = []
    current_guests = []
    pending_checkins = []
    pending_checkouts = []
    for row in bookings:
        status = str(row["booking_status"] or "").strip().lower()
        check_in = _frontdesk_date(row["check_in_date"])
        expected_out = _frontdesk_date(row["expected_check_out"])
        if check_in == today and status not in {"cancelled", "no-show", "checked out", "checked_out"}:
            arrivals.append(row)
        if expected_out == today and status not in {"cancelled", "no-show", "checked out", "checked_out"}:
            departures.append(row)
        if status in {"checked-in", "checked in", "occupied"}:
            current_guests.append(row)
        if check_in == today and status in {"pending", "confirmed"}:
            pending_checkins.append(row)
        if expected_out == today and status in {"checked-in", "checked in", "occupied"}:
            pending_checkouts.append(row)
    rooms = list(get_all_rooms())
    available = [r for r in rooms if str(r["room_status"]).strip().lower() == "available"]
    occupied = [r for r in rooms if str(r["room_status"]).strip().lower() == "occupied"]
    return {
        "data": {
            "date": today.isoformat(),
            "arrivals": rows_dict(arrivals),
            "departures": rows_dict(departures),
            "current_guests": rows_dict(current_guests),
            "pending_checkins": rows_dict(pending_checkins),
            "pending_checkouts": rows_dict(pending_checkouts),
            "available_rooms": rows_dict(available),
            "occupied_rooms": rows_dict(occupied),
            "reservation_results": rows_dict(bookings),
        }
    }


@router.get("/frontdesk/guest-lookup")
def frontdesk_guest_lookup(q: str = Query(..., min_length=1, max_length=100), user=Depends(get_current_user)):
    term = f"%{q.strip()}%"
    connection = __import__("database.database", fromlist=["get_connection"]).get_connection()
    try:
        rows = connection.execute(
            """SELECT * FROM room_bookings
               WHERE hotel_id = ?
               AND (customer_id LIKE ? OR customer_name LIKE ? OR customer_mobile LIKE ?)
               ORDER BY created_at DESC LIMIT 50""",
            (user["hotel_id"], term, term, term),
        ).fetchall()
    finally:
        connection.close()
    return {"data": rows_dict(rows)}


@router.get("/room-bookings")
def room_bookings(user=Depends(get_current_user), booking_id: str | None = None, status: str | None = None):
    connection = __import__("database.database", fromlist=["get_connection"]).get_connection()
    try:
        if booking_id:
            row = get_room_booking_by_id(booking_id.strip().upper())
            if row is None:
                raise HTTPException(status_code=404, detail="Room booking not found.")
            return {"data": row_dict(row), "rooms": rows_dict(get_reservation_rooms(booking_id.strip().upper()))}
        sql = "SELECT * FROM room_bookings WHERE hotel_id = ?"
        params = [user["hotel_id"]]
        if status:
            sql += " AND booking_status = ?"; params.append(status)
        sql += " ORDER BY created_at DESC LIMIT 500"
        rows = connection.execute(sql, params).fetchall()
    finally:
        connection.close()
    return {"data": rows_dict(rows)}


@router.patch("/room-bookings/{booking_id}")
def modify_room_reservation(booking_id: str, payload: ReservationModify, user=Depends(require_permission("Rooms", "Update"))):
    bid = booking_id.strip().upper()
    try:
        modify_reservation(bid, payload.customer_name, payload.customer_mobile, payload.room_number, payload.check_in_date, payload.nights, payload.notes, None, None, payload.adults, payload.children)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"data": row_dict(get_room_booking_by_id(bid)), "message": "Reservation modified successfully."}


@router.post("/room-bookings/{booking_id}/confirm")
def confirm_room_reservation(booking_id: str, user=Depends(require_permission("Rooms", "Update"))):
    bid = booking_id.strip().upper()
    try: confirm_reservation(bid)
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc))
    return {"data": row_dict(get_room_booking_by_id(bid)), "message": "Reservation confirmed."}


@router.post("/room-bookings/{booking_id}/cancel")
def cancel_room_reservation(booking_id: str, payload: CancellationRequest, user=Depends(require_permission("Rooms", "Cancel"))):
    bid = booking_id.strip().upper()
    try: cancel_reservation(bid, payload.reason)
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc))
    return {"data": row_dict(get_room_booking_by_id(bid)), "message": "Reservation cancelled."}


@router.post("/room-bookings/{booking_id}/no-show")
def no_show_room_reservation(booking_id: str, payload: NoShowRequest, user=Depends(require_permission("Rooms", "Update"))):
    bid = booking_id.strip().upper()
    try: mark_booking_no_show(bid, payload.reason)
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc))
    return {"data": row_dict(get_room_booking_by_id(bid)), "message": "Reservation marked No-Show."}


@router.post("/room-bookings/{booking_id}/check-in")
def check_in_room_reservation(booking_id: str, user=Depends(require_permission("Rooms", "Update"))):
    bid = booking_id.strip().upper()
    try: check_in_guest(bid)
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc))
    return {"data": row_dict(get_room_booking_by_id(bid)), "message": "Guest checked in."}


@router.post("/room-bookings/{booking_id}/check-out")
def check_out_room_reservation(booking_id: str, user=Depends(require_permission("Rooms", "Update"))):
    bid = booking_id.strip().upper()
    try: check_out_guest(bid)
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc))
    return {"data": row_dict(get_room_booking_by_id(bid)), "message": "Guest checked out."}


@router.post("/room-bookings/{booking_id}/transfer")
def transfer_room_reservation(booking_id: str, payload: TransferRoomRequest, user=Depends(require_permission("Rooms", "Update"))):
    bid = booking_id.strip().upper(); new_room = payload.new_room_number.strip()
    try: transfer_room(bid, new_room)
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc))
    return {"data": row_dict(get_room_booking_by_id(bid)), "message": "Room transferred successfully."}


@router.patch("/room-bookings/{booking_id}/stay-options")
def update_room_stay_options(booking_id: str, payload: StayOptionsUpdate, user=Depends(require_permission("Rooms", "Update"))):
    bid = booking_id.strip().upper()
    try: update_stay_options(bid, payload.early_check_in_time, payload.late_check_out_time)
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc))
    return {"data": row_dict(get_room_booking_by_id(bid)), "message": "Early check-in / late check-out options updated."}


@router.patch("/room-bookings/{booking_id}/status")
def room_booking_status(booking_id: str, payload: StatusUpdate, user=Depends(require_permission("Rooms", "Update"))):
    try: update_booking_status(booking_id.strip().upper(), payload.status)
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc))
    return {"data": row_dict(get_room_booking_by_id(booking_id.strip().upper())), "message": "Room booking status updated."}


@router.get("/restaurant/menu")
def restaurant_menu(user=Depends(get_current_user), available_only: bool = True):
    return {"data": rows_dict(get_menu_items(available_only=available_only, hotel_id=user["hotel_id"]))}


@router.get("/restaurant/menu/{item_id}")
def restaurant_menu_item(item_id: str, user=Depends(get_current_user)):
    row = get_menu_item(item_id.strip().upper(), user["hotel_id"])
    if row is None:
        raise HTTPException(status_code=404, detail="Menu item not found.")
    return {"data": row_dict(row)}


@router.get("/restaurant/orders")
def restaurant_orders(user=Depends(get_current_user), status: str | None = None, search: str | None = None):
    if status:
        rows = list(get_restaurant_operational_orders(status=status, hotel_id=user["hotel_id"]))
    else:
        rows = list(get_orders(user["hotel_id"]))
    if search:
        term = search.strip().lower()
        rows = [r for r in rows if term in str(r["order_id"] or "").lower() or term in str(r["customer_name"] or "").lower() or term in str(r["customer_mobile"] or "").lower() or term in str(r["table_number"] or "").lower()]
    return {"data": rows_dict(rows[:500])}


@router.get("/restaurant/orders/{order_id}")
def restaurant_order(order_id: str, user=Depends(get_current_user)):
    row = get_order(order_id.strip().upper(), user["hotel_id"])
    if row is None:
        raise HTTPException(status_code=404, detail="Restaurant order not found.")
    return {"data": row_dict(row)}


@router.post("/restaurant/orders", status_code=201)
def create_restaurant_order(payload: RestaurantOrderCreate, user=Depends(require_permission("Restaurant", "Create"))):
    cart = []
    for requested in payload.items:
        item = get_menu_item(requested.item_id.strip().upper(), user["hotel_id"])
        if item is None or not item["is_available"]:
            raise HTTPException(status_code=400, detail=f"Menu item {requested.item_id} is unavailable.")
        price = float(item["price"])
        cart.append({"item_id": item["item_id"], "name": item["item_name"], "price": price, "quantity": requested.quantity, "subtotal": round(price * requested.quantity, 2)})
    subtotal = round(sum(i["subtotal"] for i in cart), 2)
    taxable = round(subtotal - payload.discount, 2)
    gst = round(taxable * 0.05, 2)
    grand_total = round(taxable + gst, 2)
    order_id = payload.order_id or datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
    save_order(cart, order_id, datetime.now(), payload.customer_name, payload.customer_mobile, payload.table_number, subtotal, gst, grand_total, payload.customer_id, payload.discount, user["hotel_id"], payload.order_notes, payload.payment_method, payload.paid_amount, 0, payload.advance_amount)
    return {"data": row_dict(get_order(order_id, user["hotel_id"])), "message": "Restaurant order created successfully."}


@router.patch("/restaurant/orders/{order_id}/status")
def restaurant_order_status(order_id: str, payload: StatusUpdate, user=Depends(require_permission("Restaurant", "Update"))):
    update_order_status(order_id.strip().upper(), payload.status, user["hotel_id"])
    return {"data": row_dict(get_order(order_id.strip().upper(), user["hotel_id"])), "message": "Restaurant order status updated."}


@router.get("/table-bookings")
def table_bookings(user=Depends(get_current_user), search: str | None = None):
    connection = __import__("database.database", fromlist=["get_connection"]).get_connection()
    try:
        sql = "SELECT * FROM table_bookings WHERE hotel_id = ?"
        params = [user["hotel_id"]]
        if search:
            term = f"%{search.strip()}%"
            sql += " AND (booking_id LIKE ? OR customer_name LIKE ? OR customer_mobile LIKE ? OR table_number LIKE ?)"
            params.extend([term] * 4)
        sql += " ORDER BY booking_date DESC, booking_time DESC LIMIT 500"
        rows = connection.execute(sql, params).fetchall()
    finally:
        connection.close()
    return {"data": rows_dict(rows)}


@router.get("/restaurant/dashboard")
def restaurant_dashboard(user=Depends(get_current_user)):
    hotel_id = user["hotel_id"]
    orders = list(get_orders(hotel_id))
    menu = list(get_menu_items(available_only=False, hotel_id=hotel_id))
    tables = list(get_all_tables(hotel_id))
    today = datetime.now().date().isoformat()
    todays = [o for o in orders if str(o["order_date"] or "")[:10] == today and str(o["order_status"] or "").lower() != "cancelled"]
    revenue = round(sum(float(o["grand_total"] or 0) for o in todays), 2)
    pending_payment = round(sum(max(0.0, float(o["balance_amount"] or 0)) for o in todays if str(o["payment_status"] or "").lower() not in {"paid", "settled"}), 2)
    kitchen = [o for o in todays if str(o["order_status"] or "New") in {"New", "Preparing", "Ready", "Served"}]
    connection = __import__("database.database", fromlist=["get_connection"]).get_connection()
    try:
        table_rows = connection.execute("SELECT * FROM table_bookings WHERE hotel_id = ? ORDER BY booking_date DESC, booking_time DESC LIMIT 200", (hotel_id,)).fetchall()
    finally:
        connection.close()
    return {"data": {"date": today, "overview": {"menu_items": len(menu), "orders_today": len(todays), "revenue_today": revenue, "pending_payments": pending_payment, "tables": len(tables), "available_tables": sum(1 for t in tables if str(t["table_status"] or "").lower() == "available"), "occupied_tables": sum(1 for t in tables if str(t["table_status"] or "").lower() == "occupied")}, "menu": rows_dict(menu), "orders": rows_dict(todays), "kitchen_orders": rows_dict(kitchen), "tables": rows_dict(tables), "table_bookings": rows_dict(table_rows)}}


@router.get("/tables")
def tables(user=Depends(get_current_user)):
    return {"data": rows_dict(get_all_tables(user["hotel_id"]))}


@router.get("/tables/availability")
def table_availability(min_capacity: int | None = Query(None, ge=1, le=100), user=Depends(get_current_user)):
    return {"data": rows_dict(get_available_restaurant_tables(min_capacity, user["hotel_id"]))}


@router.post("/table-bookings", status_code=201)
def create_table_reservation(payload: TableBookingCreate, user=Depends(require_permission("Tables", "Create"))):
    booking_id = payload.booking_id or datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
    booking_dt = datetime.combine(payload.booking_date or datetime.now().date(), time.fromisoformat(payload.booking_time))
    create_table_booking(booking_id, booking_dt, payload.customer_id, payload.customer_name, payload.customer_mobile, payload.table_number, payload.persons)
    connection = __import__("database.database", fromlist=["get_connection"]).get_connection()
    try:
        row = connection.execute("SELECT * FROM table_bookings WHERE booking_id = ? AND hotel_id = ?", (booking_id, user["hotel_id"])).fetchone()
    finally:
        connection.close()
    return {"data": row_dict(row), "message": "Table booking created successfully."}
