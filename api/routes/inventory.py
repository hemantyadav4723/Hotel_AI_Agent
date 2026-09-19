from fastapi import APIRouter, Depends, Query, Body

from api.common import row_dict, rows_dict
from api.dependencies import get_current_user, require_permission
from database.database import get_connection
from database.inventory_db import get_low_stock_items, get_inventory_valuation
from database.inventory_category_db import get_category_options
from database.inventory_unit_db import get_unit_options
from database.inventory_batch_db import view_batches
from database.inventory_db import stock_in, stock_out, stock_adjustment, damaged_stock, update_reorder_level, set_expiry_date

router = APIRouter(tags=["Inventory & Procurement"])


@router.get("/inventory/items")
def inventory_items(user=Depends(get_current_user), search: str | None = None, limit: int = 500):
    connection = get_connection()
    try:
        sql = "SELECT * FROM inventory WHERE hotel_id = ?"
        params = [user["hotel_id"]]
        if search:
            sql += " AND (lower(item_id) LIKE lower(?) OR lower(item_name) LIKE lower(?))"
            like = f"%{search.strip()}%"
            params.extend([like, like])
        sql += " ORDER BY item_name LIMIT ?"
        params.append(max(1, min(limit, 1000)))
        rows = connection.execute(sql, params).fetchall()
    finally:
        connection.close()
    return {"data": rows_dict(rows)}


@router.get("/inventory/low-stock")
def low_stock(user=Depends(get_current_user)):
    connection = get_connection()
    try:
        rows = connection.execute(
            """SELECT * FROM inventory
               WHERE hotel_id = ?
                 AND COALESCE(quantity, 0) <= COALESCE(reorder_level, 0)
               ORDER BY item_name""",
            (user["hotel_id"],),
        ).fetchall()
    finally:
        connection.close()
    return {"data": rows_dict(rows)}


@router.get("/inventory/valuation")
def inventory_valuation(user=Depends(get_current_user)):
    connection = get_connection()
    try:
        row = connection.execute(
            """SELECT ROUND(COALESCE(SUM(COALESCE(quantity, 0) * COALESCE(cost_price, 0)), 0), 2) AS inventory_value,
                      COUNT(*) AS item_count
               FROM inventory WHERE hotel_id = ?""",
            (user["hotel_id"],),
        ).fetchone()
    finally:
        connection.close()
    return {"data": row_dict(row)}


@router.get("/inventory/categories")
def inventory_categories(user=Depends(get_current_user)):
    return {"data": rows_dict(get_category_options())}


@router.get("/inventory/units")
def inventory_units(user=Depends(get_current_user)):
    return {"data": rows_dict(get_unit_options())}


@router.get("/suppliers")
def suppliers(user=Depends(get_current_user), limit: int = 500):
    connection = get_connection()
    try:
        rows = connection.execute("SELECT * FROM suppliers WHERE hotel_id = ? ORDER BY supplier_name LIMIT ?", (user["hotel_id"], max(1, min(limit, 1000)))).fetchall()
    finally:
        connection.close()
    return {"data": rows_dict(rows)}


@router.get("/procurement/purchase-orders")
def purchase_orders(user=Depends(get_current_user), limit: int = 200):
    connection = get_connection()
    try:
        rows = connection.execute("SELECT * FROM purchase_orders WHERE hotel_id = ? ORDER BY po_date DESC LIMIT ?", (user["hotel_id"], max(1, min(limit, 500)))).fetchall()
    finally:
        connection.close()
    return {"data": rows_dict(rows)}


@router.get("/procurement/receivings")
def purchase_receivings(user=Depends(get_current_user), limit: int = 200):
    connection = get_connection()
    try:
        rows = connection.execute("SELECT * FROM purchase_receivings WHERE hotel_id = ? ORDER BY receiving_date DESC LIMIT ?", (user["hotel_id"], max(1, min(limit, 500)))).fetchall()
    finally:
        connection.close()
    return {"data": rows_dict(rows)}


@router.get("/inventory/history")
def inventory_history(user=Depends(get_current_user), item_id: str | None = None, transaction_type: str | None = None, limit: int = 500):
    connection = get_connection()
    try:
        sql = "SELECT * FROM inventory_transactions WHERE hotel_id = ?"
        params = [user["hotel_id"]]
        if item_id:
            sql += " AND item_id = ?"; params.append(item_id.strip().upper())
        if transaction_type:
            sql += " AND transaction_type = ?"; params.append(transaction_type.strip().upper())
        sql += " ORDER BY transaction_id DESC LIMIT ?"; params.append(max(1, min(limit, 1000)))
        rows = connection.execute(sql, params).fetchall()
    finally:
        connection.close()
    return {"data": rows_dict(rows)}

@router.get("/inventory/batches")
def inventory_batches(user=Depends(get_current_user), item_id: str | None = None, limit: int = 500):
    connection = get_connection()
    try:
        sql = "SELECT * FROM inventory_batches WHERE hotel_id = ?"; params = [user["hotel_id"]]
        if item_id:
            sql += " AND item_id = ?"; params.append(item_id.strip().upper())
        sql += " ORDER BY expiry_date ASC, batch_id DESC LIMIT ?"; params.append(max(1, min(limit, 1000)))
        rows = connection.execute(sql, params).fetchall()
    finally:
        connection.close()
    return {"data": rows_dict(rows)}

@router.post("/inventory/stock-in")
def inventory_stock_in(payload: dict = Body(...), user=Depends(get_current_user), _=Depends(require_permission("Inventory", "Create"))):
    return {"data": stock_in(**payload)}

