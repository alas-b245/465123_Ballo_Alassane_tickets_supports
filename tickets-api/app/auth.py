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

class AuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        user = USERS.get(token) if scheme.lower() == "bearer" else None
        request.state.user = user
        return await call_next(request)


async def authenticated_user(request: Request) -> User:
    # Yielding here makes the cross-request leak observable under concurrency.
    await asyncio.sleep(0)
    if request.state.user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid bearer token",
        )
    return request.state.user

