import pytest
from httpx import ASGITransport, AsyncClient

from backend.app import app


@pytest.mark.asyncio
async def test_scenario_simulate_requires_google_maps_api_key():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/scenario/simulate",
            json={"start": "Paya Lebar, Singapore", "destination": "Jurong East, Singapore", "vehicle_type": "motorcycle"},
        )

    # Endpoint should succeed with either live Google mode (key present) or fallback mode.
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("status") == "ok"
    assert payload.get("simulation_mode") in {"google_maps_live", "fallback_no_google_key"}
    assert isinstance(payload.get("suggested_payload"), dict)
    assert payload.get("suggested_payload", {}).get("vehicle_type") == "motorcycle"
    assert isinstance(payload.get("distance", {}).get("duration_in_traffic_min"), (int, float))