@router.post("/inventory/stock-out")
def inventory_stock_out(payload: dict = Body(...), user=Depends(get_current_user), _=Depends(require_permission("Inventory", "Create"))):
    return {"data": stock_out(**payload)}

@router.post("/inventory/adjustment")
def inventory_adjustment(payload: dict = Body(...), user=Depends(get_current_user), _=Depends(require_permission("Inventory", "Update"))):
    return {"data": stock_adjustment(**payload)}

@router.post("/inventory/damaged")
def inventory_damaged(payload: dict = Body(...), user=Depends(get_current_user), _=Depends(require_permission("Inventory", "Update"))):
    return {"data": damaged_stock(**payload)}

@router.patch("/inventory/reorder-level")
def inventory_reorder_level(payload: dict = Body(...), user=Depends(get_current_user), _=Depends(require_permission("Inventory", "Update"))):
    return {"data": update_reorder_level(payload.get("item_id"), payload.get("reorder_level"))}

@router.patch("/inventory/expiry")
def inventory_expiry(payload: dict = Body(...), user=Depends(get_current_user), _=Depends(require_permission("Inventory", "Update"))):
    return {"data": set_expiry_date(payload.get("item_id"), payload.get("expiry_date"))}

@router.get("/suppliers/detail")
def supplier_detail(supplier_id: str, user=Depends(get_current_user)):
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT * FROM suppliers WHERE hotel_id = ? AND supplier_id = ?",
            (user["hotel_id"], supplier_id.strip().upper()),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Supplier not found.")
    return {"data": row_dict(row)}


@router.get("/suppliers/search")
def supplier_search(q: str | None = None, status: str | None = None, user=Depends(get_current_user)):
    connection = get_connection()
    try:
        sql = "SELECT * FROM suppliers WHERE hotel_id = ?"
        params = [user["hotel_id"]]
        if q and q.strip():
            term = f"%{q.strip()}%"
            sql += " AND (supplier_id LIKE ? OR supplier_name LIKE ? OR mobile LIKE ? OR contact_person LIKE ? OR gstin LIKE ?)"
            params.extend([term] * 5)
        if status and status.strip():
            sql += " AND status = ?"
            params.append(status.strip())
        sql += " ORDER BY supplier_name LIMIT 500"
        rows = connection.execute(sql, params).fetchall()
    finally:
        connection.close()
    return {"data": rows_dict(rows)}


@router.get("/procurement/purchase-orders/{po_id}")
def purchase_order_detail(po_id: str, user=Depends(get_current_user)):
    connection = get_connection()
    try:
        po = connection.execute(
            """SELECT po.*, s.supplier_name, s.mobile AS supplier_mobile, s.gstin
               FROM purchase_orders po
               JOIN suppliers s ON s.supplier_id = po.supplier_id AND s.hotel_id = po.hotel_id
               WHERE po.hotel_id = ? AND po.po_id = ?""",
            (user["hotel_id"], po_id.strip().upper()),
        ).fetchone()
        if po is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Purchase Order not found.")
        items = connection.execute(
            "SELECT * FROM purchase_order_items WHERE hotel_id = ? AND po_id = ? ORDER BY po_item_id",
            (user["hotel_id"], po_id.strip().upper()),
        ).fetchall()
    finally:
        connection.close()
    return {"data": row_dict(po), "items": rows_dict(items)}


@router.get("/procurement/purchase-history")
def procurement_purchase_history(supplier_id: str | None = None, po_id: str | None = None, user=Depends(get_current_user)):
    connection = get_connection()
    try:
        sql = """SELECT pr.*, s.supplier_name
                 FROM purchase_receivings pr
                 JOIN suppliers s ON s.supplier_id = pr.supplier_id AND s.hotel_id = pr.hotel_id
                 WHERE pr.hotel_id = ?"""
        params = [user["hotel_id"]]
        if supplier_id:
            sql += " AND pr.supplier_id = ?"; params.append(supplier_id.strip().upper())
        if po_id:
            sql += " AND pr.po_id = ?"; params.append(po_id.strip().upper())
        sql += " ORDER BY pr.receiving_date DESC, pr.created_at DESC LIMIT 500"
        rows = connection.execute(sql, params).fetchall()
    finally:
        connection.close()
    return {"data": rows_dict(rows)}


@router.get("/procurement/payment-terms")
def procurement_payment_terms(supplier_id: str | None = None, user=Depends(get_current_user)):
    from database.supplier_payment_terms_db import get_supplier_payment_terms
    if supplier_id:
        return {"data": get_supplier_payment_terms(supplier_id.strip().upper())}
    connection = get_connection()
    try:
        rows = connection.execute(
            """SELECT s.supplier_id, s.supplier_name, t.payment_type, t.credit_days,
                      t.advance_percentage, t.notes
               FROM suppliers s LEFT JOIN supplier_payment_terms t
                 ON t.supplier_id=s.supplier_id AND t.hotel_id=s.hotel_id
               WHERE s.hotel_id=? ORDER BY s.supplier_name""",
            (user["hotel_id"],),
        ).fetchall()
    finally:
        connection.close()
    return {"data": rows_dict(rows)}


@router.get("/procurement/outstanding")
def procurement_outstanding(supplier_id: str | None = None, user=Depends(get_current_user)):
    from database.supplier_outstanding_db import get_supplier_outstanding
    data = get_supplier_outstanding(supplier_id.strip().upper() if supplier_id else None)
    return {"data": data if isinstance(data, list) else [data] if data else []}
