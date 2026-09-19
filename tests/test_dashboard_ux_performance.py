from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "dashboard" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "dashboard" / "styles.css").read_text(encoding="utf-8")
HTML = (ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")


def test_ux_foundations():
    for marker in ["@media(max-width:800px)", "@media(max-width:520px)", "class=\"table-wrap\"", "form-grid", "data-close", "toast(", "error-box", "empty", "loading"]:
        assert marker in (JS + CSS + HTML)


def test_reusable_pagination_foundation():
    assert "function paginatedTable(" in JS
    assert 'data-page-prev' in JS and 'data-page-next' in JS
    assert "role=\"navigation\" aria-label=\"Pagination\"" in JS
    assert "pageSize=25" in JS


def test_search_and_filters_exist():
    for marker in ["id=\"page-search\"", "data-audit-filter", "data-expense-filter", "data-feedback-filter", "data-transport-filter"]:
        assert marker in JS


def test_loading_success_error_empty_states():
    assert 'setAttribute("aria-busy","true")' in JS
    assert 'role="status" aria-live="polite"' in JS
    assert 'toast("Saved successfully.")' in JS
    assert 'class="error-box"' in JS
    assert 'No records found.' in JS


def test_parallel_independent_loading_is_preserved():
    assert "Promise.all([" in JS
    assert JS.count("Promise.all([") >= 5


def test_performance_request_timeout_and_optimized_rendering():
    assert "requestTimeoutMs" in JS
    assert "AbortController" in JS
    assert "encodeURIComponent" in JS
    assert "paginatedTable(rows" in JS
