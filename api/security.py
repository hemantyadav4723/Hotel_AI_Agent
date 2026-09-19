from datetime import datetime, timedelta, timezone

import jwt

from api.config import settings


class AuthenticationError(Exception):
    pass


def create_access_token(*, user_id: str, username: str, role: str, hotel_id: int, staff_id: str | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "hotel_id": int(hotel_id),
        "staff_id": staff_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
        "type": "access",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid or expired access token.") from exc
    if payload.get("type") != "access" or not payload.get("sub") or not payload.get("username") or not payload.get("role"):
        raise AuthenticationError("Invalid access token claims.")
    try:
        hotel_id = int(payload.get("hotel_id"))
    except (TypeError, ValueError) as exc:
        raise AuthenticationError("Invalid access token claims.") from exc
    if hotel_id <= 0:
        raise AuthenticationError("Invalid access token claims.")
    return payload
