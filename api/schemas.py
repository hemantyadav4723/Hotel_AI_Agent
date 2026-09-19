from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginRequest(APIModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)
    hotel_id: int | None = Field(default=None, ge=1)


class TokenResponse(APIModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: dict[str, Any]


class CustomerCreate(APIModel):
    customer_id: str | None = Field(default=None, max_length=50)
    customer_name: str = Field(min_length=1, max_length=150)
    customer_mobile: str = Field(min_length=5, max_length=30)
    customer_email: str | None = Field(default=None, max_length=200)
    customer_address: str | None = Field(default=None, max_length=300)
    customer_city: str | None = Field(default=None, max_length=100)
    customer_state: str | None = Field(default=None, max_length=100)
    customer_country: str = Field(default="India", max_length=100)
    customer_pincode: str | None = Field(default=None, max_length=20)
    guest_status: str = Field(default="Active", max_length=30)
    preferences: str | None = None
    special_requests: str | None = None
    guest_notes: str | None = None


class CustomerUpdate(APIModel):
    customer_name: str = Field(min_length=1, max_length=150)
    customer_mobile: str = Field(min_length=5, max_length=30)
    customer_email: str | None = Field(default=None, max_length=200)
    customer_address: str | None = Field(default=None, max_length=300)
    customer_city: str | None = Field(default=None, max_length=100)
    customer_state: str | None = Field(default=None, max_length=100)
    customer_country: str = Field(default="India", max_length=100)
    customer_pincode: str | None = Field(default=None, max_length=20)
    guest_status: str = Field(default="Active", max_length=30)
    is_active: bool = True
    preferences: str | None = None
    special_requests: str | None = None
    guest_notes: str | None = None


class RoomBookingCreate(APIModel):
    booking_id: str | None = None
    customer_name: str = Field(min_length=1, max_length=150)
    customer_mobile: str = Field(min_length=5, max_length=30)
    room_number: str = Field(min_length=1, max_length=30)
    days: int = Field(ge=1, le=365)
    check_in_date: date | None = None
    advance_amount: float = Field(default=0, ge=0)
    payment_method: str | None = None
    notes: str = ""
    booking_status: str = "Pending"
    adults: int = Field(default=1, ge=1, le=20)
    children: int = Field(default=0, ge=0, le=20)
    customer_id: str | None = None
    customer_email: str | None = None
    customer_address: str | None = None


class ReservationModify(APIModel):
    customer_name: str | None = Field(default=None, min_length=1, max_length=150)
    customer_mobile: str | None = Field(default=None, min_length=5, max_length=30)
    room_number: str | None = Field(default=None, max_length=200)
    check_in_date: date | None = None
    nights: int | None = Field(default=None, ge=1, le=365)
    notes: str | None = Field(default=None, max_length=2000)
    adults: int | None = Field(default=None, ge=1, le=20)
    children: int | None = Field(default=None, ge=0, le=20)


class StayOptionsUpdate(APIModel):
    early_check_in_time: str | None = Field(default=None, max_length=30)
    late_check_out_time: str | None = Field(default=None, max_length=30)


class CancellationRequest(APIModel):
    reason: str = Field(min_length=1, max_length=500)


class NoShowRequest(APIModel):
    reason: str = Field(min_length=1, max_length=500)


class TransferRoomRequest(APIModel):
    new_room_number: str = Field(min_length=1, max_length=30)


class OrderItem(APIModel):
    item_id: str
    quantity: int = Field(ge=1, le=1000)


class RestaurantOrderCreate(APIModel):
    order_id: str | None = None
    customer_name: str = Field(min_length=1, max_length=150)
    customer_mobile: str = Field(min_length=5, max_length=30)
    table_number: str = Field(min_length=1, max_length=30)
    items: list[OrderItem] = Field(min_length=1)
    discount: float = Field(default=0, ge=0)
    payment_method: str | None = None
    paid_amount: float = Field(default=0, ge=0)
    advance_amount: float = Field(default=0, ge=0)
    order_notes: str | None = None
    customer_id: str | None = None


class TableBookingCreate(APIModel):
    booking_id: str | None = None
    booking_date: date | None = None
    booking_time: str
    customer_id: str
    customer_name: str
    customer_mobile: str
    table_number: str
    persons: int = Field(ge=1, le=100)


class TransportationCreate(APIModel):
    customer_id: str | None = None
    guest_name: str | None = None
    guest_mobile: str | None = None
    guest_email: str | None = None
    transportation_type: str
    pickup_date: date
    pickup_time: str
    pickup_location: str
    drop_location: str
    vehicle_id: str | None = None
    vehicle_type: str | None = None
    driver_id: str | None = None
    fare: float = Field(default=0, ge=0)
    special_request: str | None = None
    notes: str | None = None


class FeedbackCreate(APIModel):
    feedback_id: str | None = None
    customer_name: str
    mobile: str
    rating: int = Field(ge=1, le=5)
    review: str = Field(min_length=1, max_length=2000)
    customer_id: str | None = None
    category: str = "General"
    complaint: str | None = None
    allow_pending_complaint: bool = False


class FeedbackUpdate(APIModel):
    rating: int = Field(ge=1, le=5)
    review: str = Field(min_length=10, max_length=2000)
    category: str = "General"
    complaint: str | None = None
    issue: str | None = None
    resolution: str | None = None
    status: str = "Closed"
    follow_up_date: str | None = None
    follow_up_required: bool = False
    follow_up_method: str | None = None
    follow_up_status: str | None = None
    follow_up_notes: str | None = None
    allow_pending_complaint: bool = False


class ExpenseCreate(APIModel):
    expense_id: str
    expense_date: date
    expense_time: str
    expense_name: str
    amount: float = Field(gt=0)
    category: str
    description: str
    category_id: str | None = None
    vendor_id: str | None = None
    payment_method: str | None = None
    receipt_reference: str | None = None
    department_id: str | None = None
    is_recurring: bool = False
    recurrence_frequency: str | None = None
    recurrence_start_date: date | None = None


class MapConfigurationUpdate(APIModel):
    provider: str
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    default_zoom: int = Field(default=16, ge=1, le=22)
    api_enabled: bool = False
    integration_status: str = "Not Integrated"


class NearbyPlaceCreate(APIModel):
    place_name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)
    address: str | None = None
    distance_km: float | None = Field(default=None, ge=0)
    travel_time_minutes: int | None = Field(default=None, ge=0)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    notes: str | None = None


