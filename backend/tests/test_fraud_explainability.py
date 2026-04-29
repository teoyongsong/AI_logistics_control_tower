import pytest
from httpx import ASGITransport, AsyncClient

from backend.app import app


@pytest.mark.asyncio
async def test_fraud_detect_returns_explainability():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/fraud/detect",
            json={
                "claim_id": "C-100",
                "customer_id": "U-1",
                "claim_amount": 250.0,
                "claims_last_90_days": 3,
                "missing_proof_docs": 1,
                "account_age_days": 45,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload.get("explainability"), dict)
    explain = payload["explainability"]
    assert {"inputs", "components", "formula", "thresholds"} <= set(explain.keys())
    assert {"claim_amount_component", "claims_frequency_component", "missing_docs_component", "account_age_component"} <= set(
        explain["components"].keys()
    )
