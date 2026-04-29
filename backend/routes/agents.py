from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any, Dict

from backend.services.langgraph_orchestrator import (
    TOOL_REGISTRY,
    LANGGRAPH_AVAILABLE,
    run_simulation,
    run_simulation_async,
    run_simulation_with_trace,
)
from backend.services.calibrators import evaluate_calibrators

router = APIRouter()


def _langgraph_unavailable_response():
    return {
        "status": "error",
        "message": "LangGraph is not installed. Run: pip install langgraph",
        "available_tools": sorted(TOOL_REGISTRY.keys()),
    }

class ControlTowerRequest(BaseModel):
    region: str
    demand_index: float
    weather: str
    urgency_mix: str
    fleet_health_index: float
    date: str = "2026-04-29"
    origin: str = "Hub-A"
    destination: str = "Region-Cluster-1"
    traffic_level: str = "medium"
    vehicle_type: str = "diesel_van"
    route_distance_km: float = 26.0
    tool_retries: int = 1
    tool_timeout_s: float = 3.0


@router.post("/control")
def control_tower(request: ControlTowerRequest):
    scenario = request.model_dump()
    if not LANGGRAPH_AVAILABLE:
        return _langgraph_unavailable_response()

    result = run_simulation(scenario)
    tool_outputs = result.get("tool_outputs", {})
    return {
        "status": "Agents coordinated successfully",
        "region": request.region,
        "agent_notes": result.get("agent_notes", []),
        "plan": result.get("plan", {}),
        "execution_meta": result.get("execution_meta", {}),
        "tool_outputs": tool_outputs,
    }


@router.post("/control/async")
async def control_tower_async(request: ControlTowerRequest):
    scenario = request.model_dump()
    if not LANGGRAPH_AVAILABLE:
        return _langgraph_unavailable_response()
    result = await run_simulation_async(scenario)
    return {
        "status": "Agents coordinated successfully",
        "region": request.region,
        "agent_notes": result.get("agent_notes", []),
        "plan": result.get("plan", {}),
        "execution_meta": result.get("execution_meta", {}),
        "tool_outputs": result.get("tool_outputs", {}),
    }


@router.post("/control/replay")
def control_tower_replay(request: ControlTowerRequest):
    scenario = request.model_dump()
    if not LANGGRAPH_AVAILABLE:
        return _langgraph_unavailable_response()
    result = run_simulation_with_trace(scenario)
    return {
        "status": "Agents coordinated successfully",
        "region": request.region,
        "agent_notes": result.get("agent_notes", []),
        "plan": result.get("plan", {}),
        "execution_meta": result.get("execution_meta", {}),
        "tool_outputs": result.get("tool_outputs", {}),
    }


class ToolCallRequest(BaseModel):
    tool_name: str
    scenario: Dict[str, Any]


@router.post("/tool-call")
def tool_call(request: ToolCallRequest):
    tool_fn = TOOL_REGISTRY.get(request.tool_name)
    if not tool_fn:
        return {"status": "error", "message": "Unknown tool", "available_tools": sorted(TOOL_REGISTRY.keys())}
    return {"status": "ok", "tool": request.tool_name, "result": tool_fn(request.scenario)}


@router.get("/eval-metrics")
def eval_metrics():
    metrics = evaluate_calibrators(seed=99, n_samples=2000)
    return {
        "status": "ok",
        "metrics": metrics,
        "notes": "Offline calibration metrics for forecast and delivery-failure components.",
    }
