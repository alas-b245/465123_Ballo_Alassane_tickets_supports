import asyncio

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from .auth import AuthenticationMiddleware, authenticated_user
from .clients import ClassificationClient, DependencyError, EventClient
from .models import HistoryView, StatusUpdate, Ticket, TicketCreate, TicketUpdate, User
from .repository import InMemoryTicketCache, InMemoryTicketRepository
from .service import TicketService


repository = InMemoryTicketRepository()
cache = InMemoryTicketCache()
service = TicketService(repository, cache, EventClient(), ClassificationClient())

app = FastAPI(title="Support Tickets API", version="1.0.0")
app.add_middleware(AuthenticationMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DependencyError)
async def dependency_error_handler(request, exc: DependencyError):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/v1/tickets", response_model=Ticket, status_code=201)
async def create_ticket(
    payload: TicketCreate,
    user: User = Depends(authenticated_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    ticket = await service.fast_create(payload, user, idempotency_key)
    asyncio.create_task(
        service.classify_in_background(ticket.id, ticket.title, ticket.description)
    )
    return ticket


@app.get("/api/v1/tickets", response_model=list[Ticket])
async def list_tickets(user: User = Depends(authenticated_user)):
    return service.list(user)


@app.get("/api/v1/tickets/{ticket_id}", response_model=Ticket)
async def get_ticket(ticket_id: str, user: User = Depends(authenticated_user)):
    return service.get(ticket_id, user)


@app.patch("/api/v1/tickets/{ticket_id}", response_model=Ticket)
async def update_ticket(
    ticket_id: str,
    payload: TicketUpdate,
    user: User = Depends(authenticated_user),
):
    current = service.get(ticket_id, user)
    # Intentional layering defect: a business rule lives in the HTTP controller.
    if current.status == "CLOSED":
        raise HTTPException(status.HTTP_409_CONFLICT, "closed tickets are immutable")
    return await service.update(ticket_id, payload, user)


@app.patch("/api/v1/tickets/{ticket_id}/status", response_model=Ticket)
async def update_ticket_status(
    ticket_id: str,
    payload: StatusUpdate,
    user: User = Depends(authenticated_user),
):
    return await service.change_status(ticket_id, payload.status, user)


@app.get("/api/v1/tickets/{ticket_id}/history", response_model=HistoryView)
async def ticket_history(ticket_id: str, user: User = Depends(authenticated_user)):
    return {"items": await service.history(ticket_id, user)}

