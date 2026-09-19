from fastapi import APIRouter, Depends, HTTPException, Query

from api.common import row_dict, rows_dict
from api.dependencies import get_current_user, require_permission
from api.schemas import ExpenseCreate
from database.database import get_connection
from database.expenses_db import save_expense, get_expense_payment_methods
from database.analytics_report_db import get_revenue_summary
from database.billing_invoice_db import list_invoice_history
from database.order_db import get_order_payment_history, add_order_payment, record_order_refund, get_order_payment
from database.room_payment_db import get_room_payment_transactions, get_room_folio_summary, record_room_payment

router = APIRouter(tags=["Finance"])


@router.get("/billing/invoices")
def invoices(
    user=Depends(get_current_user),
    search: str | None = Query(None),
    source_type: str | None = Query(None),
    invoice_status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    connection = get_connection()
    try:
        rows = list_invoice_history(connection.cursor(), user["hotel_id"], source_type=source_type, invoice_status=invoice_status, limit=limit)
        if search:
            term = str(search).strip().lower()
            rows = [r for r in rows if term in str(r["invoice_number"]).lower() or term in str(r["source_id"]).lower() or term in str(r["source_type"]).lower()]
    finally:
        connection.close()
    return {"data": rows_dict(rows)}


@router.get("/billing/invoices/{invoice_number}")
def invoice_detail(invoice_number: str, user=Depends(get_current_user)):
    connection = get_connection()
    try:
        from database.billing_invoice_db import get_invoice_by_number
        row = get_invoice_by_number(connection.cursor(), user["hotel_id"], invoice_number)
    finally:
        connection.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    return {"data": row_dict(row)}


@router.get("/billing/summary")
def billing_summary(user=Depends(get_current_user)):
    connection = get_connection()
    try:
        hotel_id = user["hotel_id"]
        invoice_count = connection.execute("SELECT COUNT(*) FROM invoices WHERE hotel_id=?", (hotel_id,)).fetchone()[0]
        room = connection.execute("SELECT COALESCE(SUM(paid_amount),0) paid, COALESCE(SUM(balance_amount),0) balance, COALESCE(SUM(grand_total),0) total FROM room_bookings WHERE hotel_id=? AND COALESCE(booking_status,'') NOT IN ('Cancelled','No-Show')", (hotel_id,)).fetchone()
        rest = connection.execute("SELECT COALESCE(SUM(paid_amount),0) paid, COALESCE(SUM(balance_amount),0) balance, COALESCE(SUM(grand_total),0) total FROM orders WHERE hotel_id=? AND COALESCE(order_status,'')!='Cancelled'", (hotel_id,)).fetchone()
    finally:
        connection.close()
    return {"data": {"invoice_count": invoice_count, "room": dict(room), "restaurant": dict(rest)}}


@router.get("/billing/restaurant/{order_id}")
def restaurant_payment_detail(order_id: str, user=Depends(get_current_user)):
    connection = get_connection()
    try:
        row = connection.execute("SELECT order_id, hotel_id, customer_name, grand_total, paid_amount, advance_amount, balance_amount, payment_status, payment_method, refund_amount, order_status FROM orders WHERE order_id=? AND hotel_id=?", (order_id, user["hotel_id"])).fetchone()
    finally:
        connection.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Restaurant order not found.")
    return {"data": row_dict(row)}


@router.post("/billing/room/{booking_id}/payments", status_code=201)
def add_room_payment(booking_id: str, payload: dict, user=Depends(require_permission("Rooms", "Payment"))):
    try:
        transaction_id = record_room_payment(booking_id, payload.get("amount"), payload.get("payment_method"), notes=payload.get("notes"), hotel_id=user["hotel_id"])
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"data": {"transaction_id": transaction_id}, "message": "Room payment recorded."}


@router.post("/billing/restaurant/{order_id}/payments", status_code=201)
def add_restaurant_payment(order_id: str, payload: dict, user=Depends(require_permission("Restaurant", "Payment"))):
    try:
        result = add_order_payment(order_id, payload.get("amount"), payload.get("payment_method"), payload.get("notes"), user["hotel_id"])
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"data": result, "message": "Restaurant payment recorded."}


@router.post("/billing/restaurant/{order_id}/refund")
def refund_restaurant_payment(order_id: str, payload: dict, user=Depends(require_permission("Restaurant", "Refund"))):
    try:
        status = record_order_refund(order_id, payload.get("amount"), payload.get("reason"), user["hotel_id"])
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"data": {"payment_status": status}, "message": "Restaurant refund recorded."}


@router.get("/billing/room/{booking_id}/folio")
def room_folio(booking_id: str, user=Depends(get_current_user)):
    return {"data": row_dict(get_room_folio_summary(booking_id, user["hotel_id"]))}


@router.get("/billing/room/{booking_id}/transactions")
def room_transactions(booking_id: str, user=Depends(get_current_user)):
    return {"data": rows_dict(get_room_payment_transactions(booking_id, user["hotel_id"]))}


@router.get("/billing/restaurant/{order_id}/transactions")
def restaurant_transactions(order_id: str, user=Depends(get_current_user)):
    return {"data": rows_dict(get_order_payment_history(order_id, user["hotel_id"]))}


@router.get("/billing/payment-methods")
def payment_methods(user=Depends(get_current_user)):
    return {"data": get_expense_payment_methods()}