class NearbyPlaceStatusUpdate(APIModel):
    is_active: bool


class NavigationRouteCreate(APIModel):
    origin: str = Field(min_length=1, max_length=300)
    destination: str = Field(min_length=1, max_length=300)
    distance_km: float | None = Field(default=None, ge=0)
    eta_minutes: int | None = Field(default=None, ge=0)
    provider: str | None = None
    integration_status: str = "Not Integrated"
    notes: str | None = None


class MediaCreate(APIModel):
    media_type: str
    title: str
    file_url: str
    category: str = "General"
    description: str | None = None
    display_order: int = Field(default=0, ge=0)
    guest_visible: bool = True


class TransportationUpdate(APIModel):
    status: str | None = Field(default=None, max_length=50)
    vehicle_id: str | None = None
    driver_id: str | None = None
    fare: float | None = Field(default=None, ge=0)
    provider_name: str | None = None
    provider_reference: str | None = None
    integration_status: str | None = None
    special_request: str | None = None
    notes: str | None = None


class VehicleCreate(APIModel):
    vehicle_number: str
    vehicle_type: str
    capacity: int = Field(default=4, ge=1, le=100)
    notes: str | None = None


class DriverCreate(APIModel):
    driver_name: str
    driver_mobile: str | None = None
    license_number: str | None = None
    vehicle_type: str | None = None
    notes: str | None = None


