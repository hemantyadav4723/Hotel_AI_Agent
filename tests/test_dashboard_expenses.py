from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "dashboard" / "app.js"
FINANCE = ROOT / "api" / "routes" / "finance.py"


def test_expense_dashboard_has_filters_and_reports():
    text = APP.read_text(encoding="utf-8")
    for token in (
        "Expense Management", "expense-start", "expense-end", "expense-search",
        "expense-category", "expense-payment", "expense-approval", "expense-recurring",
        "Category Report", "Payment Method Report", "Approval Report",
        "Recurring Expenses / Next Due", "data-expense-filter", "data-expense-clear",
    ):
        assert token in text


def test_expense_api_supports_filtering_and_summary():
    text = FINANCE.read_text(encoding="utf-8")
    for token in (
        '@router.get("/expenses")', '@router.get("/expenses/summary")',
        '@router.get("/expenses/categories")', '@router.get("/expenses/vendors")',
        '@router.get("/expenses/departments")', 'start_date', 'end_date',
        'approval_status', 'is_recurring', 'category_id', 'payment_method',
    ):
        assert token in text


def test_expense_creation_supports_enterprise_fields():
    text = FINANCE.read_text(encoding="utf-8")
    for token in (
        "ExpenseCreate", "category_id", "vendor_id", "payment_method",
        "receipt_reference", "department_id", "is_recurring",
        "recurrence_frequency", "recurrence_start_date",
    ):
        assert token in text


def test_expense_read_routes_require_expense_view_permission():
    text = FINANCE.read_text(encoding="utf-8")
    for route in (
        'def expenses(',
        'def expense_summary(',
        'def expense_categories(',
        'def expense_vendors(',
        'def expense_departments(',
    ):
        start = text.index(route)
        end = text.find('\n@router.', start + 1)
        block = text[start:] if end == -1 else text[start:end]
        assert 'require_permission("Expenses", "View")' in block
