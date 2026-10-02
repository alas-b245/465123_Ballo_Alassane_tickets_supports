import asyncio
import time

import pytest
import httpx

from app.clients import DependencyError
from app.main import cache, repository, service
from app.main import app


pytestmark = pytest.mark.acceptance
known_issue = pytest.mark.xfail(strict=True, reason="зафиксированный тикет лабораторной")


@known_issue
def test_alice_sees_only_her_cards(client, auth, create_ticket):
    own = create_ticket("alice-token")
    create_ticket("bob-token", title="Обращение Bob")
    response = client.get("/api/v1/tickets", headers=auth("alice-token"))
    assert [item["id"] for item in response.json()] == [own["id"]]


@known_issue
def test_bob_cannot_open_alice_card(client, auth, create_ticket):
    card = create_ticket("alice-token")
    response = client.get(f"/api/v1/tickets/{card['id']}", headers=auth("bob-token"))
    assert response.status_code == 403


@known_issue
def test_author_cannot_close_own_card(client, auth, create_ticket):
    card = create_ticket("alice-token")
    response = client.patch(
        f"/api/v1/tickets/{card['id']}/status",
        json={"status": "CLOSED"},
        headers=auth("alice-token"),
    )
    assert response.status_code == 403


@known_issue
def test_unknown_priority_is_rejected(client, auth):
    response = client.post(
        "/api/v1/tickets",
        json={"title": "T", "description": "D", "priority": "URGENT"},
        headers=auth(),
    )
    assert response.status_code == 422


@known_issue
def test_repeated_submit_returns_the_same_card(client, auth):
    headers = {**auth(), "Idempotency-Key": "browser-submit-42"}
    payload = {"title": "T", "description": "D", "priority": "LOW"}
    first = client.post("/api/v1/tickets", json=payload, headers=headers)
    second = client.post("/api/v1/tickets", json=payload, headers=headers)
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    assert len(repository.list()) == 1


@known_issue
def test_reopened_card_contains_latest_title(client, auth, create_ticket):
    card = create_ticket()
    client.get(f"/api/v1/tickets/{card['id']}", headers=auth())
    changed = client.patch(
        f"/api/v1/tickets/{card['id']}",
        json={"title": "Новый заголовок"},
        headers=auth(),
    )
    assert changed.status_code == 200
    reopened = client.get(f"/api/v1/tickets/{card['id']}", headers=auth())
    assert reopened.json()["title"] == "Новый заголовок"


@known_issue
def test_unsent_activity_does_not_leave_a_saved_card(client, auth):
    class UnavailableEvents:
        async def publish(self, event_type, ticket_id, data):
            raise DependencyError("temporarily unavailable")

    service.events = UnavailableEvents()
    response = client.post(
        "/api/v1/tickets",
        json={"title": "T", "description": "D", "priority": "LOW"},
        headers=auth(),
    )
    assert response.status_code == 502
    assert repository.list() == []


def test_confirmation_is_returned_before_extra_processing(client, auth):
    class NoticeablySlowClassifier:
        async def classify(self, title, description):
            await asyncio.sleep(0.08)
            return "GENERAL"

    service.classifier = NoticeablySlowClassifier()
    started = time.perf_counter()
    response = client.post(
        "/api/v1/tickets",
        json={"title": "T", "description": "D", "priority": "LOW"},
        headers=auth(),
    )
    elapsed = time.perf_counter() - started
    assert response.status_code == 201
    assert elapsed < 0.04


@known_issue
def test_saved_priority_change_is_reported_as_success(client, auth, create_ticket):
    card = create_ticket()

    class RejectPriorityEvent:
        async def publish(self, event_type, ticket_id, data):
            if event_type == "ticket.priority_changed":
                raise DependencyError("event rejected")

        async def history(self, ticket_id):
            return []

    service.events = RejectPriorityEvent()
    response = client.patch(
        f"/api/v1/tickets/{card['id']}",
        json={"priority": "HIGH"},
        headers=auth("support-token"),
    )
    assert repository.get(card["id"]).priority == "HIGH"
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_parallel_submits_keep_each_persons_identity():
    class QuietEvents:
        async def publish(self, event_type, ticket_id, data):
            return None

    class QuickClassifier:
        async def classify(self, title, description):
            return "GENERAL"

    repository.clear()
    cache.clear()
    service.events = QuietEvents()
    service.classifier = QuickClassifier()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"title": "T", "description": "D", "priority": "LOW"}
        alice, bob = await asyncio.gather(
            client.post(
                "/api/v1/tickets",
                json=payload,
                headers={"Authorization": "Bearer alice-token"},
            ),
            client.post(
                "/api/v1/tickets",
                json=payload,
                headers={"Authorization": "Bearer bob-token"},
            ),
        )
    assert alice.json()["author_id"] == "alice"
    assert bob.json()["author_id"] == "bob"


@pytest.mark.asyncio
async def test_closed_ticket_edit_returns_consistent_error():
    class QuietEvents:
        async def publish(self, event_type, ticket_id, data):
            return None

    class QuickClassifier:
        async def classify(self, title, description):
            return "GENERAL"

    repository.clear()
    cache.clear()
    service.events = QuietEvents()
    service.classifier = QuickClassifier()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post(
            "/api/v1/tickets",
            json={"title": "Old", "description": "Desc"},
            headers={"Authorization": "Bearer support-token"},
        )
        assert created.status_code == 201
        ticket_id = created.json()["id"]

        closed = await client.patch(
            f"/api/v1/tickets/{ticket_id}/status",
            json={"status": "CLOSED"},
            headers={"Authorization": "Bearer support-token"},
        )
        assert closed.status_code == 200

        edited = await client.patch(
            f"/api/v1/tickets/{ticket_id}",
            json={"title": "New"},
            headers={"Authorization": "Bearer support-token"},
        )
        assert edited.status_code == 409
        assert "detail" in edited.json()
