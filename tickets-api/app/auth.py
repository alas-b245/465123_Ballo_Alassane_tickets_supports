import asyncio

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

from .models import Role, User


USERS = {
    "alice-token": User(id="alice", name="Alice", role=Role.USER),
    "bob-token": User(id="bob", name="Bob", role=Role.USER),
    "support-token": User(id="support", name="Support", role=Role.SUPPORT),
    "admin-token": User(id="admin", name="Admin", role=Role.ADMIN),
}

# Intentional lab defect: mutable process-wide auth context is unsafe for concurrent requests.
current_user: User | None = None


class AuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        global current_user
        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        user = USERS.get(token) if scheme.lower() == "bearer" else None
        request.state.user = user
        current_user = user
        return await call_next(request)


async def authenticated_user() -> User:
    # Yielding here makes the cross-request leak observable under concurrency.
    await asyncio.sleep(0)
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid bearer token",
        )
    return current_user

