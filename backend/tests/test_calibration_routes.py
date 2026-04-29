import math
import pytest
from httpx import ASGITransport, AsyncClient

from backend.app import app


def _expected_forecast_volume(baseline: float, promo_campaign: bool, holiday_period: bool) -> int:
    multiplier = 1.0 + (0.12 if promo_campaign else 0.0) + (0.18 if holiday_period else 0.0)
    return int(round(baseline * multiplier))


def _expected_delivery_failure_prob(
    customer_present_probability: float,
    address_quality_score: float,
    weather_severity: float,
    prior_failed_attempts: int,
    cod_order: bool,
) -> float:
    def clamp01(x: float) -> float:
        return min(1.0, max(0.0, x))

    cpp = clamp01(customer_present_probability)
    aqs = clamp01(address_quality_score)
    ws = clamp01(weather_severity)
    pfa_term = min(float(prior_failed_attempts) / 3.0, 1.0)
    cod_term = 0.05 if cod_order else 0.0
    failure_probability = (1 - cpp) * 0.35 + (1 - aqs) * 0.25 + ws * 0.2 + pfa_term * 0.15 + cod_term
    failure_probability = round(min(max(failure_probability, 0.0), 0.99), 3)
    return float(failure_probability)


@pytest.mark.asyncio
async def test_forecast_calibration_shapes_and_thresholds():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/forecast/",
            json={
                "region": "SG",
                "date": "2026-04-29",
                "historical_daily_volume": [920, 980, 1015, 1090, 1060, 1120, 1180, 1210, 1265, 1310],
                "promo_campaign": True,
                "holiday_period": False,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["region"] == "SG"
    assert payload["date"] == "2026-04-29"

    pred = payload["prediction"]
    assert isinstance(pred["volume"], int)
    assert pred["trend"] in {"upward", "stable", "downward"}
    assert pred["capacity_risk"] in {"low", "medium", "high"}
    assert pred["recommended_buffer_pct"] in {3, 8, 15}

    # Buffer matches risk label contract.
    if pred["capacity_risk"] == "high":
        assert pred["recommended_buffer_pct"] == 15
    if pred["capacity_risk"] == "medium":
        assert pred["recommended_buffer_pct"] == 8
    if pred["capacity_risk"] == "low":
        assert pred["recommended_buffer_pct"] == 3

    # Calibration shouldn't wildly deviate from old heuristic.
    last7 = [920, 980, 1015, 1090, 1060, 1120, 1180, 1210, 1265, 1310][-7:]
    baseline = sum(last7) / len(last7)
    expected = _expected_forecast_volume(baseline, promo_campaign=True, holiday_period=False)
    assert abs(pred["volume"] - expected) <= max(10, int(0.03 * expected))


@pytest.mark.asyncio
async def test_delivery_failure_calibration_probability_range_and_action():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/delivery/predict",
            json={
                "delivery_id": "D-99271",
                "customer_present_probability": 0.72,
                "address_quality_score": 0.84,
                "weather_severity": 0.45,
                "prior_failed_attempts": 1,
                "cod_order": False,
            },
        )

    assert response.status_code == 200
    payload = response.json()

    fp = payload["failure_probability"]
    assert isinstance(fp, float) and 0.0 <= fp <= 0.99
    assert payload["recommended_action"] in {"confirm_delivery_window", "normal_dispatch"}

    expected = _expected_delivery_failure_prob(
        customer_present_probability=0.72,
        address_quality_score=0.84,
        weather_severity=0.45,
        prior_failed_attempts=1,
        cod_order=False,
    )
    assert abs(fp - expected) <= 0.05

    expected_action = "confirm_delivery_window" if expected >= 0.5 else "normal_dispatch"
    assert payload["recommended_action"] == expected_action

