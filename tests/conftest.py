import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tickets-api"))

from app.main import app, cache, repository, service  # noqa: E402


class RecordingEvents:
    def __init__(self):
        self.items = []

    async def publish(self, event_type, ticket_id, data):
        self.items.append(
            {
                "event_id": str(uuid4()),
                "event_type": event_type,
                "ticket_id": ticket_id,
                "occurred_at": datetime.now(UTC).isoformat(),
                "data": data,
            }
        )

    async def history(self, ticket_id):
        return [item for item in self.items if item["ticket_id"] == ticket_id]


class FastClassifier:
    async def classify(self, title, description):
        return "GENERAL"


@pytest.fixture
def client():
    repository.clear()
    cache.clear()
    service.events = RecordingEvents()
    service.classifier = FastClassifier()
    with TestClient(app) as test_client:
        yield test_client
    repository.clear()
    cache.clear()


@pytest.fixture
def auth():
    return lambda token="alice-token": {"Authorization": f"Bearer {token}"}


@pytest.fixture
def create_ticket(client, auth):
    def create(token="alice-token", **overrides):
        payload = {
            "title": "Не работает личный кабинет",
            "description": "После входа вижу пустую страницу",
            "priority": "MEDIUM",
            **overrides,
        }
        response = client.post("/api/v1/tickets", json=payload, headers=auth(token))
        assert response.status_code == 201, response.text
        return response.json()

    return create

