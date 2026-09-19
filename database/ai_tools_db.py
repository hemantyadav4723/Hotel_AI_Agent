"""AI business-tool registry and safe hotel-scoped read adapters.

The AI layer never receives arbitrary SQL or direct database access. Registered
read tools validate their contract, permission, and authenticated hotel scope,
then delegate to existing business/database functions.
"""

from datetime import datetime
import json
from contextvars import ContextVar

from database.database import get_connection
from database.hotel_context import get_current_hotel_id
from database.permission_db import has_permission

TOOL_VERSION = "1.1"
_AI_TOOL_USER: ContextVar[object | None] = ContextVar("ai_tool_user", default=None)


def _hotel_id(hotel_id=None):
    current = get_current_hotel_id()
    if hotel_id is None:
        return int(current)
    hotel_id = int(hotel_id)
    if hotel_id != int(current):
        raise PermissionError("AI tool hotel scope mismatch.")
    return hotel_id


def _row_to_dict(row):
    if row is None:
        return None
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    if isinstance(row, dict):
        return dict(row)
    return row


def _rows_to_dicts(rows):
    return [_row_to_dict(row) for row in rows]


def _json_safe(value):
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _clean_args(args):
    if args is None:
        return {}
    if not isinstance(args, dict):
        raise ValueError("Tool arguments must be a JSON object.")
    return dict(args)


# All tools in 8.2 are intentionally read-only. Mutation/action tools are
# introduced later after the agent and confirmation/guardrail layers exist.
_TOOL_SPECS = [
    ("hotel_information", "Get structured hotel master information for the active hotel.", "hotel", "Hotel", [], [], True),
    ("guest_information", "Get guest profile and available stay/lifecycle context.", "guest", "Customers", ["customer_id"], [], True),
    ("room_availability", "Get room master information or availability for a date range.", "rooms", "Rooms", [], ["room_number", "check_in_date", "nights"], True),
    ("room_booking_information", "Get a structured room reservation by booking ID.", "booking", "Rooms", ["booking_id"], [], True),
    ("table_information", "Get restaurant table information or available tables.", "tables", "Tables", [], ["min_capacity", "status"], True),
    ("restaurant_information", "Get restaurant order information or operational summary.", "restaurant", "Restaurant", [], ["order_id"], True),
    ("billing_information", "Get invoice/payment information by invoice ID.", "billing", "Reports", [], ["invoice_id"], True),
    ("inventory_information", "Get inventory, low-stock, or valuation information.", "inventory", "Inventory", [], ["item_id", "low_stock_only"], True),
    ("staff_information", "Get active-hotel staff information.", "staff", "Staff", [], ["staff_id", "status"], True),
    ("expense_information", "Get expense records and totals.", "expense", "Expenses", [], ["start_date", "end_date", "expense_id"], True),
    ("feedback_information", "Get guest feedback, complaint, resolution and satisfaction context.", "feedback", "Customers", [], ["feedback_id", "customer_id"], True),
    ("notification_information", "Get hotel notification events and delivery status.", "notifications", "Settings", [], ["event_id", "status"], True),
    ("transportation_information", "Get transportation requests, vehicles, and drivers.", "transportation", "Hotel", [], ["request_id"], True),
    ("maps_information", "Get hotel map configuration, nearby places, and routes.", "maps", "Hotel", [], ["category"], True),
    ("media_information", "Get hotel media/gallery records.", "media", "Hotel", [], ["media_id", "category", "active_only"], True),
    ("reports_summary", "Get structured revenue and operational analytics.", "reports", "Reports", [], ["start_date", "end_date"], True),
    ("audit_information", "Get hotel-scoped audit/activity history.", "audit", "Reports", [], ["search", "module", "action", "record_id", "request_id", "status", "limit"], True),
]


def get_tool_registry():
    return [
        {
            "name": name,
            "description": description,
            "category": category,
            "read_only": read_only,
            "required_arguments": required,
            "optional_arguments": optional,
            "permission": {"module": module, "action": "View"},
            "hotel_scoped": True,
            "version": TOOL_VERSION,
        }
        for name, description, category, module, required, optional, read_only in _TOOL_SPECS
    ]


def get_tool_definition(tool_name):
    tool_name = str(tool_name or "").strip().lower()
    for tool in get_tool_registry():
        if tool["name"] == tool_name:
            return tool
    return None


def _hotel_information(args):
    from database.hotel_information_db import get_hotel_information
    return {"hotel": _row_to_dict(get_hotel_information())}


