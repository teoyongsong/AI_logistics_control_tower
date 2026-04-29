import pytest
from httpx import ASGITransport, AsyncClient

from backend.app import app


@pytest.mark.asyncio
async def test_route_endpoint_respects_provided_route_distance():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/route/",
            json={
                "origin": "A",
                "destination": "B",
                "traffic_level": "medium",
                "weather": "clear",
                "vehicle_type": "diesel_van",
                "route_distance_km": 41.3,
                "waypoints": [],
                "constraints": {},
            },
        )

    assert response.status_code == 200
    payload = response.json()
    metrics = payload.get("metrics", {})
    assert metrics.get("estimated_distance_km") == 41.3

