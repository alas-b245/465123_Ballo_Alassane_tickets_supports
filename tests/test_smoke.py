def test_service_reports_readiness(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_card_can_be_created_and_opened(client, auth, create_ticket):
    created = create_ticket()
    response = client.get(f"/api/v1/tickets/{created['id']}", headers=auth())
    assert response.status_code == 200
    assert response.json()["title"] == created["title"]
    assert response.json()["category"] == "GENERAL"


def test_operator_change_appears_in_timeline(client, auth, create_ticket):
    created = create_ticket()
    changed = client.patch(
        f"/api/v1/tickets/{created['id']}/status",
        json={"status": "IN_PROGRESS"},
        headers=auth("support-token"),
    )
    assert changed.status_code == 200

    history = client.get(
        f"/api/v1/tickets/{created['id']}/history",
        headers=auth("support-token"),
    )
    assert history.status_code == 200
    assert [item["event_type"] for item in history.json()["items"]] == [
        "ticket.created",
        "ticket.classified",
        "ticket.status_changed",
    ]


def test_anonymous_request_is_rejected(client):
    response = client.get("/api/v1/tickets")
    assert response.status_code == 401