class StatusUpdate(APIModel):
    status: str = Field(min_length=1, max_length=50)


class PasswordChange(APIModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=256)


class ToolRequest(APIModel):
    arguments: dict[str, Any] = Field(default_factory=dict)


class AICommunicationRequest(APIModel):
    message: str = Field(min_length=1, max_length=8000)
    channel: Literal[
        "website_web_app",
        "whatsapp",
        "mobile_app",
        "social_media",
        "internal_hotel_system",
        "qr_code",
    ]
    conversation_id: str | None = Field(default=None, max_length=128)


class AIVoiceRequest(APIModel):
    input_type: Literal["transcript", "audio_reference"] = "transcript"
    transcript: str | None = Field(default=None, max_length=8000)
    audio_reference: str | None = Field(default=None, max_length=1000)
    conversation_id: str | None = Field(default=None, max_length=128)
    use_case: Literal[
        "hotel_phone_reception",
        "reception_desk_assistant",
        "guest_room_voice_assistant",
        "staff_voice_assistant",
    ] = "hotel_phone_reception"
    handoff_requested: bool = False


class AIRequest(APIModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: str | None = Field(default=None, max_length=128)


class AIReceptionistRequest(APIModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: str | None = Field(default=None, max_length=128)


class AIGuestServiceRequest(APIModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: str | None = Field(default=None, max_length=128)
    guest_name: str | None = Field(default=None, max_length=150)
    customer_id: str | None = Field(default=None, max_length=50)
    room_number: str | None = Field(default=None, max_length=30)
    priority: str = Field(default="Normal", max_length=20)


class AIStaffAssistantRequest(APIModel):
    message: str = Field(min_length=1, max_length=8000)
    assistant_area: Literal[
        "reception",
        "housekeeping",
        "maintenance",
        "restaurant_kitchen",
        "laundry",
        "transport_concierge",
        "management",
    ] | None = None
    conversation_id: str | None = Field(default=None, max_length=128)


class AIBookingItem(APIModel):
    item_id: str = Field(min_length=1, max_length=50)
    quantity: int = Field(ge=1, le=1000)


class AIBookingAutomationRequest(APIModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: str | None = Field(default=None, max_length=128)
    booking_type: Literal["room", "table", "restaurant", "transportation"] | None = None
    confirm: bool = False
    guest_name: str | None = Field(default=None, max_length=150)
    guest_mobile: str | None = Field(default=None, max_length=30)
    guest_email: str | None = Field(default=None, max_length=200)
    customer_id: str | None = Field(default=None, max_length=50)
    room_number: str | None = Field(default=None, max_length=30)
    check_in_date: date | None = None
    nights: int | None = Field(default=None, ge=1, le=365)
    advance_amount: float = Field(default=0, ge=0)
    payment_method: str | None = Field(default=None, max_length=50)
    adults: int = Field(default=1, ge=1, le=20)
    children: int = Field(default=0, ge=0, le=20)
    notes: str = Field(default="", max_length=2000)
    table_number: str | None = Field(default=None, max_length=30)
    booking_date: date | None = None
    booking_time: str | None = Field(default=None, max_length=30)
    persons: int | None = Field(default=None, ge=1, le=100)
    items: list[AIBookingItem] = Field(default_factory=list, max_length=100)
    transportation_type: str | None = Field(default=None, max_length=60)
    pickup_date: date | None = None
    pickup_time: str | None = Field(default=None, max_length=30)
    pickup_location: str | None = Field(default=None, max_length=300)
    drop_location: str | None = Field(default=None, max_length=300)
    vehicle_id: str | None = Field(default=None, max_length=50)
    vehicle_type: str | None = Field(default=None, max_length=100)
    driver_id: str | None = Field(default=None, max_length=50)
    fare: float = Field(default=0, ge=0)

class AIProactiveNotificationRequest(APIModel):
    trigger: Literal[
        "booking_created", "check_in", "check_out", "low_inventory",
        "guest_complaint", "transportation_request", "event", "follow_up",
    ]
    confirm: bool = False
    conversation_id: str | None = Field(default=None, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)


class AIAutomationRequest(APIModel):
    message: str = Field(min_length=1, max_length=8000)
    automation_type: Literal[
        "booking", "guest_request", "notification", "follow_up",
        "task", "escalation", "reminder", "status_update",
    ] | None = None
    workflow: str | None = Field(default=None, max_length=100)
    confirm: bool = False
    conversation_id: str | None = Field(default=None, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)



class AISafetyRequest(APIModel):
    message: str = Field(min_length=1, max_length=8000)
    confirm: bool = False
    human_approved: bool = False
    requested_hotel_id: int | None = None

class AIMultilingualRequest(APIModel):
    message: str = Field(min_length=1, max_length=8000)
    language: str | None = Field(default=None, min_length=2, max_length=30)
    conversation_id: str | None = Field(default=None, max_length=128)


class AIPersonalizationRequest(APIModel):
    customer_id: str = Field(min_length=1, max_length=50)
    special_occasions: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    communication_channel: str | None = Field(default=None, max_length=50)
    communication_purpose: str | None = Field(default=None, max_length=200)

class AIMemoryRequest(APIModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: str = Field(min_length=1, max_length=128)
    customer_id: str | None = Field(default=None, max_length=50)

class AIHotelKnowledgeRequest(APIModel):
    section: str = Field(default="all", min_length=2, max_length=60)


class AIIntegrationConfigRequest(APIModel):
    integration: Literal[
        "whatsapp", "email", "sms", "voice", "payment_gateway",
        "maps", "ride_provider", "food_delivery"
    ]
    provider: str = Field(min_length=1, max_length=100)
    enabled: bool = True
    configured: bool = False
    credential_reference: str | None = Field(default=None, max_length=200)
    endpoint: str | None = Field(default=None, max_length=1000)


class AIIntegrationExecuteRequest(APIModel):
    integration: Literal[
        "whatsapp", "email", "sms", "voice", "payment_gateway",
        "maps", "ride_provider", "food_delivery"
    ]
    operation: str = Field(min_length=1, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)


class AIIntegrationAIRequest(APIModel):
    integration: Literal[
        "whatsapp", "email", "sms", "voice", "payment_gateway",
        "maps", "ride_provider", "food_delivery"
    ]
    operation: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: str | None = Field(default=None, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)


class AIIntegrationWebhookRequest(APIModel):
    integration: Literal[
        "whatsapp", "email", "sms", "voice", "payment_gateway",
        "maps", "ride_provider", "food_delivery"
    ]
    event_type: str = Field(min_length=1, max_length=100)
    event_id: str = Field(min_length=1, max_length=200)
    payload: dict[str, Any] = Field(default_factory=dict)

class AIHandoffDetectRequest(APIModel):
    message: str = Field(min_length=1, max_length=8000)
    requested: bool = False
    priority: str = Field(default="normal", max_length=20)


class AIHandoffRequest(APIModel):
    conversation_id: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=1, max_length=200)
    priority: str = Field(default="normal", max_length=20)
    target: str = Field(default="reception", max_length=30)
    context: dict[str, Any] = Field(default_factory=dict)


class AIHandoffAssignRequest(APIModel):
    conversation_id: str = Field(min_length=1, max_length=128)
    human_user_id: str = Field(min_length=1, max_length=100)
    target: str | None = Field(default=None, max_length=30)


class AIHandoffTakeoverRequest(APIModel):
    conversation_id: str = Field(min_length=1, max_length=128)
    human_user_id: str = Field(min_length=1, max_length=100)


class AIHandoffResolveRequest(APIModel):
    conversation_id: str = Field(min_length=1, max_length=128)
    resolution: str = Field(min_length=1, max_length=4000)
    context: dict[str, Any] = Field(default_factory=dict)


class AIHandoffConversationRequest(APIModel):
    conversation_id: str = Field(min_length=1, max_length=128)
