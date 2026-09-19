from fastapi import APIRouter, Depends, Query

from api.common import json_safe
from database.analytics_report_db import _parse_date
from api.dependencies import get_current_user, require_permission
from database.analytics_report_db import (
    get_revenue_summary, room_revenue_data, restaurant_revenue_data,
    occupancy_data, adr_data, revpar_data, booking_trends_data,
    cancellation_data, no_show_data, customer_trends_data,
    inventory_trends_data, expense_trends_data, department_performance_data,
    staff_report_data, profitability_data, get_dashboard_home_summary,
)

router = APIRouter(tags=["Reports & Analytics"])


def _range(start_date: str | None, end_date: str | None):
    start = _parse_date(start_date) if start_date else None
    end = _parse_date(end_date) if end_date else None
    if start and end and start > end:
        raise ValueError("From Date cannot be after To Date.")
    return start, end


@router.get("/reports/dashboard")
def dashboard(user=Depends(require_permission("Reports", "Reports"))):
    return {"data": json_safe(get_revenue_summary(user["hotel_id"]))}


@router.get("/dashboard/home")
def dashboard_home(user=Depends(require_permission("Reports", "View"))):
    return {"data": json_safe(get_dashboard_home_summary(user["hotel_id"]))}


@router.get("/reports/revenue")
def revenue(start_date: str | None = None, end_date: str | None = None, user=Depends(require_permission("Reports", "Reports"))):
    s, e = _range(start_date, end_date)
    return {"data": json_safe(get_revenue_summary(user["hotel_id"], s, e))}


@router.get("/reports/room-revenue")
def room_revenue(start_date: str | None = None, end_date: str | None = None, user=Depends(require_permission("Reports", "Reports"))):
    start, end = _range(start_date, end_date)
    return {"data": json_safe(room_revenue_data(user["hotel_id"], start, end))}


@router.get("/reports/restaurant-revenue")
def restaurant_revenue(start_date: str | None = None, end_date: str | None = None, user=Depends(require_permission("Reports", "Reports"))):
    start, end = _range(start_date, end_date)
    return {"data": json_safe(restaurant_revenue_data(user["hotel_id"], start, end))}


@router.get("/reports/occupancy")
def occupancy(start_date: str | None = None, end_date: str | None = None, user=Depends(require_permission("Reports", "Reports"))):
    start, end = _range(start_date, end_date)
    return {"data": json_safe(occupancy_data(user["hotel_id"], start, end))}


@router.get("/reports/adr")
def adr(start_date: str | None = None, end_date: str | None = None, user=Depends(require_permission("Reports", "Reports"))):
    start, end = _range(start_date, end_date)
    return {"data": json_safe(adr_data(user["hotel_id"], start, end))}


@router.get("/reports/revpar")
def revpar(start_date: str | None = None, end_date: str | None = None, user=Depends(require_permission("Reports", "Reports"))):
    start, end = _range(start_date, end_date)
    return {"data": json_safe(revpar_data(user["hotel_id"], start, end))}


@router.get("/reports/booking-trends")
def booking_trends(start_date: str | None = None, end_date: str | None = None, user=Depends(require_permission("Reports", "Reports"))):
    start, end = _range(start_date, end_date)
    return {"data": json_safe(booking_trends_data(user["hotel_id"], start, end))}


@router.get("/reports/cancellation")
def cancellation(start_date: str | None = None, end_date: str | None = None, user=Depends(require_permission("Reports", "Reports"))):
    start, end = _range(start_date, end_date)
    return {"data": json_safe(cancellation_data(user["hotel_id"], start, end))}


@router.get("/reports/no-show")
def no_show(start_date: str | None = None, end_date: str | None = None, user=Depends(require_permission("Reports", "Reports"))):
    start, end = _range(start_date, end_date)
    return {"data": json_safe(no_show_data(user["hotel_id"], start, end))}


@router.get("/reports/customer-trends")
def customer_trends(start_date: str | None = None, end_date: str | None = None, user=Depends(require_permission("Reports", "Reports"))):
    start, end = _range(start_date, end_date)
    return {"data": json_safe(customer_trends_data(user["hotel_id"], start, end))}


@router.get("/reports/inventory-trends")
def inventory_trends(start_date: str | None = None, end_date: str | None = None, user=Depends(require_permission("Reports", "Reports"))):
    start, end = _range(start_date, end_date)
    return {"data": json_safe(inventory_trends_data(user["hotel_id"], start, end))}


@router.get("/reports/expense-trends")
def expense_trends(start_date: str | None = None, end_date: str | None = None, user=Depends(require_permission("Reports", "Reports"))):
    start, end = _range(start_date, end_date)
    return {"data": json_safe(expense_trends_data(user["hotel_id"], start, end))}


@router.get("/reports/department-performance")
def department_performance(start_date: str | None = None, end_date: str | None = None, user=Depends(require_permission("Reports", "Reports"))):
    start, end = _range(start_date, end_date)
    return {"data": json_safe(department_performance_data(user["hotel_id"], start, end))}


@router.get("/reports/staff")
def staff_reports(start_date: str | None = None, end_date: str | None = None, user=Depends(require_permission("Reports", "Reports"))):
    start, end = _range(start_date, end_date)
    return {"data": json_safe(staff_report_data(user["hotel_id"], start, end))}


@router.get("/reports/profitability")
def profitability(start_date: str | None = None, end_date: str | None = None, user=Depends(require_permission("Reports", "Reports"))):
    start, end = _range(start_date, end_date)
    return {"data": json_safe(profitability_data(user["hotel_id"], start, end))}


@router.get("/reports/operational")
def operational(start_date: str | None = None, end_date: str | None = None, user=Depends(require_permission("Reports", "Reports"))):
    """Combined operational KPI view for the admin Reports dashboard."""
    start, end = _range(start_date, end_date)
    hotel_id = user["hotel_id"]
    return {"data": json_safe({
        "revenue": get_revenue_summary(hotel_id, start, end),
        "occupancy": occupancy_data(hotel_id, start, end),
        "cancellations": cancellation_data(hotel_id, start, end),
        "no_shows": no_show_data(hotel_id, start, end),
        "profitability": profitability_data(hotel_id, start, end),
    })}
