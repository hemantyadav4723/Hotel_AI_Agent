from fastapi import APIRouter, Depends, HTTPException

from api.common import row_dict, rows_dict
from api.dependencies import get_current_user, require_permission
from database.database_admin import run_database_health_check, is_database_healthy, backup_database, backup_configuration, restore_database
from database.audit_db import get_audit_logs, get_record_audit
from database.permission_db import get_active_permissions
from database.role_db import SYSTEM_ROLES
from database.database import get_connection

router = APIRouter(tags=["Administration"])


@router.get("/admin/health")
def health(user=Depends(require_permission("Reports", "Reports"))):
    report = run_database_health_check()
    return {"healthy": is_database_healthy(report), "data": report}


@router.get("/admin/audit")
def audit(
    user=Depends(require_permission("Reports", "View")),
    limit: int = 100,
    search: str | None = None,
    actor_username: str | None = None,
    module: str | None = None,
    action: str | None = None,
    record_id: str | None = None,
    status: str | None = None,
    request_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
):
    return {"data": rows_dict(get_audit_logs(
        hotel_id=user["hotel_id"], limit=max(1, min(limit, 500)), search=search,
        actor_username=actor_username, module=module, action=action, record_id=record_id,
        status=status, request_id=request_id, date_from=date_from, date_to=date_to
    ))}


@router.get("/admin/audit/{record_id}")
def record_audit(record_id: str, user=Depends(require_permission("Reports", "View")), record_type: str | None = None):
    return {"data": rows_dict(get_record_audit(record_id, record_type, user["hotel_id"]))}


@router.get("/admin/permissions")
def permissions(user=Depends(get_current_user), module: str | None = None):
    return {"data": rows_dict(get_active_permissions(module))}


@router.get("/admin/roles")
def roles(user=Depends(get_current_user)):
    connection = get_connection()
    try:
        rows = connection.execute("SELECT role_id, role_name, is_system_role, status FROM roles WHERE hotel_id = ? ORDER BY role_name", (user["hotel_id"],)).fetchall()
    finally:
        connection.close()
    return {"data": rows_dict(rows)}


@router.get("/admin/users")
def users(user=Depends(require_permission("Users", "View"))):
    connection = get_connection()
    try:
        rows = connection.execute("SELECT user_id, username, role, staff_id, status, created_at, updated_at FROM users WHERE hotel_id = ? ORDER BY username", (user["hotel_id"],)).fetchall()
    finally:
        connection.close()
    return {"data": rows_dict(rows)}


@router.post("/admin/backup")
def backup(user=Depends(require_permission("Users", "Create"))):
    return {"data": backup_database(backup_type="API")}


@router.post("/admin/configuration-backup")
def configuration_backup(user=Depends(require_permission("Users", "Create"))):
    return {"data": backup_configuration()}
