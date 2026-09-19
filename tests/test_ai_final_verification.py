from pathlib import Path

from ai.final_verification import (
    EXPECTED_AI_MODULES,
    EXPECTED_TEST_MODULES,
    REQUIRED_AI_ROUTES,
    run_final_checks,
    verify_ai_routes_are_auth_protected,
    verify_context_contract,
    verify_core_to_tool_workflow,
    verify_expected_modules,
    verify_expected_tests,
    verify_no_direct_sqlite_in_ai_modules,
)

ROOT = Path(__file__).resolve().parents[1]


def test_01_all_phase8_ai_modules_are_present():
    result = verify_expected_modules()
    assert result.passed, result.detail
    assert EXPECTED_AI_MODULES <= {p.name for p in (ROOT / "ai").glob("*.py")}


def test_02_all_phase8_ai_test_modules_are_present():
    result = verify_expected_tests()
    assert result.passed, result.detail
    assert EXPECTED_TEST_MODULES <= {p.name for p in (ROOT / "tests").glob("test_ai_*.py")}


def test_03_ai_service_modules_keep_sqlite_boundary():
    result = verify_no_direct_sqlite_in_ai_modules()
    assert result.passed, result.detail


def test_04_ai_api_surface_is_auth_protected():
    result = verify_ai_routes_are_auth_protected()
    assert result.passed, result.detail
    assert result.detail.startswith("routes=")


def test_05_context_contract_preserves_hotel_and_user_scope():
    result = verify_context_contract()
    assert result.passed, result.detail


def test_06_core_to_tool_workflow_preserves_conversation_and_hotel_scope():
    result = verify_core_to_tool_workflow()
    assert result.passed, result.detail


def test_07_final_check_suite_is_all_green():
    results = run_final_checks()
    assert all(item.passed for item in results), [item.__dict__ for item in results if not item.passed]
