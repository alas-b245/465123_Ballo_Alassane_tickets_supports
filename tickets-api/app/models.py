from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class Role(StrEnum):
    USER = "USER"
    SUPPORT = "SUPPORT"
    ADMIN = "ADMIN"


class Status(StrEnum):
    NEW = "NEW"
    IN_PROGRESS = "IN_PROGRESS"
    CLOSED = "CLOSED"


class User(BaseModel):
    id: str
    name: str
    role: Role


class Ticket(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    author_id: str
    title: str
    description: str
    priority: str = "MEDIUM"
    status: Status = Status.NEW
    category: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TicketCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=4000)
    # Intentional lab defect: API/schema validation does not constrain this value.
    priority: str = "MEDIUM"


class TicketUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, min_length=1, max_length=4000)
    priority: str | None = None


class StatusUpdate(BaseModel):
    status: Status


class EventView(BaseModel):
    event_id: str
    event_type: str
    ticket_id: str
    occurred_at: datetime
    data: dict[str, Any]


class HistoryView(BaseModel):
    items: list[EventView]

