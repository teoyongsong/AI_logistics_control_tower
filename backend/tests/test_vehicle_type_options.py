import pytest
from httpx import ASGITransport, AsyncClient

from backend.app import app


@pytest.mark.asyncio
async def test_carbon_supports_motorcycle_vehicle_type():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/carbon/optimize",
            json={
                "route_distance_km": 20,
                "vehicle_type": "motorcycle",
                "grid_carbon_intensity": 0.45,
                "delivery_urgency": "standard",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert "estimated_emissions_kg" in payload
    assert payload["estimated_emissions_kg"] > 0


@pytest.mark.asyncio
async def test_carbon_supports_ui_vehicle_labels():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        diesel_res = await client.post(
            "/carbon/optimize",
            json={
                "route_distance_km": 20,
                "vehicle_type": "diesel",
                "grid_carbon_intensity": 0.45,
                "delivery_urgency": "standard",
            },
        )
        ev_res = await client.post(
            "/carbon/optimize",
            json={
                "route_distance_km": 20,
                "vehicle_type": "EV",
                "grid_carbon_intensity": 0.45,
                "delivery_urgency": "standard",
            },
        )

    assert diesel_res.status_code == 200
    assert ev_res.status_code == 200
    diesel_payload = diesel_res.json()
    ev_payload = ev_res.json()
    assert ev_payload["estimated_emissions_kg"] < diesel_payload["estimated_emissions_kg"]