def _guest_information(args):
    from database.customer_db import get_customer_by_id, get_guest_stay_summary, get_guest_booking_summary, get_guest_restaurant_summary, get_customer_lifecycle
    cid = str(args["customer_id"]).strip().upper()
    hotel_id = _hotel_id()
    customer = get_customer_by_id(cid)
    if customer is None:
        return {"customer": None}
    return {"customer": _row_to_dict(customer), "stay_summary": _json_safe(get_guest_stay_summary(cid, hotel_id)), "booking_summary": _json_safe(get_guest_booking_summary(cid, hotel_id)), "restaurant_summary": _json_safe(get_guest_restaurant_summary(cid, hotel_id)), "lifecycle": _json_safe(get_customer_lifecycle(cid, hotel_id))}


def _room_availability(args):
    from database.room_booking_db import get_all_rooms, get_room_by_number, get_available_rooms_for_dates
    room_number = str(args.get("room_number") or "").strip()
    check_in = str(args.get("check_in_date") or "").strip()
    if room_number:
        return {"room": _row_to_dict(get_room_by_number(room_number))}
    if check_in:
        try:
            nights = int(args.get("nights"))
        except (TypeError, ValueError) as exc:
            raise ValueError("nights must be a whole number when check_in_date is provided.") from exc
        if nights <= 0:
            raise ValueError("nights must be greater than zero.")
        return {"check_in_date": check_in, "nights": nights, "available_rooms": _rows_to_dicts(get_available_rooms_for_dates(check_in, nights))}
    return {"rooms": _rows_to_dicts(get_all_rooms())}


def _room_booking_information(args):
    from database.room_booking_db import get_room_booking_by_id
    bid = str(args["booking_id"]).strip().upper()
    return {"booking": _row_to_dict(get_room_booking_by_id(bid))}


def _table_information(args):
    from database.table_booking_db import get_available_restaurant_tables, get_restaurant_tables
    hotel_id = _hotel_id()
    if args.get("min_capacity") is not None and str(args.get("min_capacity")).strip():
        try: capacity = int(args["min_capacity"])
        except (TypeError, ValueError) as exc: raise ValueError("min_capacity must be a whole number.") from exc
        if capacity <= 0: raise ValueError("min_capacity must be greater than zero.")
        return {"available_tables": _rows_to_dicts(get_available_restaurant_tables(capacity, hotel_id))}
    return {"tables": _rows_to_dicts(get_restaurant_tables(str(args.get("status") or "").strip() or None, hotel_id))}


def _restaurant_information(args):
    from database.order_db import get_order, restaurant_operational_summary
    hotel_id = _hotel_id()
    order_id = str(args.get("order_id") or "").strip().upper()
    if order_id: return {"order": _row_to_dict(get_order(order_id, hotel_id))}
    return {"operational_summary": _json_safe(restaurant_operational_summary(hotel_id))}


def _billing_information(args):
    hotel_id = _hotel_id()
    invoice_id = str(args.get("invoice_id") or "").strip().upper()
    connection = get_connection()
    try:
        if invoice_id:
            row = connection.execute("SELECT * FROM invoices WHERE invoice_id = ? AND hotel_id = ?", (invoice_id, hotel_id)).fetchone()
            return {"invoice": _row_to_dict(row)}
        rows = connection.execute("SELECT * FROM invoices WHERE hotel_id = ? ORDER BY rowid DESC LIMIT 100", (hotel_id,)).fetchall()
        return {"invoices": _rows_to_dicts(rows)}
    finally: connection.close()


def _inventory_information(args):
    from database.inventory_db import get_low_stock_items, get_inventory_valuation
    hotel_id = _hotel_id(); item_id = str(args.get("item_id") or "").strip().upper()
    auth_user = _AI_TOOL_USER.get()
    user_id = auth_user.get("user_id") if isinstance(auth_user, dict) else None
    low = args.get("low_stock_only", False)
    if isinstance(low, str): low = low.lower() in {"1", "true", "yes", "y"}
    if item_id:
        connection = get_connection()
        try: row = connection.execute("SELECT * FROM inventory WHERE item_id = ? AND hotel_id = ?", (item_id, hotel_id)).fetchone()
        finally: connection.close()
        return {"item": _row_to_dict(row)}
    if low: return {"low_stock_items": _rows_to_dicts(get_low_stock_items(user_id=user_id, hotel_id=hotel_id))}
    return {"low_stock_items": _rows_to_dicts(get_low_stock_items(user_id=user_id, hotel_id=hotel_id)), "valuation": _json_safe(get_inventory_valuation(user_id=user_id, hotel_id=hotel_id))}


def _staff_information(args):
    hotel_id = _hotel_id(); staff_id = str(args.get("staff_id") or "").strip().upper(); status = str(args.get("status") or "").strip() or None
    connection = get_connection()
    try:
        sql = "SELECT * FROM staff WHERE hotel_id = ?"; params = [hotel_id]
        if staff_id: sql += " AND staff_id = ?"; params.append(staff_id)
        if status: sql += " AND lower(status) = lower(?)"; params.append(status)
        sql += " ORDER BY staff_name"
        return {"staff": _rows_to_dicts(connection.execute(sql, params).fetchall())}
    finally: connection.close()


