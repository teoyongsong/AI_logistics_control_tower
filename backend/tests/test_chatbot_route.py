import pytest
from httpx import ASGITransport, AsyncClient

from backend.app import app


@pytest.mark.asyncio
async def test_chatbot_delivery_eta_answer_grounded():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/chatbot/query",
            json={"query": "Where is my parcel?", "tracking_id": "TRK-445901"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "Where is my parcel?"
    assert isinstance(payload["answer"], str) and payload["answer"]
    assert isinstance(payload["retrieval"], list) and len(payload["retrieval"]) >= 1

    # The KB sentence includes "expected to arrive ... local time".
    assert "expected to arrive" in payload["answer"]
    assert payload["escalate_to_human"] in {True, False}


@pytest.mark.asyncio
async def test_chatbot_refund_claim_answer_grounded():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/chatbot/query",
            json={"query": "How do I request a refund / claim?", "tracking_id": None},
        )

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["answer"], str) and payload["answer"]
    assert isinstance(payload["retrieval"], list) and len(payload["retrieval"]) >= 1
    assert "filing a claim" in payload["answer"].lower()


@pytest.mark.asyncio
async def test_chatbot_complaint_escalates():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/chatbot/query",
            json={"query": "This is a complaint about delivery delay.", "tracking_id": None},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["escalate_to_human"] is True