@router.get("/expenses")
def expenses(
    user=Depends(require_permission("Expenses", "View")),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    search: str | None = Query(None),
    category_id: str | None = Query(None),
    payment_method: str | None = Query(None),
    approval_status: str | None = Query(None),
    recurring: bool | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
):
    connection = get_connection()
    try:
        where = ["hotel_id = ?"]; params = [user["hotel_id"]]
        if start_date: where.append("expense_date >= ?"); params.append(start_date)
        if end_date: where.append("expense_date <= ?"); params.append(end_date)
        if search:
            like = f"%{search.strip()}%"; where.append("(expense_id LIKE ? OR expense_name LIKE ? OR COALESCE(vendor_name,'') LIKE ? OR COALESCE(receipt_reference,'') LIKE ?)"); params.extend([like]*4)
        if category_id: where.append("category_id = ?"); params.append(category_id.strip().upper())
        if payment_method: where.append("payment_method = ?"); params.append(payment_method.strip())
        if approval_status: where.append("approval_status = ?"); params.append(approval_status.strip().title())
        if recurring is not None: where.append("is_recurring = ?"); params.append(1 if recurring else 0)
        params.append(max(1, min(limit, 500)))
        rows = connection.execute(f"SELECT * FROM expenses WHERE {' AND '.join(where)} ORDER BY expense_date DESC, expense_time DESC, expense_id DESC LIMIT ?", params).fetchall()
    finally:
        connection.close()
    return {"data": rows_dict(rows)}


@router.get("/expenses/summary")
def expense_summary(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    category_id: str | None = Query(None),
    payment_method: str | None = Query(None),
    approval_status: str | None = Query(None),
    recurring: bool | None = Query(None),
    user=Depends(require_permission("Expenses", "View")),
):
    connection = get_connection()
    try:
        hotel_id = user["hotel_id"]
        where = ["hotel_id = ?"]
        params = [hotel_id]
        if start_date:
            where.append("expense_date >= ?"); params.append(start_date)
        if end_date:
            where.append("expense_date <= ?"); params.append(end_date)
        if category_id:
            where.append("category_id = ?"); params.append(category_id.strip().upper())
        if payment_method:
            where.append("payment_method = ?"); params.append(payment_method.strip())
        if approval_status:
            where.append("approval_status = ?"); params.append(approval_status.strip().title())
        if recurring is not None:
            where.append("is_recurring = ?"); params.append(1 if recurring else 0)
        clause = " AND ".join(where)
        total = connection.execute(f"SELECT COUNT(*) count, COALESCE(SUM(amount),0) total FROM expenses WHERE {clause}", params).fetchone()
        by_category = connection.execute(f"SELECT COALESCE(category,'Uncategorized') category, ROUND(COALESCE(SUM(amount),0),2) amount, COUNT(*) count FROM expenses WHERE {clause} GROUP BY category ORDER BY amount DESC", params).fetchall()
        by_payment = connection.execute(f"SELECT COALESCE(payment_method,'Not Provided') payment_method, ROUND(COALESCE(SUM(amount),0),2) amount, COUNT(*) count FROM expenses WHERE {clause} GROUP BY payment_method ORDER BY amount DESC", params).fetchall()
        by_approval = connection.execute(f"SELECT COALESCE(approval_status,'Pending') approval_status, ROUND(COALESCE(SUM(amount),0),2) amount, COUNT(*) count FROM expenses WHERE {clause} GROUP BY approval_status ORDER BY count DESC", params).fetchall()
        recurring_rows = connection.execute(f"SELECT expense_id, expense_name, amount, recurrence_frequency, recurrence_start_date, next_due_date, approval_status FROM expenses WHERE {clause} AND is_recurring=1 ORDER BY next_due_date ASC, expense_id ASC", params).fetchall()
    finally:
        connection.close()
    return {"data": {"count": int(total["count"]), "total": float(total["total"] or 0), "by_category": rows_dict(by_category), "by_payment_method": rows_dict(by_payment), "by_approval": rows_dict(by_approval), "recurring": rows_dict(recurring_rows)}}


@router.get("/expenses/categories")
def expense_categories(user=Depends(require_permission("Expenses", "View"))):
    connection = get_connection()
    try:
        rows = connection.execute("SELECT category_id, category_name, status FROM expense_categories WHERE hotel_id = ? ORDER BY category_name", (user["hotel_id"],)).fetchall()
    finally:
        connection.close()
    return {"data": rows_dict(rows)}


@router.get("/expenses/vendors")
def expense_vendors(user=Depends(require_permission("Expenses", "View"))):
    connection = get_connection()
    try:
        rows = connection.execute("SELECT supplier_id AS vendor_id, supplier_name AS vendor_name, status FROM suppliers WHERE hotel_id = ? ORDER BY supplier_name", (user["hotel_id"],)).fetchall()
    finally:
        connection.close()
    return {"data": rows_dict(rows)}


@router.get("/expenses/departments")
def expense_departments(user=Depends(require_permission("Expenses", "View"))):
    connection = get_connection()
    try:
        rows = connection.execute("SELECT department_id, department_name, status FROM department WHERE hotel_id = ? ORDER BY department_name", (user["hotel_id"],)).fetchall()
    finally:
        connection.close()
    return {"data": rows_dict(rows)}


@router.post("/expenses", status_code=201)
def create_expense(payload: ExpenseCreate, user=Depends(require_permission("Expenses", "Create"))):
    save_expense(
        payload.expense_id, payload.expense_date.isoformat(), payload.expense_time,
        payload.expense_name, payload.amount, payload.category, payload.description,
        payload.category_id, payload.vendor_id, payload.payment_method, payload.receipt_reference,
        payload.department_id, payload.is_recurring,
        payload.recurrence_frequency, payload.recurrence_start_date.isoformat() if payload.recurrence_start_date else None,
        user["hotel_id"],
    )
    connection = get_connection()
    try:
        row = connection.execute("SELECT * FROM expenses WHERE expense_id = ? AND hotel_id = ?", (payload.expense_id.upper(), user["hotel_id"])).fetchone()
    finally:
        connection.close()
    return {"data": row_dict(row), "message": "Expense created successfully."}
