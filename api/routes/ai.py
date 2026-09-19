from fastapi import APIRouter, Depends, HTTPException

from api.common import json_safe
from api.dependencies import get_current_user
from api.schemas import AIRequest, AICommunicationRequest, AIReceptionistRequest, AIGuestServiceRequest, AIBookingAutomationRequest, AIVoiceRequest, AIStaffAssistantRequest, AIAutomationRequest, AIProactiveNotificationRequest, AIPersonalizationRequest, AIMultilingualRequest, AISafetyRequest, AIMemoryRequest, AIHotelKnowledgeRequest, AIIntegrationConfigRequest, AIIntegrationExecuteRequest, AIIntegrationAIRequest, AIIntegrationWebhookRequest, AIHandoffDetectRequest, AIHandoffRequest, AIHandoffAssignRequest, AIHandoffTakeoverRequest, AIHandoffResolveRequest, AIHandoffConversationRequest, ToolRequest
from ai.config import settings as ai_settings
from ai.context import AIRequestContext
from ai.service import AIRequest as AIServiceRequest, service as ai_service
from ai.receptionist import receptionist
from ai.guest_service import guest_service_agent
from ai.booking import booking_automation, BookingItem
from ai.communication import CommunicationRequest, gateway as communication_gateway
from ai.voice import VoiceRequest, voice_agent
from ai.staff_assistant import staff_assistant
from ai.automation import automation_engine
from ai.proactive_notifications import proactive_notification_engine
from ai.multilingual import multilingual_agent
from ai.safety import safety_guardrails, sanitize_sensitive
from ai.memory import memory_service
from ai.integration import integration_hub
from ai.handoff import human_handoff
from ai.observability import observability
from database.ai_tools_db import get_tool_registry, get_tool_definition, execute_ai_tool

router = APIRouter(prefix="/ai", tags=["AI Agent"])


@router.get("/status")
def ai_status(user=Depends(get_current_user)):
    return {
        "data": {
            "enabled": ai_settings.enabled,
            "provider": ai_settings.provider,
            "model": ai_settings.model or None,
            "status": "ready" if ai_settings.enabled and ai_settings.provider != "none" else "foundation_ready",
            "hotel_id": int(user["hotel_id"]),
        }
    }


@router.get("/context")
def ai_context(user=Depends(get_current_user)):
    context = AIRequestContext.from_user(user)
    return {"data": context.public_dict()}


@router.post("/request")
def ai_request(payload: AIRequest, user=Depends(get_current_user)):
    request = AIServiceRequest(
        message=payload.message,
        context=AIRequestContext.from_user(user),
        conversation_id=payload.conversation_id,
    )
    response = ai_service.process(request)
    return {"data": response.to_dict()}


@router.post("/receptionist")
def ai_receptionist(payload: AIReceptionistRequest, user=Depends(get_current_user)):
    response = receptionist.process(
        message=payload.message,
        context=AIRequestContext.from_user(user),
        conversation_id=payload.conversation_id,
    )
    return {"data": response.to_dict()}


@router.get("/communication/channels")
def communication_channels(user=Depends(get_current_user)):
    return {"data": communication_gateway.channel_registry()}


