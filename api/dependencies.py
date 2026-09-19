from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.security import AuthenticationError, decode_access_token
from database.database import get_connection
from database.hotel_context import set_current_hotel_id
from database.permission_db import has_permission


bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    try:
        claims = decode_access_token(credentials.credentials)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    try:
        hotel_id = set_current_hotel_id(int(claims["hotel_id"]))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Hotel context is invalid or inactive.") from exc

    connection = get_connection()
    try:
        user = connection.execute(
            """
            SELECT user_id, username, role, hotel_id, staff_id, status
            FROM users
            WHERE user_id = ? AND hotel_id = ?
            """,
            (claims["sub"], hotel_id),
        ).fetchone()
    finally:
        connection.close()

    if user is None or user["status"] != "Active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is inactive or not found.")

    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "role": user["role"],
        "hotel_id": int(user["hotel_id"]),
        "staff_id": user["staff_id"],
    }


def require_permission(module: str, action: str) -> Callable:
    def dependency(user=Depends(get_current_user)):
        try:
            allowed = has_permission(user["user_id"], module, action)
        except Exception as exc:
            raise HTTPException(status_code=500, detail="Authorization service error.") from exc
        if not allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Permission denied: {module} - {action}.")
        return user
    return dependency

