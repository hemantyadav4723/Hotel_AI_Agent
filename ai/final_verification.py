"""Final Phase 8 verification helpers.

This module provides deterministic, provider-neutral checks for the completed
AI architecture. It verifies that the expected AI modules, test coverage,
protected API surface, hotel/user context boundaries, and production
readiness artifacts are present without creating a second business layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]
AI_DIR = ROOT / "ai"
TEST_DIR = ROOT / "tests"

EXPECTED_AI_MODULES = {
    "config.py", "context.py", "service.py", "booking.py", "communication.py",
    "voice.py", "guest_service.py", "receptionist.py", "staff_assistant.py",
    "automation.py", "proactive_notifications.py", "personalization.py",
    "multilingual.py", "safety.py", "memory.py", "knowledge.py", "integration.py",
    "handoff.py", "observability.py", "production.py",
}

EXPECTED_TEST_MODULES = {
    "test_ai_foundation.py", "test_ai_tools_architecture.py", "test_ai_agent_core.py",
    "test_ai_receptionist.py", "test_ai_guest_service.py", "test_ai_booking.py",
    "test_ai_communication.py", "test_ai_voice.py", "test_ai_staff_assistant.py",
    "test_ai_automation.py", "test_ai_proactive_notifications.py", "test_ai_personalization.py",
    "test_ai_multilingual.py", "test_ai_safety.py", "test_ai_memory.py", "test_ai_knowledge.py",
    "test_ai_integration.py", "test_ai_handoff.py", "test_ai_observability.py",
    "test_ai_testing.py", "test_ai_production.py", "test_ai_final_verification.py",
}

REQUIRED_AI_ROUTES = {
    "/api/v1/ai/status", "/api/v1/ai/context", "/api/v1/ai/request", "/api/v1/ai/receptionist",
    "/api/v1/ai/guest-service", "/api/v1/ai/booking", "/api/v1/ai/communication",
    "/api/v1/ai/voice", "/api/v1/ai/staff-assistant", "/api/v1/ai/automation",
    "/api/v1/ai/proactive-notifications/trigger", "/api/v1/ai/personalization",
    "/api/v1/ai/multilingual", "/api/v1/ai/safety/validate", "/api/v1/ai/memory",
    "/api/v1/ai/knowledge", "/api/v1/ai/integrations/ai", "/api/v1/ai/handoff/request",
    "/api/v1/ai/observability/history", "/api/v1/ai/tools",
}


@dataclass(frozen=True)
class VerificationResult:
    name: str
    passed: bool
    detail: str


def verify_expected_modules() -> VerificationResult:
    actual = {p.name for p in AI_DIR.glob("*.py")}
    missing = sorted(EXPECTED_AI_MODULES - actual)
    return VerificationResult("ai_modules", not missing, "missing=" + ",".join(missing) if missing else "all expected AI modules present")


def verify_expected_tests() -> VerificationResult:
    actual = {p.name for p in TEST_DIR.glob("test_ai_*.py")}
    missing = sorted(EXPECTED_TEST_MODULES - actual)
    return VerificationResult("ai_test_modules", not missing, "missing=" + ",".join(missing) if missing else "all expected AI test modules present")


def verify_no_direct_sqlite_in_ai_modules() -> VerificationResult:
    violations: list[str] = []
    for path in AI_DIR.glob("*.py"):
        source = path.read_text(encoding="utf-8").lower()
        if path.name in {"production.py", "final_verification.py"}:
            continue
        if "import sqlite3" in source or "from sqlite3" in source:
            violations.append(path.name)
    return VerificationResult("ai_sql_boundary", not violations, "violations=" + ",".join(violations) if violations else "no direct sqlite3 imports in AI service modules")


def verify_ai_routes_are_auth_protected() -> VerificationResult:
    route_file = ROOT / "api" / "routes" / "ai.py"
    tree = ast.parse(route_file.read_text(encoding="utf-8"), filename=str(route_file))
    protected = 0
    route_paths: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        decorators = [d for d in node.decorator_list if isinstance(d, ast.Call)]
        route_deps = []
        for decorator in decorators:
            if isinstance(decorator.func, ast.Attribute) and decorator.func.attr in {"get", "post", "put", "delete", "patch"}:
                if decorator.args and isinstance(decorator.args[0], ast.Constant):
                    route_deps.append(str(decorator.args[0].value))
        if not route_deps:
            continue
        route_paths.update("/api/v1/ai" + p for p in route_deps)
        if any("get_current_user" in ast.unparse(default) for default in node.args.defaults):
            protected += 1
        elif any("get_current_user" in ast.unparse(default) for default in node.args.kw_defaults if default is not None):
            protected += 1
    missing = sorted(REQUIRED_AI_ROUTES - route_paths)
    # Every discovered AI route is expected to carry the current-user dependency.
    total_routes = len(route_paths)
    passed = not missing and protected == total_routes
    detail = f"routes={total_routes}, protected={protected}, missing_required={missing}"
    return VerificationResult("ai_route_auth", passed, detail)


def verify_context_contract() -> VerificationResult:
    from ai.context import AIRequestContext
    ctx = AIRequestContext.from_user({"user_id": "u1", "username": "tester", "role": "Manager", "hotel_id": 7})
    passed = ctx.hotel_id == 7 and ctx.user_id == "u1" and ctx.role == "Manager" and ctx.public_dict()["hotel_id"] == 7
    return VerificationResult("context_contract", passed, str(ctx.public_dict()))


def verify_core_to_tool_workflow() -> VerificationResult:
    from ai.context import AIRequestContext
    from ai.service import AIAgentCore, AIRequest
    response = AIAgentCore().process(AIRequest("show hotel information", AIRequestContext("u1", "tester", "Manager", 1), "final-e2e"))
    passed = response.conversation_id == "final-e2e" and response.hotel_id == 1 and response.tool_calls
    return VerificationResult("core_tool_workflow", bool(passed), f"status={response.status}, tools={len(response.tool_calls)}")


def run_final_checks() -> list[VerificationResult]:
    return [
        verify_expected_modules(),
        verify_expected_tests(),
        verify_no_direct_sqlite_in_ai_modules(),
        verify_ai_routes_are_auth_protected(),
        verify_context_contract(),
        verify_core_to_tool_workflow(),
    ]
