import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.integration
known_issue = pytest.mark.xfail(strict=True, reason="зафиксированный тикет лабораторной")
ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_event_history_preserves_order():
    module = load_module("event_service_main", ROOT / "event-service/app/main.py")
    module.store.clear()
    client = TestClient(module.app)
    first = {
        "event_id": "event-1",
        "event_type": "ticket.created",
        "ticket_id": "ticket-1",
        "occurred_at": "2026-09-18T10:00:00Z",
        "data": {"author_id": "alice"},
    }
    second = {
        "event_id": "event-2",
        "event_type": "ticket.classified",
        "ticket_id": "ticket-1",
        "occurred_at": "2026-09-18T10:00:20Z",
        "data": {"category": "BILLING"},
    }
    assert client.post("/internal/events", json=first).status_code == 201
    assert client.post("/internal/events", json=second).status_code == 201
    response = client.get("/internal/events", params={"ticket_id": "ticket-1"})
    assert [item["event_id"] for item in response.json()["items"]] == [
        "event-1",
        "event-2",
    ]


@known_issue
def test_priority_activity_is_accepted_by_history_service():
    module = load_module("event_service_contract", ROOT / "event-service/app/main.py")
    module.store.clear()
    client = TestClient(module.app)
    response = client.post(
        "/internal/events",
        json={
            "event_id": "event-3",
            "event_type": "ticket.priority_changed",
            "ticket_id": "ticket-1",
            "occurred_at": "2026-09-18T10:01:00Z",
            "details": {"from": "LOW", "to": "HIGH"},
        },
    )
    assert response.status_code == 201


@known_issue
def test_public_entrypoint_routes_api_to_available_service():
    config = (ROOT / "nginx/nginx.conf").read_text()
    assert "server tickets-api:8000;" in config

