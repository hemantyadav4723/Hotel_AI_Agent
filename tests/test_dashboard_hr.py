from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_hr_route_exposes_designations_and_summary():
    text = (ROOT / "api" / "routes" / "hr.py").read_text(encoding="utf-8")
    assert '"/designations"' in text
    assert '"/hr/summary"' in text
    assert 'require_permission("Staff", "View")' in text

def test_dashboard_hr_renders_all_required_sections():
    text = (ROOT / "dashboard" / "app.js").read_text(encoding="utf-8")
    for term in ["Staff List & Profiles", "Departments", "Designations", "Attendance", "Leave", "Staff Status", "Salary", "Payroll", "HR Operational Summary"]:
        assert term in text
