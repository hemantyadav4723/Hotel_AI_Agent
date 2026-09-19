from utils.error_logging import log_non_blocking_error
"""AI booking automation for Phase 8.6.

This module is a controlled automation/orchestration layer. It never performs
arbitrary SQL and it does not replace the existing hotel booking business
logic. All committed records are created through the existing database
business functions used by the FastAPI operations routes.
"""

from dataclasses import asdict, dataclass
from datetime import date, datetime, time
import re
import uuid

from ai.context import AIRequestContext
from database.customer_db import get_customer_by_id, resolve_guest_for_booking, validate_guest_hotel_relationship
from database.permission_db import has_permission
from database.room_booking_db import (
    get_available_rooms_for_dates,
    get_room_by_number,
    get_room_booking_by_id,
    save_and_book_room,
)
from database.table_booking_db import create_table_booking, get_available_restaurant_tables
from database.room_payment_db import get_required_reservation_advance
from database.order_db import get_order, save_order
from database.restaurant_menu_db import get_menu_item, get_menu_items
from database.transportation_db import create_transportation_request


GST_RATE = 0.05
BOOKING_TYPES = ("room", "table", "restaurant", "transportation")


@dataclass(frozen=True)
class BookingItem:
    item_id: str
    quantity: int


@dataclass(frozen=True)
class AIBookingResponse:
    status: str
    handled: bool
    message: str
    booking_type: str | None
    conversation_id: str
    confirmation_required: bool = False
    booking_id: str | None = None
    reference_id: str | None = None
    missing_fields: tuple[str, ...] = ()
    quote: dict | None = None
    result: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class AIBookingAutomation:
    """Guided, confirmation-gated booking automation."""

    _TYPE_RULES = (
        ("transportation", ("transport", "transportation", "airport pickup", "airport drop", "railway station", "taxi", "cab", "pickup", "drop")),
        ("restaurant", ("restaurant order", "food order", "order food", "order", "menu")),
        ("table", ("table booking", "book a table", "reserve a table", "table reservation")),
        ("room", ("room booking", "book a room", "reserve a room", "room reservation", "reservation")),
    )

    def detect_booking_type(self, message: str, booking_type: str | None = None) -> str | None:
        explicit = str(booking_type or "").strip().lower()
        if explicit:
            if explicit not in BOOKING_TYPES:
                raise ValueError("Unsupported booking type.")
            return explicit
        text = " ".join(str(message or "").strip().lower().split())
        for kind, phrases in self._TYPE_RULES:
            if any(phrase in text for phrase in phrases):
                return kind
        return None

    @staticmethod
    def _conversation_id(value: str | None) -> str:
        return str(value or uuid.uuid4()).strip()[:128]

    @staticmethod
    def _permission(context: AIRequestContext, module: str, action: str) -> None:
        if not has_permission(context.user_id, module, action):
            raise PermissionError(f"Permission denied: {module} - {action}.")

    @staticmethod
    def _parse_date(value: str | date | None) -> date | None:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        raw = str(value).strip()
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(raw[:10], fmt).date()
            except ValueError:
                continue
        raise ValueError("Date must use YYYY-MM-DD or DD-MM-YYYY format.")

    @staticmethod
    def _parse_time(value: str | None) -> time | None:
        if value is None or not str(value).strip():
            return None
        raw = str(value).strip().upper()
        for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M:%S %p"):
            try:
                return datetime.strptime(raw, fmt).time()
            except ValueError:
                continue
        raise ValueError("Time must use HH:MM or HH:MM AM/PM format.")

    @staticmethod
    def _booking_id(prefix: str = "AI") -> str:
        return f"AI-{prefix}-{datetime.now().strftime('%Y%m%d%H%M%S%f')[:-3]}"

    @staticmethod
    def _parse_items(message: str, items: list[BookingItem] | None) -> list[BookingItem]:
        if items:
            return [BookingItem(str(item.item_id).strip().upper(), int(item.quantity)) for item in items]
        parsed: list[BookingItem] = []
        # Supported lightweight syntax: ITEM_ID x2 / ITEM_ID:2.
        for match in re.finditer(r"\b([A-Z][A-Z0-9_-]{2,})\s*(?:x|:|qty\s*)\s*(\d{1,3})\b", str(message or ""), re.I):
            parsed.append(BookingItem(match.group(1).upper(), int(match.group(2))))
        return parsed

    @staticmethod
    def _guest_fields(guest_name: str | None, guest_mobile: str | None, customer_id: str | None) -> tuple[str | None, str | None, str | None]:
        return (
            str(guest_name or "").strip() or None,
            str(guest_mobile or "").strip() or None,
            str(customer_id or "").strip().upper() or None,
        )

    def process(
        self,
        message: str,
        context: AIRequestContext,
        conversation_id: str | None = None,
        *,
        booking_type: str | None = None,
        confirm: bool = False,
        guest_name: str | None = None,
        guest_mobile: str | None = None,
        guest_email: str | None = None,
        customer_id: str | None = None,
        room_number: str | None = None,
        check_in_date: str | date | None = None,
        nights: int | None = None,
        adults: int = 1,
        children: int = 0,
        advance_amount: float = 0,
        payment_method: str | None = None,
        notes: str = "",
        table_number: str | None = None,
        booking_date: str | date | None = None,
        booking_time: str | None = None,
        persons: int | None = None,
        items: list[BookingItem] | None = None,
        transportation_type: str | None = None,
        pickup_date: str | date | None = None,
        pickup_time: str | None = None,
        pickup_location: str | None = None,
        drop_location: str | None = None,
        vehicle_id: str | None = None,
        vehicle_type: str | None = None,
        driver_id: str | None = None,
        fare: float = 0,
    ) -> AIBookingResponse:
        conversation = self._conversation_id(conversation_id)
        kind = self.detect_booking_type(message, booking_type)
        if kind is None:
            return AIBookingResponse(
                "unknown_booking_type", False,
                "Please specify whether you need a room reservation, table reservation, restaurant order, or transportation request.",
                None, conversation,
            )

        guest_name, guest_mobile, customer_id = self._guest_fields(guest_name, guest_mobile, customer_id)
        if customer_id:
            validate_guest_hotel_relationship(customer_id, context.hotel_id)
            guest = get_customer_by_id(customer_id)
            if guest is None:
                raise ValueError("Guest not found.")
            guest_name = guest_name or guest["customer_name"]
            guest_mobile = guest_mobile or guest["customer_mobile"]
            guest_email = guest_email or guest["customer_email"]
        text = " ".join(str(message or "").strip().lower().split())

        if kind == "room":
            return self._room(
                text, context, conversation, confirm, guest_name, guest_mobile, guest_email, customer_id,
                room_number, check_in_date, nights, adults, children, notes, advance_amount, payment_method,
            )
        if kind == "table":
            return self._table(
                context, conversation, confirm, guest_name, guest_mobile, customer_id,
                table_number, booking_date, booking_time, persons,
            )
        if kind == "restaurant":
            return self._restaurant(
                message, context, conversation, confirm, guest_name, guest_mobile, guest_email, customer_id,
                table_number, items, notes,
            )
        return self._transportation(
            context, conversation, confirm, guest_name, guest_mobile, guest_email, customer_id,
            transportation_type, pickup_date, pickup_time, pickup_location, drop_location,
            vehicle_id, vehicle_type, driver_id, fare, notes,
        )

    def _room(self, text, context, conversation, confirm, guest_name, guest_mobile, guest_email, customer_id,
              room_number, check_in_date, nights, adults, children, notes, advance_amount, payment_method):
        check_in = self._parse_date(check_in_date)
        if check_in is None:
            match = re.search(r"\b(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4}|\d{2}/\d{2}/\d{4})\b", text)
            check_in = self._parse_date(match.group(1)) if match else None
        if nights is None:
            match = re.search(r"\b(\d{1,3})\s+nights?\b", text)
            nights = int(match.group(1)) if match else None
        if room_number is None:
            match = re.search(r"\broom\s*(?:number|no)?\s*[:#-]?\s*([A-Z0-9][A-Z0-9_-]{0,9})\b", text, re.I)
            if match:
                room_number = match.group(1).upper()

        missing = []
        if not check_in: missing.append("check_in_date")
        if not nights: missing.append("nights")
        if missing:
            return AIBookingResponse("information_required", True, f"I need: {', '.join(missing)}.", "room", conversation, missing_fields=tuple(missing))

        available = get_available_rooms_for_dates(check_in.strftime("%d-%m-%Y"), int(nights))
        available_map = {str(row["room_number"]).upper(): row for row in available}
        if not room_number:
            options = [
                {"room_number": row["room_number"], "room_type": row["room_type"], "room_price": float(row["room_price"] or 0)}
                for row in available[:20]
            ]
            return AIBookingResponse("room_selection_required", True, "Please select an available room.", "room", conversation, result={"available_rooms": options})
        room = available_map.get(str(room_number).upper())
        if room is None:
            return AIBookingResponse("unavailable", True, f"Room {room_number} is not available for the selected stay.", "room", conversation, result={"available_rooms": [row["room_number"] for row in available[:20]]})

        guest_missing = []
        if not guest_name: guest_missing.append("guest_name")
        if not guest_mobile and not customer_id: guest_missing.append("guest_mobile")
        if guest_missing:
            return AIBookingResponse("information_required", True, f"Room {room_number} is available. Before pricing and confirmation, I need: {', '.join(guest_missing)}.", "room", conversation, missing_fields=tuple(guest_missing), result={"selected_room": {"room_number": room_number, "room_type": room["room_type"]}})

        price = float(room["room_price"] or 0)
        subtotal = round(price * int(nights), 2)
        gst = round(subtotal * GST_RATE, 2)
        total = round(subtotal + gst, 2)
        minimum_advance = get_required_reservation_advance(room_number, context.hotel_id)
        advance = round(float(advance_amount or 0), 2)
        quote = {"room_number": room_number, "room_type": room["room_type"], "room_price_per_night": price, "nights": int(nights), "subtotal": subtotal, "gst": gst, "grand_total": total, "check_in_date": check_in.isoformat(), "minimum_reservation_advance": minimum_advance, "advance_amount": advance, "balance_amount": round(total - advance, 2)}
        if not confirm:
            return AIBookingResponse("confirmation_required", True, f"Room {room_number} is available. Total is ₹{total:.2f}. Minimum reservation advance is ₹{minimum_advance:.2f}. Please provide the advance amount and confirm.", "room", conversation, True, quote=quote)

        if advance < minimum_advance:
            return AIBookingResponse("advance_required", True, f"A minimum reservation advance of ₹{minimum_advance:.2f} is required for Room {room_number}. Please provide the advance amount and confirm again.", "room", conversation, True, missing_fields=("advance_amount",), quote=quote)
        if advance > total:
            raise ValueError("Advance payment cannot exceed the booking total.")

        self._permission(context, "Rooms", "Create")
        # Resolve/create the guest only after all booking validations pass.
        if not customer_id:
            customer_id = resolve_guest_for_booking(guest_name, guest_mobile, guest_email, None, hotel_id=context.hotel_id)
        bid = self._booking_id("ROOM")
        save_and_book_room(
            bid, datetime.now(), guest_name, guest_mobile or "N/A", room_number, room["room_type"], room["room_price"], int(nights), subtotal, gst, total,
            check_in.strftime("%d-%m-%Y"), advance, payment_method, notes, "Confirmed", int(adults), int(children), customer_id, guest_email, None,
        )
        booking = get_room_booking_by_id(bid)
        return AIBookingResponse("booked", True, f"Room reservation {bid} has been created.", "room", conversation, booking_id=bid, reference_id=bid, quote=quote, result={"booking": self._row_dict(booking)})

    def _table(self, context, conversation, confirm, guest_name, guest_mobile, customer_id, table_number, booking_date, booking_time, persons):
        booking_day = self._parse_date(booking_date)
        reservation_time = self._parse_time(booking_time)
        missing = []
        if not guest_name: missing.append("guest_name")
        if not guest_mobile and not customer_id: missing.append("guest_mobile")
        if not booking_day: missing.append("booking_date")
        if not reservation_time: missing.append("booking_time")
        if not persons: missing.append("persons")
        if missing:
            return AIBookingResponse("information_required", True, f"I need: {', '.join(missing)}.", "table", conversation, missing_fields=tuple(missing))
        available_tables = get_available_restaurant_tables(int(persons), context.hotel_id)
        if not table_number:
            options = [
                {"table_number": row["table_number"], "capacity": row["table_capacity"], "status": row["table_status"]}
                for row in available_tables[:50]
            ]
            return AIBookingResponse("table_selection_required", True, "Please select an available table.", "table", conversation, result={"available_tables": options})
        selected_table = next((row for row in available_tables if str(row["table_number"]).upper() == str(table_number).upper()), None)
        if selected_table is None:
            return AIBookingResponse("unavailable", True, f"Table {table_number} is not available for {persons} person(s).", "table", conversation, result={"available_tables": [row["table_number"] for row in available_tables[:50]]})
        if not confirm:
            return AIBookingResponse("confirmation_required", True, f"Table {table_number} can be reserved for {persons} person(s) on {booking_day.isoformat()} at {reservation_time.strftime('%H:%M')}. Please confirm to create the reservation.", "table", conversation, True, quote={"table_number": table_number, "persons": int(persons), "booking_date": booking_day.isoformat(), "booking_time": reservation_time.strftime("%H:%M")})

        self._permission(context, "Tables", "Create")
        if not customer_id:
            customer_id = resolve_guest_for_booking(guest_name, guest_mobile, None, None, hotel_id=context.hotel_id)
        bid = self._booking_id("TABLE")
        create_table_booking(bid, datetime.combine(booking_day, reservation_time), customer_id, guest_name, guest_mobile or "N/A", table_number, int(persons))
        return AIBookingResponse("booked", True, f"Table reservation {bid} has been created.", "table", conversation, booking_id=bid, reference_id=bid, result={"booking_id": bid, "customer_id": customer_id, "table_number": table_number})

    def _restaurant(self, message, context, conversation, confirm, guest_name, guest_mobile, guest_email, customer_id, table_number, items, notes):
        guest_required = not guest_name or (not guest_mobile and not customer_id)
        cart_items = self._parse_items(message, items)
        missing = []
        if guest_required: missing.extend(["guest_name", "guest_mobile"] if not customer_id else ["guest_name"])
        if not table_number: missing.append("table_number")
        if not cart_items: missing.append("items")
        if missing:
            menu = None
            if "items" in missing:
                menu = [{"item_id": row["item_id"], "item_name": row["item_name"], "price": float(row["price"] or 0)} for row in get_menu_items(available_only=True, hotel_id=context.hotel_id)[:50]]
            return AIBookingResponse("information_required", True, f"I need: {', '.join(missing)}.", "restaurant", conversation, missing_fields=tuple(missing), result={"menu": menu} if menu is not None else None)

        cart = []
        for item in cart_items:
            menu_item = get_menu_item(item.item_id, context.hotel_id)
            if menu_item is None or not menu_item["is_available"]:
                return AIBookingResponse("unavailable", True, f"Menu item {item.item_id} is unavailable.", "restaurant", conversation)
            cart.append({"item_id": menu_item["item_id"], "name": menu_item["item_name"], "price": float(menu_item["price"]), "quantity": int(item.quantity), "subtotal": round(float(menu_item["price"]) * int(item.quantity), 2)})
        subtotal = round(sum(item["subtotal"] for item in cart), 2)
        gst = round(subtotal * GST_RATE, 2)
        total = round(subtotal + gst, 2)
        quote = {"table_number": table_number, "items": cart, "subtotal": subtotal, "gst": gst, "grand_total": total}
        if not confirm:
            return AIBookingResponse("confirmation_required", True, f"Restaurant order total is ₹{total:.2f}. Please confirm to create the order.", "restaurant", conversation, True, quote=quote)

        self._permission(context, "Restaurant", "Create")
        if not customer_id:
            customer_id = resolve_guest_for_booking(guest_name, guest_mobile, guest_email, None, hotel_id=context.hotel_id)
        order_id = self._booking_id("ORDER")
        save_order(cart, order_id, datetime.now(), guest_name, guest_mobile or "N/A", table_number, subtotal, gst, total, customer_id, 0, context.hotel_id, notes, None, 0, 0, 0)
        try:
            from database.notification_db import record_notification_event
            record_notification_event(
                "Booking",
                "Restaurant Order Created",
                f"Restaurant order {order_id} has been created for {guest_name}.",
                reference_type="RESTAURANT_ORDER",
                reference_id=order_id,
                recipient_type="Guest",
                recipient_id=customer_id,
                recipient_name=guest_name,
                recipient_mobile=guest_mobile,
                recipient_email=guest_email,
                hotel_id=context.hotel_id,
                idempotency_key=f"BOOKING:{context.hotel_id}:RESTAURANT:{order_id}",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        order = get_order(order_id, context.hotel_id)
        return AIBookingResponse("booked", True, f"Restaurant order {order_id} has been created.", "restaurant", conversation, booking_id=order_id, reference_id=order_id, quote=quote, result={"order": self._row_dict(order)})

    def _transportation(self, context, conversation, confirm, guest_name, guest_mobile, guest_email, customer_id, transportation_type, pickup_date, pickup_time, pickup_location, drop_location, vehicle_id, vehicle_type, driver_id, fare, notes):
        pickup_day = self._parse_date(pickup_date)
        pickup_clock = self._parse_time(pickup_time)
        missing = []
        for field, value in (("guest_name", guest_name), ("transportation_type", transportation_type), ("pickup_date", pickup_day), ("pickup_time", pickup_clock), ("pickup_location", pickup_location), ("drop_location", drop_location)):
            if not value: missing.append(field)
        if missing:
            return AIBookingResponse("information_required", True, f"I need: {', '.join(missing)}.", "transportation", conversation, missing_fields=tuple(missing))
        quote = {"transportation_type": transportation_type, "pickup_date": pickup_day.isoformat(), "pickup_time": pickup_clock.strftime("%H:%M"), "pickup_location": pickup_location, "drop_location": drop_location, "fare": float(fare or 0)}
        if not confirm:
            return AIBookingResponse("confirmation_required", True, "Transportation details are ready. Please confirm to create the request.", "transportation", conversation, True, quote=quote)

        self._permission(context, "Hotel", "Create")
        request_id = create_transportation_request(customer_id, guest_name, guest_mobile, guest_email, transportation_type, pickup_day.isoformat(), pickup_clock.strftime("%H:%M"), pickup_location, drop_location, vehicle_id, vehicle_type, driver_id, float(fare or 0), notes=notes)
        return AIBookingResponse("booked", True, f"Transportation request {request_id} has been created.", "transportation", conversation, reference_id=request_id, result={"request_id": request_id, **quote})

    @staticmethod
    def _row_dict(row):
        return dict(row) if row is not None else None


booking_automation = AIBookingAutomation()
