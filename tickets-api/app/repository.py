from datetime import UTC, datetime

from .models import Ticket


class InMemoryTicketRepository:
    def __init__(self) -> None:
        self._tickets: dict[str, Ticket] = {}

    def create(self, ticket: Ticket) -> Ticket:
        self._tickets[ticket.id] = ticket.model_copy(deep=True)
        return ticket.model_copy(deep=True)

    def list(self) -> list[Ticket]:
        return [ticket.model_copy(deep=True) for ticket in self._tickets.values()]

    def get(self, ticket_id: str) -> Ticket | None:
        ticket = self._tickets.get(ticket_id)
        return ticket.model_copy(deep=True) if ticket else None

    def save(self, ticket: Ticket) -> Ticket:
        ticket = ticket.model_copy(update={"updated_at": datetime.now(UTC)}, deep=True)
        self._tickets[ticket.id] = ticket
        return ticket.model_copy(deep=True)

    def clear(self) -> None:
        self._tickets.clear()


class InMemoryTicketCache:
    def __init__(self) -> None:
        self._items: dict[str, Ticket] = {}

    def get(self, ticket_id: str) -> Ticket | None:
        ticket = self._items.get(ticket_id)
        return ticket.model_copy(deep=True) if ticket else None

    def put(self, ticket: Ticket) -> None:
        self._items[ticket.id] = ticket.model_copy(deep=True)

    def invalidate(self, ticket_id: str) -> None:
        self._items.pop(ticket_id, None)

    def clear(self) -> None:
        self._items.clear()