@router.post("/communication")
def ai_communication(payload: AICommunicationRequest, user=Depends(get_current_user)):
    try:
        response = communication_gateway.process(
            CommunicationRequest(
                message=payload.message,
                context=AIRequestContext.from_user(user),
                channel=payload.channel,
                conversation_id=payload.conversation_id,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": response.to_dict()}


@router.get("/voice/use-cases")
def voice_use_cases(user=Depends(get_current_user)):
    return {"data": voice_agent.use_case_registry()}


@router.post("/voice")
def ai_voice(payload: AIVoiceRequest, user=Depends(get_current_user)):
    try:
        response = voice_agent.process(
            VoiceRequest(
                context=AIRequestContext.from_user(user),
                input_type=payload.input_type,
                transcript=payload.transcript,
                audio_reference=payload.audio_reference,
                conversation_id=payload.conversation_id,
                use_case=payload.use_case,
                handoff_requested=payload.handoff_requested,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": response.to_dict()}


@router.get("/staff-assistant/areas")
def staff_assistant_areas(user=Depends(get_current_user)):
    return {
        "data": {
            "role": user["role"],
            "areas": staff_assistant.area_registry(user["role"]),
        }
    }


@router.post("/staff-assistant")
def ai_staff_assistant(payload: AIStaffAssistantRequest, user=Depends(get_current_user)):
    try:
        response = staff_assistant.process(
            message=payload.message,
            context=AIRequestContext.from_user(user),
            assistant_area=payload.assistant_area,
            conversation_id=payload.conversation_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": response.to_dict()}


@router.get("/safety/registry")
def ai_safety_registry(user=Depends(get_current_user)):
    return {"data": safety_guardrails.registry()}


@router.post("/safety/validate")
def ai_safety_validate(payload: AISafetyRequest, user=Depends(get_current_user)):
    context = AIRequestContext.from_user(user)
    scope = safety_guardrails.validate_hotel_scope(context, payload.requested_hotel_id)
    if not scope.allowed:
        raise HTTPException(status_code=403, detail=scope.reason)
    decision = safety_guardrails.validate(
        message=payload.message, context=context, confirm=payload.confirm,
        human_approved=payload.human_approved,
    )
    status_code = 200 if decision.allowed else (403 if decision.status in {"permission_denied", "guardrail_blocked", "hotel_scope_blocked"} else 409)
    if not decision.allowed:
        raise HTTPException(status_code=status_code, detail=decision.reason)
    return {"data": decision.to_dict()}


@router.post("/memory")
def ai_memory(payload: AIMemoryRequest, user=Depends(get_current_user)):
    try:
        response = memory_service.process(
            message=payload.message,
            context=AIRequestContext.from_user(user),
            conversation_id=payload.conversation_id,
            customer_id=payload.customer_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": response.to_dict()}

@router.get("/memory/{conversation_id}")
def ai_memory_context(conversation_id: str, user=Depends(get_current_user)):
    try:
        context = AIRequestContext.from_user(user)
        data = memory_service.build_context(context=context, conversation_id=conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": data}


@router.get("/tools")
def tools(user=Depends(get_current_user)):
    return {"data": get_tool_registry()}


@router.get("/tools/{tool_name}")
def tool_definition(tool_name: str, user=Depends(get_current_user)):
    definition = get_tool_definition(tool_name)
    if definition is None:
        raise HTTPException(status_code=404, detail="AI tool not found.")
    return {"data": definition}


@router.post("/guest-service")
def ai_guest_service(payload: AIGuestServiceRequest, user=Depends(get_current_user)):
    try:
        response = guest_service_agent.process(
            message=payload.message,
            context=AIRequestContext.from_user(user),
            conversation_id=payload.conversation_id,
            guest_name=payload.guest_name,
            customer_id=payload.customer_id,
            room_number=payload.room_number,
            priority=payload.priority,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": response.to_dict()}


@router.post("/booking")
def ai_booking_automation(payload: AIBookingAutomationRequest, user=Depends(get_current_user)):
    try:
        response = booking_automation.process(
            message=payload.message,
            context=AIRequestContext.from_user(user),
            conversation_id=payload.conversation_id,
            booking_type=payload.booking_type,
            confirm=payload.confirm,
            guest_name=payload.guest_name,
            guest_mobile=payload.guest_mobile,
            guest_email=payload.guest_email,
            customer_id=payload.customer_id,
            room_number=payload.room_number,
            check_in_date=payload.check_in_date,
            nights=payload.nights,
            advance_amount=payload.advance_amount,
            payment_method=payload.payment_method,
            adults=payload.adults,
            children=payload.children,
            notes=payload.notes,
            table_number=payload.table_number,
            booking_date=payload.booking_date,
            booking_time=payload.booking_time,
            persons=payload.persons,
            items=[BookingItem(item.item_id, item.quantity) for item in payload.items],
            transportation_type=payload.transportation_type,
            pickup_date=payload.pickup_date,
            pickup_time=payload.pickup_time,
            pickup_location=payload.pickup_location,
            drop_location=payload.drop_location,
            vehicle_id=payload.vehicle_id,
            vehicle_type=payload.vehicle_type,
            driver_id=payload.driver_id,
            fare=payload.fare,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": response.to_dict()}


@router.post("/automation")
def ai_automation(payload: AIAutomationRequest, user=Depends(get_current_user)):
    try:
        response = automation_engine.process(
            message=payload.message,
            context=AIRequestContext.from_user(user),
            automation_type=payload.automation_type,
            confirm=payload.confirm,
            conversation_id=payload.conversation_id,
            workflow=payload.workflow,
            payload=payload.payload,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": response.to_dict()}


@router.get("/proactive-notifications/triggers")
def ai_proactive_triggers(user=Depends(get_current_user)):
    return {"data": proactive_notification_engine.available_triggers()}


@router.post("/proactive-notifications/trigger")
def ai_proactive_notification(payload: AIProactiveNotificationRequest, user=Depends(get_current_user)):
    try:
        response = proactive_notification_engine.trigger(
            trigger=payload.trigger,
            hotel_id=int(user["hotel_id"]),
            user_id=user["user_id"],
            payload=payload.payload,
            confirm=payload.confirm,
            conversation_id=payload.conversation_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": response.to_dict()}


@router.get("/proactive-notifications/status")
def ai_proactive_notification_status(event_id: str | None = None, reference_id: str | None = None, limit: int = 50, user=Depends(get_current_user)):
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200.")
    rows = proactive_notification_engine.status(
        hotel_id=int(user["hotel_id"]), event_id=event_id, reference_id=reference_id, limit=limit
    )
    return {"data": json_safe(rows)}


@router.post("/tools/{tool_name}/execute")
def execute_tool(tool_name: str, payload: ToolRequest, user=Depends(get_current_user)):
    definition = get_tool_definition(tool_name)
    if definition is None:
        raise HTTPException(status_code=404, detail="AI tool not found.")
    try:
        result = execute_ai_tool(tool_name, payload.arguments, user=user)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"tool": tool_name, "data": sanitize_sensitive(json_safe(result))}

@router.post("/personalization")
def ai_personalization(payload: AIPersonalizationRequest, user=Depends(get_current_user)):
    try:
        from ai.personalization import personalization_service
        response = personalization_service.build(
            context=AIRequestContext.from_user(user),
            customer_id=payload.customer_id,
            special_occasions=payload.special_occasions,
            communication_channel=payload.communication_channel,
            communication_purpose=payload.communication_purpose,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": response.to_dict()}


@router.get("/multilingual/languages")
def multilingual_languages(user=Depends(get_current_user)):
    return {"data": multilingual_agent.language_registry()}


@router.post("/multilingual")
def ai_multilingual(payload: AIMultilingualRequest, user=Depends(get_current_user)):
    try:
        response = multilingual_agent.process(
            message=payload.message,
            context=AIRequestContext.from_user(user),
            language=payload.language,
            conversation_id=payload.conversation_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": response.to_dict()}

@router.get("/knowledge/sections")
def ai_knowledge_sections(user=Depends(get_current_user)):
    from ai.knowledge import hotel_knowledge_service
    return {"data": hotel_knowledge_service.section_registry()}


@router.post("/knowledge")
def ai_knowledge(payload: AIHotelKnowledgeRequest, user=Depends(get_current_user)):
    from ai.knowledge import hotel_knowledge_service
    try:
        response = hotel_knowledge_service.build(
            context=AIRequestContext.from_user(user),
            section=payload.section,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": response.to_dict()}


@router.get("/handoff/registry")
def ai_handoff_registry(user=Depends(get_current_user)):
    return {"data": human_handoff.registry()}


@router.post("/handoff/detect")
def ai_handoff_detect(payload: AIHandoffDetectRequest, user=Depends(get_current_user)):
    try:
        decision = human_handoff.detect(payload.message, payload.requested, payload.priority)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": decision.to_dict()}


@router.post("/handoff/request")
def ai_handoff_request(payload: AIHandoffRequest, user=Depends(get_current_user)):
    try:
        record = human_handoff.request(AIRequestContext.from_user(user), payload.conversation_id, payload.reason, payload.priority, payload.target, payload.context)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": record.to_dict()}


@router.post("/handoff/assign")
def ai_handoff_assign(payload: AIHandoffAssignRequest, user=Depends(get_current_user)):
    try:
        record = human_handoff.assign(AIRequestContext.from_user(user), payload.conversation_id, payload.human_user_id, payload.target)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": record.to_dict()}


@router.post("/handoff/takeover")
def ai_handoff_takeover(payload: AIHandoffTakeoverRequest, user=Depends(get_current_user)):
    try:
        record = human_handoff.takeover(AIRequestContext.from_user(user), payload.conversation_id, payload.human_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": record.to_dict()}


@router.post("/handoff/resolve")
def ai_handoff_resolve(payload: AIHandoffResolveRequest, user=Depends(get_current_user)):
    try:
        record = human_handoff.resolve(AIRequestContext.from_user(user), payload.conversation_id, payload.resolution, payload.context)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": record.to_dict()}


@router.post("/handoff/cancel")
def ai_handoff_cancel(payload: AIHandoffConversationRequest, user=Depends(get_current_user)):
    try:
        record = human_handoff.cancel(AIRequestContext.from_user(user), payload.conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": record.to_dict()}


@router.post("/handoff/status")
def ai_handoff_status(payload: AIHandoffConversationRequest, user=Depends(get_current_user)):
    try:
        record = human_handoff.get(AIRequestContext.from_user(user), payload.conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"data": record.to_dict()}


@router.get("/integrations")
def ai_integrations(user=Depends(get_current_user)):
    return {"data": integration_hub.integration_registry()}


@router.get("/integrations/status")
def ai_integration_status(integration: str | None = None, user=Depends(get_current_user)):
    try:
        data = integration_hub.status(AIRequestContext.from_user(user), integration)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": data}


@router.post("/integrations/configure")
def ai_integration_configure(payload: AIIntegrationConfigRequest, user=Depends(get_current_user)):
    try:
        config = integration_hub.configure(
            context=AIRequestContext.from_user(user),
            integration=payload.integration,
            provider=payload.provider,
            enabled=payload.enabled,
            configured=payload.configured,
            credential_reference=payload.credential_reference,
            endpoint=payload.endpoint,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": config.public_dict()}


@router.post("/integrations/execute")
def ai_integration_execute(payload: AIIntegrationExecuteRequest, user=Depends(get_current_user)):
    try:
        result = integration_hub.execute(
            context=AIRequestContext.from_user(user),
            integration=payload.integration,
            operation=payload.operation,
            payload=payload.payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"data": result}


@router.post("/integrations/ai")
def ai_integration_process(payload: AIIntegrationAIRequest, user=Depends(get_current_user)):
    try:
        response = integration_hub.process_ai(
            context=AIRequestContext.from_user(user),
            integration=payload.integration,
            operation=payload.operation,
            message=payload.message,
            conversation_id=payload.conversation_id,
            payload=payload.payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": response.to_dict()}


@router.post("/integrations/webhook")
def ai_integration_webhook(payload: AIIntegrationWebhookRequest, user=Depends(get_current_user)):
    try:
        event = integration_hub.webhook(
            context=AIRequestContext.from_user(user),
            integration=payload.integration,
            event_type=payload.event_type,
            event_id=payload.event_id,
            payload=payload.payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": event.to_dict()}


@router.get("/observability/registry")
def ai_observability_registry(user=Depends(get_current_user)):
    return {"data": observability.registry()}


@router.get("/observability/history")
def ai_observability_history(conversation_id: str | None = None, event_type: str | None = None, limit: int = 100, user=Depends(get_current_user)):
    try:
        data = observability.history(AIRequestContext.from_user(user), conversation_id, event_type, limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": json_safe(data)}
