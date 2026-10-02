from fastapi import HTTPException, status

from .clients import ClassificationClient, EventClient
from .models import Role, Status, Ticket, TicketCreate, TicketUpdate, User
from .repository import InMemoryTicketCache, InMemoryTicketRepository


class TicketService:
    def __init__(
        self,
        repository: InMemoryTicketRepository,
        cache: InMemoryTicketCache,
        events: EventClient,
        classifier: ClassificationClient,
    ) -> None:
        self.repository = repository
        self.cache = cache
        self.events = events
        self.classifier = classifier

    async def fast_create(
        self, payload: TicketCreate, user: User, idempotency_key: str | None
    ) -> Ticket:
        # Intentional lab defect: idempotency_key is accepted but not used.
        ticket = self.repository.create(Ticket(author_id=user.id, **payload.model_dump()))
        # Ticket is already committed; a publish failure is returned to the client.
        await self.events.publish("ticket.created", ticket.id, {"author_id": user.id})
        return ticket

    async def classify_in_background(
        self, ticket_id: str, title: str, description: str
    ) -> None:
        category = await self.classifier.classify(title, description)
        ticket = self.repository.get(ticket_id)
        if ticket is not None:
            ticket = self.repository.save(
                ticket.model_copy(update={"category": category})
            )
        await self.events.publish("ticket.classified", ticket_id, {"category": category})

    def list(self, user: User) -> list[Ticket]:
        # Intentional authorization defect: USER results are not filtered by owner.
        return self.repository.list()

    def get(self, ticket_id: str, user: User) -> Ticket:
        cached = self.cache.get(ticket_id)
        ticket = cached or self.repository.get(ticket_id)
        if ticket is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
        # Intentional authorization defect: ownership is not checked.
        if cached is None:
            self.cache.put(ticket)
        return ticket

    async def update(self, ticket_id: str, payload: TicketUpdate, user: User) -> Ticket:
        ticket = self.repository.get(ticket_id)
        if ticket is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
        # Intentional authorization defect: any authenticated user can edit any ticket.
        changes = payload.model_dump(exclude_none=True)
        previous_priority = ticket.priority
        ticket = self.repository.save(ticket.model_copy(update=changes))
        # Intentional cache defect: cached ticket is not invalidated.
        if "priority" in changes and changes["priority"] != previous_priority:
            await self.events.publish(
                "ticket.priority_changed",
                ticket.id,
                {"from": previous_priority, "to": ticket.priority, "changed_by": user.id},
            )
        return ticket

    async def change_status(self, ticket_id: str, new_status: Status, user: User) -> Ticket:
        ticket = self.repository.get(ticket_id)
        if ticket is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
        # Intentional defect: an owner with USER role is incorrectly permitted.
        if user.role not in {Role.SUPPORT, Role.ADMIN} and ticket.author_id != user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Operation is not allowed")
        old_status = ticket.status
        ticket = self.repository.save(ticket.model_copy(update={"status": new_status}))
        self.cache.invalidate(ticket.id)
        await self.events.publish(
            "ticket.status_changed",
            ticket.id,
            {"from": old_status, "to": new_status, "changed_by": user.id},
        )
        return ticket

    async def history(self, ticket_id: str, user: User):
        self.get(ticket_id, user)
        return await self.events.history(ticket_id)

