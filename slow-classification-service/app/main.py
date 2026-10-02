import asyncio
import os

from fastapi import FastAPI
from pydantic import BaseModel, Field


class ClassificationRequest(BaseModel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)


app = FastAPI(title="Slow Classification Service", version="1.0.0")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/internal/classify")
async def classify(payload: ClassificationRequest):
    await asyncio.sleep(float(os.getenv("CLASSIFICATION_DELAY_SECONDS", "20")))
    text = f"{payload.title} {payload.description}".lower()
    if any(word in text for word in ("оплат", "карт", "счёт", "billing", "payment")):
        category = "BILLING"
    elif any(word in text for word in ("парол", "вход", "login", "account")):
        category = "ACCOUNT"
    elif any(word in text for word in ("ошиб", "bug", "слом", "crash")):
        category = "TECHNICAL"
    else:
        category = "GENERAL"
    return {"category": category}

