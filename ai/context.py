"""Request-scoped AI context helpers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AIRequestContext:
    user_id: str
    username: str
    role: str
    hotel_id: int

    @classmethod
    def from_user(cls, user: dict) -> "AIRequestContext":
        return cls(
            user_id=str(user["user_id"]),
            username=str(user["username"]),
            role=str(user["role"]),
            hotel_id=int(user["hotel_id"]),
        )

    def public_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "role": self.role,
            "hotel_id": self.hotel_id,
        }
