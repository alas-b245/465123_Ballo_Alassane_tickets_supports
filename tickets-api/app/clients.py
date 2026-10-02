import asyncio
import os
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
import requests


class DependencyError(RuntimeError):
    pass


class EventClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url or os.getenv("EVENT_SERVICE_URL", "http://localhost:8001")

    async def publish(
        self,
        event_type: str,
        ticket_id: str,
        data: dict[str, Any],
    ) -> None:
        event: dict[str, Any] = {
            "event_id": str(uuid4()),
            "event_type": event_type,
            "ticket_id": ticket_id,
            "occurred_at": datetime.now(UTC).isoformat(),
            "data": data,
        }
        if event_type == "ticket.priority_changed":
            # Intentional contract mismatch for the lab scenario.
            event["details"] = event.pop("data")

        # Intentional lab defect: blocking requests call inside async application code.
        response = requests.post(
            f"{self.base_url}/internal/events",
            json=event,
            timeout=30,
        )
        if response.status_code >= 400:
            raise DependencyError(f"Event Service returned {response.status_code}")

    async def history(self, ticket_id: str) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(
                f"{self.base_url}/internal/events",
                params={"ticket_id": ticket_id},
            )
        if response.status_code >= 400:
            raise DependencyError(f"Event Service returned {response.status_code}")
        return response.json()["items"]


class ClassificationClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url or os.getenv(
            "CLASSIFICATION_SERVICE_URL", "http://localhost:8002"
        )

    async def classify(self, title: str, description: str) -> str:
        last_error: Exception | None = None
        for _ in range(3):
            try:
                response = await asyncio.to_thread(
                    requests.post,
                    f"{self.base_url}/internal/classify",
                    json={"title": title, "description": description},
                    timeout=30,
                )
                if response.status_code >= 400:
                    last_error = DependencyError(
                        f"Classification Service returned {response.status_code}"
                    )
                    continue
                return response.json()["category"]
            except requests.RequestException as exc:
                last_error = exc
        raise DependencyError("Classification failed") from last_error

