from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import get_current_user
from api.schemas import LoginRequest, PasswordChange, TokenResponse
from api.security import create_access_token
from api.config import settings
from database.database import get_connection
from database.hotel_context import get_current_hotel_id, set_current_hotel_id
from database.user_db import _verify_password, _hash_password
from database.permission_db import get_user_permissions

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest):
    hotel_id = payload.hotel_id or get_current_hotel_id()
    try:
        hotel_id = set_current_hotel_id(hotel_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    connection = get_connection()
    try:
        user = connection.execute(
            """
            SELECT u.user_id, u.username, u.password, u.role, u.hotel_id, u.staff_id,
                   u.status, s.staff_name, s.status AS staff_status
            FROM users u
            LEFT JOIN staff s ON s.staff_id = u.staff_id AND s.hotel_id = u.hotel_id
            WHERE lower(u.username) = lower(?) AND u.hotel_id = ?
            """,
            (payload.username.strip(), hotel_id),
        ).fetchone()
    finally:
        connection.close()

    if not user or user["status"] != "Active" or not _verify_password(payload.password, user["password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")
    if user["staff_id"] and user["staff_status"] not in {"New", "Active"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Login blocked because linked staff is inactive.")

    token = create_access_token(
        user_id=user["user_id"], username=user["username"], role=user["role"],
        hotel_id=user["hotel_id"], staff_id=user["staff_id"],
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.access_token_minutes * 60,
        "user": {
            "user_id": user["user_id"], "username": user["username"],
            "role": user["role"], "hotel_id": user["hotel_id"],
            "staff_id": user["staff_id"], "staff_name": user["staff_name"],
        },
    }


@router.get("/me")
def me(user=Depends(get_current_user)):
    return {"data": user}


@router.get("/permissions")
def permissions(user=Depends(get_current_user)):
    rows = get_user_permissions(user["user_id"])
    return {"data": [dict(row) for row in rows]}


@router.post("/change-password")
def change_password(payload: PasswordChange, user=Depends(get_current_user)):
    connection = get_connection()
    try:
        record = connection.execute(
            "SELECT password FROM users WHERE user_id = ? AND hotel_id = ? AND status = 'Active'",
            (user["user_id"], user["hotel_id"]),
        ).fetchone()
        if not record or not _verify_password(payload.current_password, record["password"]):
            raise HTTPException(status_code=400, detail="Current password is incorrect.")
        connection.execute(
            "UPDATE users SET password = ?, updated_at = ? WHERE user_id = ? AND hotel_id = ?",
            (_hash_password(payload.new_password), datetime.now().strftime("%d-%m-%Y %I:%M:%S %p"), user["user_id"], user["hotel_id"]),
        )
        connection.commit()
    finally:
        connection.close()
    return {"message": "Password changed successfully."}
