from fastapi import APIRouter, Depends

from api.common import row_dict, rows_dict
from api.dependencies import get_current_user, require_permission
from database.database import get_connection
from database.hr_report_db import (
    staff_report, department_wise_staff_report, attendance_report, monthly_attendance_report,
    leave_report, salary_report, payroll_report, department_payroll_report,
    staff_cost_summary, active_inactive_staff_report, hr_dashboard,
)

router = APIRouter(tags=["Staff & HR"])

STAFF_VIEW = require_permission("Staff", "View")


def _table_rows(table: str, hotel_id: int, limit: int = 500):
    connection = get_connection()
    try:
        rows = connection.execute(f"SELECT * FROM {table} WHERE hotel_id = ? ORDER BY 1 LIMIT ?", (hotel_id, max(1, min(limit, 1000)))).fetchall()
    finally:
        connection.close()
    return rows


@router.get("/staff")
def staff(user=Depends(STAFF_VIEW), limit: int = 500):
    return {"data": rows_dict(_table_rows("staff", user["hotel_id"], limit))}


@router.get("/departments")
def departments(user=Depends(STAFF_VIEW)):
    return {"data": rows_dict(_table_rows("department", user["hotel_id"]))}


@router.get("/attendance")
def attendance(user=Depends(STAFF_VIEW), limit: int = 500):
    return {"data": rows_dict(_table_rows("attendance", user["hotel_id"], limit))}


@router.get("/leave")
def leave(user=Depends(STAFF_VIEW), limit: int = 500):
    return {"data": rows_dict(_table_rows("staff_leaves", user["hotel_id"], limit))}


@router.get("/salary")
def salary(user=Depends(STAFF_VIEW), limit: int = 500):
    return {"data": rows_dict(_table_rows("salary", user["hotel_id"], limit))}


@router.get("/payroll")
def payroll(user=Depends(STAFF_VIEW), limit: int = 500):
    return {"data": rows_dict(_table_rows("payroll", user["hotel_id"], limit))}




@router.get("/designations")
def designations(user=Depends(STAFF_VIEW)):
    return {"data": rows_dict(_table_rows("designation", user["hotel_id"]))}


@router.get("/hr/summary")
def hr_summary(user=Depends(STAFF_VIEW)):
    connection = get_connection()
    hotel_id = user["hotel_id"]
    try:
        staff = connection.execute("SELECT COUNT(*) FROM staff WHERE hotel_id = ?", (hotel_id,)).fetchone()[0]
        active = connection.execute("SELECT COUNT(*) FROM staff WHERE hotel_id = ? AND status IN ('New','Active','On Leave')", (hotel_id,)).fetchone()[0]
        separated = connection.execute("SELECT COUNT(*) FROM staff WHERE hotel_id = ? AND status IN ('Inactive','Resigned','Terminated')", (hotel_id,)).fetchone()[0]
        departments = connection.execute("SELECT COUNT(*) FROM department WHERE hotel_id = ? AND status = 'Active'", (hotel_id,)).fetchone()[0]
        designations = connection.execute("SELECT COUNT(*) FROM designation WHERE hotel_id = ? AND status = 'Active'", (hotel_id,)).fetchone()[0]
        pending_leave = connection.execute("SELECT COUNT(*) FROM staff_leaves WHERE hotel_id = ? AND status = 'Pending'", (hotel_id,)).fetchone()[0]
        attendance = connection.execute("SELECT COUNT(*) FROM attendance WHERE hotel_id = ?", (hotel_id,)).fetchone()[0]
        payroll = connection.execute("SELECT COUNT(*) FROM payroll WHERE hotel_id = ?", (hotel_id,)).fetchone()[0]
        monthly_cost = connection.execute("SELECT COALESCE(SUM(salary),0) FROM staff WHERE hotel_id = ? AND status IN ('New','Active','On Leave')", (hotel_id,)).fetchone()[0]
    finally:
        connection.close()
    return {"data": {"total_staff": staff, "active_staff": active, "separated_staff": separated, "departments": departments, "designations": designations, "pending_leave": pending_leave, "attendance_records": attendance, "payroll_records": payroll, "monthly_staff_cost": float(monthly_cost or 0)}}

@router.get("/hr/dashboard")
def hr_dashboard_api(user=Depends(STAFF_VIEW)):
    # Existing report functions are CLI-oriented, so the API exposes the
    # underlying normalized HR tables without duplicating report SQL.
    return {"data": {
        "staff": rows_dict(_table_rows("staff", user["hotel_id"])),
        "attendance": rows_dict(_table_rows("attendance", user["hotel_id"])),
        "leave": rows_dict(_table_rows("staff_leaves", user["hotel_id"])),
        "salary": rows_dict(_table_rows("salary", user["hotel_id"])),
        "payroll": rows_dict(_table_rows("payroll", user["hotel_id"])),
    }}
