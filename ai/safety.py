"""AI safety, permission and guardrail boundary for Phase 8.14.

This module is provider-neutral and deliberately conservative. It validates the
request before AI/business execution, blocks common prompt-injection attempts,
requires confirmation for mutating/destructive/payment actions, preserves the
authenticated hotel scope, and provides safe output redaction plus audit hooks.
"""
from dataclasses import asdict, dataclass
import re
import uuid

from database.audit_db import log_activity
from database.permission_db import has_permission


@dataclass(frozen=True)
class GuardrailDecision:
    allowed: bool
    status: str
    reason: str
    confirmation_required: bool = False
    human_approval_required: bool = False
    action_class: str = "read"

    def to_dict(self):
        return asdict(self)


# Conservative patterns: these are indicators, not claims about user intent.
_INJECTION_PATTERNS = (
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions", re.I),
    re.compile(r"(?:system|developer)\s+message\s*[:：]", re.I),
    re.compile(r"reveal\s+(?:your|the)\s+(?:system|developer)\s+prompt", re.I),
    re.compile(r"bypass\s+(?:security|permission|authorization|rbac)", re.I),
    re.compile(r"disable\s+(?:audit|logging|security|permissions)", re.I),
    re.compile(r"execute\s+(?:arbitrary|raw)\s+(?:sql|code)", re.I),
)

_SENSITIVE_KEYS = {
    "password", "password_hash", "token", "access_token", "refresh_token",
    "secret", "api_key", "apikey", "authorization", "jwt", "private_key",
}

_ACTION_PATTERNS = (
    ("payment", re.compile(r"\b(?:pay|payment|charge|refund)\b", re.I)),
    ("destructive", re.compile(r"\b(?:delete|remove|destroy|purge|drop)\b", re.I)),
    ("approval", re.compile(r"\b(?:approve|approval)\b", re.I)),
    ("booking", re.compile(r"\b(?:book|reserve|cancel|modify|transfer|extend|check\s*in|check\s*out)\b", re.I)),
    ("mutation", re.compile(r"\b(?:create|add|update|change|assign|send|schedule|mark)\b", re.I)),
)

_ACTION_PERMISSIONS = {
    "payment": ("Hotel", "Payment"),
    "destructive": ("Hotel", "Delete"),
    "approval": ("Hotel", "Approve"),
    "booking": ("Rooms", "Create"),
    "mutation": ("Hotel", "Update"),
}


def _classify_action(message: str) -> str:
    text = str(message or "")
    for kind, pattern in _ACTION_PATTERNS:
        if pattern.search(text):
            return kind
    return "read"


def contains_prompt_injection(message: str) -> bool:
    return any(pattern.search(str(message or "")) for pattern in _INJECTION_PATTERNS)


def sanitize_sensitive(value):
    """Return a JSON-safe copy with credential/secret-like fields redacted."""
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if str(key).strip().lower() in _SENSITIVE_KEYS:
                result[key] = "[REDACTED]"
            else:
                result[key] = sanitize_sensitive(item)
        return result
    if isinstance(value, list):
        return [sanitize_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_sensitive(item) for item in value)
    return value


class AISafetyGuardrails:
    def _audit(self, context, action, status, details):
        try:
            log_activity(
                module="AI",
                action=action,
                record_type="AI_GUARDRAIL",
                record_id=str(uuid.uuid4()),
                status=status,
                details=details,
                actor_user_id=context.user_id,
                actor_username=context.username,
                actor_role=context.role,
                hotel_id=context.hotel_id,
            )
        except Exception:
            # Safety must not fail open because audit storage is unavailable.
            return None
        return True

    def validate(self, *, message, context, confirm=False, human_approved=False,
                 action_type=None, require_permission=True) -> GuardrailDecision:
        text = str(message or "").strip()
        if not text:
            return GuardrailDecision(False, "input_rejected", "AI message is required.")

        if contains_prompt_injection(text):
            decision = GuardrailDecision(False, "guardrail_blocked", "The request contains an unsafe instruction pattern.")
            self._audit(context, "OTHER", "FAILED", decision.reason)
            return decision

        action_class = action_type or _classify_action(text)
        if action_class not in {"read", "payment", "destructive", "approval", "booking", "mutation"}:
            action_class = "read"

        if action_class != "read" and require_permission:
            module, permission_action = _ACTION_PERMISSIONS[action_class]
            if not has_permission(context.user_id, module, permission_action):
                decision = GuardrailDecision(False, "permission_denied", f"Permission denied: {module} - {permission_action}.", action_class=action_class)
                self._audit(context, "OTHER", "FAILED", decision.reason)
                return decision

        # Payment/destructive/approval always require explicit human approval;
        # booking/mutation require user confirmation.
        if action_class in {"payment", "destructive", "approval"} and not human_approved:
            decision = GuardrailDecision(False, "human_approval_required", "Human approval is required for this action.", True, True, action_class)
            self._audit(context, "OTHER", "INFO", decision.reason)
            return decision
        if action_class in {"booking", "mutation"} and not confirm:
            decision = GuardrailDecision(False, "confirmation_required", "Explicit confirmation is required before this action.", True, False, action_class)
            self._audit(context, "OTHER", "INFO", decision.reason)
            return decision

        decision = GuardrailDecision(True, "allowed", "AI request passed safety guardrails.", False, False, action_class)
        self._audit(context, "OTHER", "SUCCESS", decision.reason)
        return decision

    def validate_hotel_scope(self, context, requested_hotel_id=None):
        if requested_hotel_id is not None and int(requested_hotel_id) != int(context.hotel_id):
            decision = GuardrailDecision(False, "hotel_scope_blocked", "Requested hotel scope does not match the authenticated hotel context.")
            self._audit(context, "OTHER", "FAILED", decision.reason)
            return decision
        return GuardrailDecision(True, "allowed", "Hotel scope validated.")

    def registry(self):
        return {
            "action_classes": ["read", "booking", "mutation", "approval", "payment", "destructive"],
            "confirmation_required": ["booking", "mutation", "approval", "payment", "destructive"],
            "human_approval_required": ["approval", "payment", "destructive"],
            "protections": [
                "role_based_permissions", "hotel_scope", "sensitive_data_redaction",
                "confirmation_gate", "human_approval_gate", "prompt_injection_detection",
                "audit_logging", "safe_error_boundary",
            ],
        }


safety_guardrails = AISafetyGuardrails()
