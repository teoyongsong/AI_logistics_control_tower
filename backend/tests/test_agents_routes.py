import pytest
from httpx import ASGITransport, AsyncClient

from backend.app import app


TEST_SCENARIO = {
    "region": "SG",
    "demand_index": 1.2,
    "weather": "rain",
    "urgency_mix": "express",
    "fleet_health_index": 0.9,
    "route_distance_km": 41.3,
    "tool_retries": 1,
    "tool_timeout_s": 3.0,
}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "expect_trace"),
    [
        ("/agents/control", False),
        ("/agents/control/async", False),
        ("/agents/control/replay", True),
    ],
)
async def test_agents_control_endpoints(path: str, expect_trace: bool):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(path, json=TEST_SCENARIO)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"Agents coordinated successfully", "error"}

    # If LangGraph is unavailable in the environment, API returns a controlled error payload.
    if payload["status"] == "error":
        assert "LangGraph is not installed" in payload["message"]
        assert isinstance(payload.get("available_tools"), list)
        return

    assert payload["region"] == TEST_SCENARIO["region"]
    assert isinstance(payload.get("agent_notes"), list)
    assert isinstance(payload.get("plan"), dict)
    assert isinstance(payload.get("tool_outputs"), dict)
    assert isinstance(payload["plan"].get("kpi_deltas"), dict)
    assert {"eta_delta_min", "cost_delta", "risk_delta", "co2_delta_kg"} <= set(payload["plan"]["kpi_deltas"].keys())
    assert isinstance(payload.get("execution_meta", {}).get("branch_decisions", []), list)
    route_tool = payload.get("tool_outputs", {}).get("optimize_route", {}).get("data", {})
    if isinstance(route_tool, dict):
        route_metrics = route_tool.get("metrics", {})
        if isinstance(route_metrics, dict) and "estimated_distance_km" in route_metrics:
            assert abs(float(route_metrics["estimated_distance_km"]) - TEST_SCENARIO["route_distance_km"]) < 0.01

    if expect_trace:
        execution_meta = payload.get("execution_meta", {})
        assert isinstance(execution_meta.get("trace"), list)
        assert execution_meta.get("total_steps", 0) >= 1
    else:
        # Sync and async routes still expose execution meta even when trace is absent.
        assert isinstance(payload.get("execution_meta"), dict)


@pytest.mark.asyncio
async def test_agents_eval_metrics_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/agents/eval-metrics")

    assert response.status_code == 200
    payload = response.json()
    assert payload.get("status") == "ok"
    assert isinstance(payload.get("notes"), str)

    metrics = payload.get("metrics", {})
    assert isinstance(metrics, dict)
    assert {"forecast_mae", "failure_brier_like", "samples"} <= set(metrics.keys())
    assert isinstance(metrics["forecast_mae"], float)
    assert isinstance(metrics["failure_brier_like"], float)
    assert metrics["samples"] >= 1
