from datetime import datetime
from typing import Any, Literal

from fastapi import FastAPI, Query
from pydantic import BaseModel


EventType = Literal[
    "ticket.created",
    "ticket.status_changed",
    "ticket.priority_changed",
    "ticket.classified",
]


class Event(BaseModel):
    event_id: str
    event_type: EventType
    ticket_id: str
    occurred_at: datetime
    data: dict[str, Any]


class InMemoryEventStore:
    def __init__(self) -> None:
        self._events: list[Event] = []

    def append(self, event: Event) -> Event:
        self._events.append(event.model_copy(deep=True))
        return event

    def by_ticket(self, ticket_id: str) -> list[Event]:
        return [
            event.model_copy(deep=True)
            for event in self._events
            if event.ticket_id == ticket_id
        ]

    def clear(self) -> None:
        self._events.clear()


store = InMemoryEventStore()
app = FastAPI(title="Ticket Event Service", version="1.0.0")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/internal/events", response_model=Event, status_code=201)
async def append_event(event: Event):
    return store.append(event)


@app.get("/internal/events")
async def list_events(ticket_id: str = Query(min_length=1)):
    return {"items": store.by_ticket(ticket_id)}

