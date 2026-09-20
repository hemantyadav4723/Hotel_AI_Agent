"""Provider-neutral AI agent core for Phase 8.3.

The core performs deterministic intent routing and controlled tool orchestration.
It never executes SQL or arbitrary application code. Read requests are routed to
registered AI business tools; mutating requests are separated and require a
later confirmation/action layer.
"""

from dataclasses import asdict, dataclass
import re
import uuid

from ai.config import settings
from ai.providers.gemini import get_gemini_provider
from ai.context import AIRequestContext
from database.ai_tools_db import execute_ai_tool, get_tool_definition
from ai.observability import observability


@dataclass(frozen=True)
class AIRequest:
    message: str
    context: AIRequestContext
    conversation_id: str | None = None


@dataclass(frozen=True)
class AIResponse:
    status: str
    handled: bool
    message: str
    provider: str
    model: str | None
    hotel_id: int
    conversation_id: str | None
    intent: str | None = None
    tool_calls: tuple[dict, ...] = ()
    confirmation_required: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class IntentDecision:
    intent: str
    tool_names: tuple[str, ...]
    arguments: dict
    confidence: str
    action_required: bool = False


class AIAgentCore:
    """Controlled intent -> tool -> response orchestration layer."""

    _INTENT_RULES = (
        ("hotel_information", ("hotel information", "hotel info", "facilities", "amenities", "timing", "check in", "check-in", "check out", "check-out", "address", "location", "wifi", "parking", "laundry", "policy", "policies")),
        ("guest_information", ("guest", "customer", "guest profile", "customer profile")),
        ("room_availability", ("room availability", "available room", "rooms available", "room vacant", "vacant room", "room status")),
        ("room_booking_information", ("booking", "reservation", "reservation status", "booking status")),
        ("table_information", ("table", "restaurant table", "table availability", "available table")),
        ("restaurant_information", ("restaurant", "food order", "restaurant order", "menu order", "food")),
        ("billing_information", ("bill", "billing", "invoice", "payment status", "payment history", "receipt")),
        ("inventory_information", ("inventory", "stock", "low stock", "stock value")),
        ("staff_information", ("staff", "employee", "employees", "hr staff")),
        ("expense_information", ("expense", "expenses", "spending", "expenditure")),
        ("feedback_information", ("feedback", "review", "reviews", "complaint", "complaints", "satisfaction")),
        ("notification_information", ("notification", "notifications", "delivery status")),
        ("transportation_information", ("transport", "transportation", "driver", "vehicle", "ride", "pickup", "drop")),
        ("maps_information", ("map", "maps", "nearby", "nearby place", "navigation", "route")),
        ("media_information", ("photo", "photos", "gallery", "media", "image")),
        ("reports_summary", ("report", "reports", "revenue", "occupancy", "adr", "revpar", "analytics", "performance")),
        ("audit_information", ("audit", "activity log", "audit log", "who changed", "activity history")),
    )

    _ACTION_WORDS = re.compile(
        r"\b(book|reserve|create|add|modify|update|change|cancel|delete|remove|pay|refund|approve|check\s*in|check\s*out|transfer|extend|assign|send|schedule)\b",
        re.IGNORECASE,
    )

    _ID_PATTERNS = {
        "booking_id": re.compile(r"\b(?:booking|reservation)(?:\s+(?:id|no|number)\s*[:#-]?\s*|\s*[:#-]\s*)([A-Z0-9][A-Z0-9_-]{2,})\b", re.I),
        "customer_id": re.compile(r"\b(?:customer|guest)\s*(?:id|no|number)?\s*[:#-]?\s*([A-Z0-9][A-Z0-9_-]{2,})\b", re.I),
        "invoice_id": re.compile(r"\b(?:invoice|bill)\s*(?:id|no|number)?\s*[:#-]?\s*([A-Z0-9][A-Z0-9_-]{2,})\b", re.I),
        "order_id": re.compile(r"\b(?:order)\s*(?:id|no|number)?\s*[:#-]?\s*([A-Z0-9][A-Z0-9_-]{2,})\b", re.I),
        "room_number": re.compile(r"\broom\s*(?:number|no)?\s*[:#-]?\s*([A-Z0-9][A-Z0-9_-]{0,9})\b", re.I),
        "media_id": re.compile(r"\bmedia\s*(?:id|no|number)?\s*[:#-]?\s*([A-Z0-9][A-Z0-9_-]{2,})\b", re.I),
        "feedback_id": re.compile(r"\bfeedback\s*(?:id|no|number)?\s*[:#-]?\s*([A-Z0-9][A-Z0-9_-]{2,})\b", re.I),
        "request_id": re.compile(r"\b(?:request|transport)(?:\s+(?:id|no|number)\s*[:#-]?\s*|\s*[:#-]\s*)([A-Z0-9][A-Z0-9_-]{2,})\b", re.I),
    }

    def decide_intent(self, message: str) -> IntentDecision:
        text = " ".join(str(message or "").strip().lower().split())
        if not text:
            return IntentDecision("unknown", (), {}, "none")

        action_required = bool(self._ACTION_WORDS.search(text))
        # Receptionist information requests such as "check-in time" or
        # "check-out information" must not be treated as operational actions.
        informational_checkin = bool(
            re.search(
                r"\b(?:check\s*-?\s*in|checkin|check\s*-?\s*out|checkout)\b.*\b(?:time|timing|information|policy|policies|hour|hours)\b",
                text,
                re.IGNORECASE,
            )
            or re.search(
                r"\b(?:what time|when can i|when is|tell me).*(?:check\s*-?\s*in|checkin|check\s*-?\s*out|checkout)\b",
                text,
                re.IGNORECASE,
            )
        )
        if informational_checkin:
            action_required = False

        matched: list[str] = []
        for tool_name, phrases in self._INTENT_RULES:
            if any(phrase in text for phrase in phrases):
                matched.append(tool_name)

        # More specific identifiers refine the otherwise broad booking/billing/etc. intent.
        args = self._extract_arguments(text)
        if "booking_id" in args and "room_booking_information" not in matched:
            matched.insert(0, "room_booking_information")
        if "customer_id" in args and "guest_information" not in matched:
            matched.insert(0, "guest_information")
        if "invoice_id" in args and "billing_information" not in matched:
            matched.insert(0, "billing_information")
        if "order_id" in args and "restaurant_information" not in matched:
            matched.insert(0, "restaurant_information")

        if not matched and action_required:
            if any(word in text for word in ("book", "reserve", "reservation")):
                action_intent = "room_booking_action"
            elif "table" in text:
                action_intent = "table_booking_action"
            elif any(word in text for word in ("order", "food")):
                action_intent = "restaurant_action"
            elif any(word in text for word in ("pay", "refund", "invoice")):
                action_intent = "billing_action"
            else:
                action_intent = "hotel_action"
            return IntentDecision(action_intent, (), args, "medium", True)

        if not matched:
            return IntentDecision("unknown", (), args, "none", action_required)

        # Keep orchestration bounded. The first three matching tools are enough for
        # compound informational requests without turning a single message into a
        # broad data dump.
        tool_names = tuple(dict.fromkeys(matched))[:3]
        return IntentDecision("multi_tool" if len(tool_names) > 1 else tool_names[0], tool_names, args, "high", action_required)

    def _extract_arguments(self, text: str) -> dict:
        args: dict = {}
        for key, pattern in self._ID_PATTERNS.items():
            match = pattern.search(text)
            if match:
                args[key] = match.group(1).strip().upper()

        if "low stock" in text or "low-stock" in text:
            args["low_stock_only"] = True
        if "nearby" in text:
            category_match = re.search(r"nearby\s+(?:places?|restaurants?|cafes?|hospitals?|attractions?)", text)
            if category_match:
                args["category"] = category_match.group(0).split()[-1]
        if "active media" in text:
            args["active_only"] = True

        # Only accept ISO dates explicitly present in the message. No current-date
        # guessing is performed by the agent core.
        iso_dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text)
        if iso_dates:
            args["start_date"] = iso_dates[0]
            args["check_in_date"] = iso_dates[0]
            if len(iso_dates) > 1:
                args["end_date"] = iso_dates[1]

        nights = re.search(r"\b(\d{1,3})\s+nights?\b", text)
        if nights:
            args["nights"] = int(nights.group(1))
        return args

    def _tool_arguments(self, tool_name: str, extracted: dict) -> dict:
        definition = get_tool_definition(tool_name)
        if definition is None:
            raise ValueError("Unknown AI tool.")
        allowed = set(definition["required_arguments"]) | set(definition["optional_arguments"])
        return {key: value for key, value in extracted.items() if key in allowed}

    def _user_for_tools(self, context: AIRequestContext) -> dict:
        return {
            "user_id": context.user_id,
            "username": context.username,
            "role": context.role,
            "hotel_id": context.hotel_id,
        }

    def _summarize_result(self, tool_name: str, result: dict) -> str:
        payload = result.get("result") if isinstance(result, dict) else result
        if not isinstance(payload, dict):
            return f"{tool_name} information retrieved successfully."
        if tool_name == "hotel_information":
            hotel = payload.get("hotel") or {}
            name = hotel.get("hotel_name") or hotel.get("name") or "the hotel"
            return f"I retrieved the available information for {name}."
        if tool_name == "room_availability":
            rooms = payload.get("available_rooms")
            if rooms is not None:
                return f"I found {len(rooms)} available room(s) for the requested stay."
            return f"I retrieved {len(payload.get('rooms') or [])} room record(s)."
        if tool_name == "guest_information":
            return "I retrieved the guest/customer information available within this hotel scope."
        if tool_name == "billing_information":
            return "I retrieved the billing/invoice information available within this hotel scope."
        if tool_name == "reports_summary":
            return "I retrieved the requested hotel analytics summary."
        return f"I retrieved {tool_name.replace('_', ' ')} information."

    def process(self, request: AIRequest) -> AIResponse:
        started = observability.start_timer()
        conversation_id = request.conversation_id
        observability.record_request(request.context, request.message, conversation_id)
        if len(request.message) > settings.max_input_characters:
            response = AIResponse(
                status="input_rejected",
                handled=False,
                message="The AI request exceeds the configured input limit.",
                provider=settings.provider,
                model=settings.model or None,
                hotel_id=request.context.hotel_id,
                conversation_id=conversation_id,
            )
            observability.record_response(request.context, response, observability.elapsed_ms(started))
            observability.record_error(request.context, "input_rejected", response.message, conversation_id)
            return response
            return AIResponse(
                status="input_rejected",
                handled=False,
                message="The AI request exceeds the configured input limit.",
                provider=settings.provider,
                model=settings.model or None,
                hotel_id=request.context.hotel_id,
                conversation_id=request.conversation_id,
            )

        conversation_id = request.conversation_id or f"conv_{uuid.uuid4().hex[:24]}"
        decision = self.decide_intent(request.message)
        if decision.intent == "unknown":
            response = AIResponse(
                status="unknown_intent",
                handled=False,
                message="I could not identify a supported hotel task from that request. Please specify what hotel information you need.",
                provider=settings.provider,
                model=settings.model or None,
                hotel_id=request.context.hotel_id,
                conversation_id=conversation_id,
                intent="unknown",
            )
            observability.record_response(request.context, response, observability.elapsed_ms(started))
            observability.record_conversation(request.context, conversation_id, "unknown_intent")
            return response

        if decision.action_required:
            response = AIResponse(
                status="confirmation_required",
                handled=False,
                message="This request appears to require a hotel action. I have not executed it. Confirmation and action execution are introduced in later Phase 8 layers.",
                provider=settings.provider,
                model=settings.model or None,
                hotel_id=request.context.hotel_id,
                conversation_id=conversation_id,
                intent=decision.intent,
                confirmation_required=True,
            )
            observability.record_response(request.context, response, observability.elapsed_ms(started))
            observability.record_action(request.context, "confirmation_required", "INFO", conversation_id)
            return response

        tool_calls = []
        messages = []
        user = self._user_for_tools(request.context)
        for tool_name in decision.tool_names:
            arguments = self._tool_arguments(tool_name, decision.arguments)
            tool_started = observability.start_timer()
            try:
                result = execute_ai_tool(tool_name, arguments, user=user)
            except (PermissionError, ValueError) as exc:
                tool_duration = observability.elapsed_ms(tool_started)
                tool_calls.append({"tool": tool_name, "status": "failed", "error": str(exc)})
                observability.record_tool(request.context, tool_name, "failed", tool_duration, conversation_id, str(exc))
                continue
            except Exception:
                tool_duration = observability.elapsed_ms(tool_started)
                tool_calls.append({"tool": tool_name, "status": "failed", "error": "Tool execution failed."})
                observability.record_tool(request.context, tool_name, "failed", tool_duration, conversation_id, "Tool execution failed.")
                continue
            tool_duration = observability.elapsed_ms(tool_started)
            tool_calls.append({"tool": tool_name, "status": "success", "arguments": arguments})
            observability.record_tool(request.context, tool_name, "success", tool_duration, conversation_id)
            messages.append(self._summarize_result(tool_name, result))

        successful = [call for call in tool_calls if call["status"] == "success"]
        failed = [call for call in tool_calls if call["status"] == "failed"]
        if not successful:
            status = "tool_execution_failed"
            message = "I identified the request, but the required hotel information could not be retrieved."
            handled = False
        else:
            status = "handled_with_tool" if not failed else "partially_handled"
            message = " ".join(messages)
            if failed:
                message += " Some requested information could not be retrieved."

            # Gemini is a response-generation layer only. Tool execution and
            # hotel data access remain inside the existing controlled tool layer.
            gemini = get_gemini_provider()
            if gemini is not None:
                try:
                    message = gemini.generate_reply(
                        user_message=request.message,
                        tool_summaries=messages,
                        hotel_id=request.context.hotel_id,
                    )
                except Exception as exc:
                    observability.record_error(
                        request.context,
                        "ai_provider_error",
                        str(exc),
                        conversation_id,
                    )
            handled = True

        response = AIResponse(
            status=status,
            handled=handled,
            message=message,
            provider=settings.provider,
            model=settings.model or None,
            hotel_id=request.context.hotel_id,
            conversation_id=conversation_id,
            intent=decision.intent,
            tool_calls=tuple(tool_calls),
        )
        duration = observability.elapsed_ms(started)
        observability.record_response(request.context, response, duration)
        observability.record_performance(request.context, "ai_agent_process", duration, conversation_id)
        if failed:
            observability.record_error(request.context, "tool_execution_failed", "One or more AI tools failed.", conversation_id)
        return response


class AIService:
    """Stable public service boundary around the Phase 8.3 agent core."""

    def __init__(self, agent: AIAgentCore | None = None):
        self.agent = agent or AIAgentCore()

    def process(self, request: AIRequest) -> AIResponse:
        response = self.agent.process(request)
        # Keep the original Phase 8.1 response for a generic message when no
        # model provider is configured, while allowing Phase 8.3 deterministic
        # hotel intents to run through the controlled tool layer.
        if not settings.enabled and response.status == "unknown_intent":
            return AIResponse(
                status="foundation_ready",
                handled=False,
                message="AI provider is not configured. AI agent core and tool orchestration are ready for provider integration.",
                provider=settings.provider,
                model=settings.model or None,
                hotel_id=request.context.hotel_id,
                conversation_id=request.conversation_id,
            )
        return response


service = AIService()