def _expense_information(args):
    hotel_id = _hotel_id(); expense_id = str(args.get("expense_id") or "").strip().upper(); start = str(args.get("start_date") or "").strip() or None; end = str(args.get("end_date") or "").strip() or None
    connection = get_connection()
    try:
        sql = "SELECT * FROM expenses WHERE hotel_id = ?"; params = [hotel_id]
        if expense_id: sql += " AND expense_id = ?"; params.append(expense_id)
        sql += " ORDER BY rowid DESC"; rows = connection.execute(sql, params).fetchall()
    finally: connection.close()
    def parse(raw):
        for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
            try: return datetime.strptime(str(raw), fmt).date()
            except ValueError: pass
        return None
    sd, ed = parse(start) if start else None, parse(end) if end else None
    if start and sd is None or end and ed is None: raise ValueError("Dates must use YYYY-MM-DD or DD-MM-YYYY.")
    if sd or ed:
        rows = [r for r in rows if (d := parse(r["expense_date"])) and (sd is None or d >= sd) and (ed is None or d <= ed)]
    records = _rows_to_dicts(rows)
    return {"expenses": records, "total_expense": sum(float(r.get("amount") or 0) for r in records)}


def _feedback_information(args):
    hotel_id = _hotel_id(); feedback_id = str(args.get("feedback_id") or "").strip().upper(); customer_id = str(args.get("customer_id") or "").strip().upper()
    connection = get_connection()
    try:
        if feedback_id: return {"feedback": _row_to_dict(connection.execute("SELECT * FROM feedback WHERE feedback_id = ? AND hotel_id = ?", (feedback_id, hotel_id)).fetchone())}
        if customer_id: return {"feedback": _rows_to_dicts(connection.execute("SELECT * FROM feedback WHERE customer_id = ? AND hotel_id = ? ORDER BY rowid DESC", (customer_id, hotel_id)).fetchall())}
        return {"feedback": _rows_to_dicts(connection.execute("SELECT * FROM feedback WHERE hotel_id = ? ORDER BY rowid DESC LIMIT 100", (hotel_id,)).fetchall())}
    finally: connection.close()


def _notification_information(args):
    hotel_id = _hotel_id(); event_id = str(args.get("event_id") or "").strip(); status = str(args.get("status") or "").strip()
    connection = get_connection()
    try:
        sql = "SELECT * FROM notification_events WHERE hotel_id = ?"; params = [hotel_id]
        if event_id: sql += " AND event_id = ?"; params.append(event_id)
        sql += " ORDER BY created_at DESC LIMIT 100"; events = connection.execute(sql, params).fetchall()
        deliveries = []
        for event in events:
            dsql = "SELECT * FROM notification_deliveries WHERE event_id = ? AND hotel_id = ?"; dparams = [event["event_id"], hotel_id]
            if status: dsql += " AND status = ?"; dparams.append(status)
            deliveries.extend(connection.execute(dsql, dparams).fetchall())
        return {"events": _rows_to_dicts(events), "deliveries": _rows_to_dicts(deliveries)}
    finally: connection.close()


def _transportation_information(args):
    hotel_id = _hotel_id(); request_id = str(args.get("request_id") or "").strip().upper()
    connection = get_connection()
    try:
        if request_id: return {"request": _row_to_dict(connection.execute("SELECT * FROM transportation_requests WHERE request_id = ? AND hotel_id = ?", (request_id, hotel_id)).fetchone())}
        return {"requests": _rows_to_dicts(connection.execute("SELECT * FROM transportation_requests WHERE hotel_id = ? ORDER BY rowid DESC LIMIT 100", (hotel_id,)).fetchall()), "vehicles": _rows_to_dicts(connection.execute("SELECT * FROM transportation_vehicles WHERE hotel_id = ? ORDER BY rowid", (hotel_id,)).fetchall()), "drivers": _rows_to_dicts(connection.execute("SELECT * FROM transportation_drivers WHERE hotel_id = ? ORDER BY rowid", (hotel_id,)).fetchall())}
    finally: connection.close()


def _maps_information(args):
    from database.maps_navigation_db import get_map_configuration, get_nearby_places, get_navigation_routes
    hotel_id = _hotel_id(); category = str(args.get("category") or "").strip() or None
    return {"map_configuration": _json_safe(get_map_configuration(hotel_id)), "nearby_places": _rows_to_dicts(get_nearby_places(category=category, hotel_id=hotel_id)), "routes": _rows_to_dicts(get_navigation_routes(hotel_id, limit=50))}


def _media_information(args):
    from database.media_db import get_media, get_media_items
    hotel_id = _hotel_id(); media_id = str(args.get("media_id") or "").strip().upper(); category = str(args.get("category") or "").strip() or None
    active = args.get("active_only", False)
    if isinstance(active, str): active = active.lower() in {"1", "true", "yes", "y"}
    if media_id: return {"media": _row_to_dict(get_media(media_id, hotel_id))}
    return {"media": _rows_to_dicts(get_media_items(category=category, active_only=active, hotel_id=hotel_id))}


def _reports_summary(args):
    from database.analytics_report_db import get_revenue_summary, occupancy_data, adr_data, revpar_data, booking_trends_data, cancellation_data, no_show_data, customer_trends_data, inventory_trends_data, expense_trends_data
    hotel_id = _hotel_id(); start = str(args.get("start_date") or "").strip() or None; end = str(args.get("end_date") or "").strip() or None
    return {"revenue": _json_safe(get_revenue_summary(hotel_id, start, end)), "occupancy": _json_safe(occupancy_data(hotel_id, start, end)), "adr": _json_safe(adr_data(hotel_id, start, end)), "revpar": _json_safe(revpar_data(hotel_id, start, end)), "booking_trends": _json_safe(booking_trends_data(hotel_id, start, end)), "cancellation": _json_safe(cancellation_data(hotel_id, start, end)), "no_show": _json_safe(no_show_data(hotel_id, start, end)), "customer_trends": _json_safe(customer_trends_data(hotel_id, start, end)), "inventory_trends": _json_safe(inventory_trends_data(hotel_id, start, end)), "expense_trends": _json_safe(expense_trends_data(hotel_id, start, end))}


def _audit_information(args):
    from database.audit_db import get_audit_logs
    hotel_id = _hotel_id(); limit = args.get("limit", 100)
    try: limit = max(1, min(200, int(limit)))
    except (TypeError, ValueError) as exc: raise ValueError("limit must be a whole number.") from exc
    rows = get_audit_logs(hotel_id=hotel_id, actor_username=None, module=str(args.get("module") or "").strip() or None, action=str(args.get("action") or "").strip() or None, record_id=str(args.get("record_id") or "").strip() or None, status=str(args.get("status") or "").strip() or None, search=str(args.get("search") or "").strip() or None, request_id=str(args.get("request_id") or "").strip() or None, limit=limit)
    return {"audit": _rows_to_dicts(rows)}


_TOOL_HANDLERS = {
    "hotel_information": _hotel_information, "guest_information": _guest_information,
    "room_availability": _room_availability, "room_booking_information": _room_booking_information,
    "table_information": _table_information, "restaurant_information": _restaurant_information,
    "billing_information": _billing_information, "inventory_information": _inventory_information,
    "staff_information": _staff_information, "expense_information": _expense_information,
    "feedback_information": _feedback_information, "notification_information": _notification_information,
    "transportation_information": _transportation_information, "maps_information": _maps_information,
    "media_information": _media_information, "reports_summary": _reports_summary,
    "audit_information": _audit_information,
}


def execute_ai_tool(tool_name, arguments=None, user=None):
    """Validate and execute one registered, read-only, hotel-scoped tool."""
    tool_name = str(tool_name or "").strip().lower(); definition = get_tool_definition(tool_name)
    if definition is None: raise ValueError("Unknown AI tool.")
    args = _clean_args(arguments)
    allowed = set(definition["required_arguments"]) | set(definition["optional_arguments"])
    unknown = sorted(set(args) - allowed)
    if unknown: raise ValueError("Unknown argument(s): " + ", ".join(unknown))
    missing = [n for n in definition["required_arguments"] if args.get(n) is None or str(args.get(n)).strip() == ""]
    if missing: raise ValueError("Missing required argument(s): " + ", ".join(missing))
    hotel_id = _hotel_id()
    if user is not None:
        if int(user["hotel_id"]) != hotel_id: raise PermissionError("AI tool hotel scope mismatch.")
        module, action = definition["permission"]["module"], definition["permission"]["action"]
        if not has_permission(user["user_id"], module, action):
            raise PermissionError(f"Permission denied: {module} - {action}.")
    token = _AI_TOOL_USER.set(user)
    try:
        result = _TOOL_HANDLERS[tool_name](args)
    finally:
        _AI_TOOL_USER.reset(token)
    return {"tool": tool_name, "tool_version": TOOL_VERSION, "hotel_id": hotel_id, "read_only": True, "result": _json_safe(result)}


def execute_ai_tool_json(tool_name, arguments_json=None, user=None):
    if arguments_json is None or not str(arguments_json).strip(): arguments = {}
    else:
        try: arguments = json.loads(arguments_json)
        except json.JSONDecodeError as exc: raise ValueError("arguments_json must contain valid JSON.") from exc
    return execute_ai_tool(tool_name, arguments, user=user)
