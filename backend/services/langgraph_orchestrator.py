from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Any, Callable, Dict, List, TypedDict

from backend.config import BASELINE_KPIS, RISK_THRESHOLDS
from backend.routes.carbon import CarbonRequest, carbon_optimization
from backend.routes.chatbot import ChatbotRequest, chatbot_query
from backend.routes.delivery_failure import DeliveryFailureRequest, delivery_failure
from backend.routes.forecast import ForecastRequest, forecast_shipments
from backend.routes.fraud import FraudRequest, detect_fraud
from backend.routes.maintenance import MaintenanceRequest, predictive_maintenance
from backend.routes.optimize_route import RouteRequest, optimize_route
from backend.routes.pricing import PricingRequest, dynamic_pricing
from backend.routes.warehouse import PickTask, PickingRequest, warehouse_picking

try:
    from langgraph.graph import END, START, StateGraph

    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    END = "END"
    START = "START"
    StateGraph = None


class OrchestrationState(TypedDict, total=False):
    scenario: Dict[str, Any]
    tool_outputs: Dict[str, Any]
    agent_notes: List[str]
    plan: Dict[str, Any]
    execution_meta: Dict[str, Any]


def _record_branch_decision(state: OrchestrationState, step: str, decision: Dict[str, Any]) -> None:
    meta = state.setdefault("execution_meta", {})
    decisions = meta.setdefault("branch_decisions", [])
    if isinstance(decisions, list):
        decisions.append({"step": step, **decision})


def _forecast_tool(scenario: Dict[str, Any]) -> Dict[str, Any]:
    req = ForecastRequest(
        region=scenario["region"],
        date=scenario.get("date", "2026-04-29"),
        historical_daily_volume=scenario.get(
            "historical_daily_volume",
            [920, 980, 1015, 1090, 1060, 1120, 1180, 1210, 1265, 1310],
        ),
        promo_campaign=scenario.get("promo_campaign", False),
        holiday_period=scenario.get("holiday_period", False),
    )
    return forecast_shipments(req)


def _route_tool(scenario: Dict[str, Any]) -> Dict[str, Any]:
    req = RouteRequest(
        origin=scenario.get("origin", "Hub-A"),
        destination=scenario.get("destination", "Region-Cluster-1"),
        traffic_level=scenario.get("traffic_level", "medium"),
        weather=scenario.get("weather", "clear"),
        vehicle_type=scenario.get("vehicle_type", "van"),
        route_distance_km=scenario.get("route_distance_km"),
        waypoints=scenario.get("waypoints", ["Checkpoint-1", "Checkpoint-2"]),
        constraints={"maximize_ontime": "true"},
    )
    return optimize_route(req)


def _warehouse_tool(scenario: Dict[str, Any]) -> Dict[str, Any]:
    tasks = [
        PickTask(item_id="SKU-FAST-1", aisle=2, shelf=5, demand_score=0.9),
        PickTask(item_id="SKU-FAST-2", aisle=3, shelf=3, demand_score=0.85),
        PickTask(item_id="SKU-LONG-1", aisle=8, shelf=2, demand_score=0.4),
    ]
    req = PickingRequest(
        picker_start_aisle=scenario.get("picker_start_aisle", 4),
        tasks=tasks,
    )
    return warehouse_picking(req)


def _maintenance_tool(scenario: Dict[str, Any]) -> Dict[str, Any]:
    req = MaintenanceRequest(
        vehicle_id=scenario.get("vehicle_id", "Truck-42"),
        engine_temp_c=scenario.get("engine_temp_c", 92.0),
        vibration_score=scenario.get("vibration_score", 5.8),
        mileage_km=scenario.get("mileage_km", 124000),
        dtc_count=scenario.get("dtc_count", 2),
    )
    return predictive_maintenance(req)


def _fraud_tool(scenario: Dict[str, Any]) -> Dict[str, Any]:
    req = FraudRequest(
        claim_id=scenario.get("claim_id", "C-2026-004"),
        customer_id=scenario.get("customer_id", "U-9981"),
        claim_amount=scenario.get("claim_amount", 180.0),
        claims_last_90_days=scenario.get("claims_last_90_days", 1),
        missing_proof_docs=scenario.get("missing_proof_docs", 0),
        account_age_days=scenario.get("account_age_days", 380),
    )
    return detect_fraud(req)


def _chatbot_tool(scenario: Dict[str, Any]) -> Dict[str, Any]:
    req = ChatbotRequest(
        query=scenario.get("support_query", "Where is my parcel?"),
        tracking_id=scenario.get("tracking_id", "TRK-445901"),
        confidence_threshold=scenario.get("chat_confidence_threshold", 0.65),
    )
    return chatbot_query(req)


def _pricing_tool(scenario: Dict[str, Any]) -> Dict[str, Any]:
    req = PricingRequest(
        distance_km=scenario.get("pricing_distance_km", 26.0),
        urgency=scenario.get("urgency_mix", "standard"),
        demand_index=scenario.get("demand_index", 1.0),
        fuel_price_per_liter=scenario.get("fuel_price_per_liter", 2.1),
        package_weight_kg=scenario.get("package_weight_kg", 1.6),
    )
    return dynamic_pricing(req)


def _derive_address_quality_score(scenario: Dict[str, Any]) -> float:
    """Lower score = worse address / instructions data → higher failure risk."""
    if "address_quality_score" in scenario:
        return float(scenario["address_quality_score"])
    base = 0.84
    weather = str(scenario.get("weather", "clear"))
    traffic = str(scenario.get("traffic_level", "medium"))
    urgency = str(scenario.get("urgency_mix", "standard"))
    demand = float(scenario.get("demand_index", 1.0))
    stress = 0.0
    if traffic == "high":
        stress += 0.10
    if weather == "storm":
        stress += 0.14
    elif weather == "rain":
        stress += 0.06
    if urgency == "same_day":
        stress += 0.08
    elif urgency == "express":
        stress += 0.03
    if demand > 1.1:
        stress += 0.08 * min(1.0, (demand - 1.1) / 0.7)
    return max(0.40, min(0.99, base - stress))


def _delivery_failure_tool(scenario: Dict[str, Any]) -> Dict[str, Any]:
    # Map Control Tower scenario fields into the last-mile failure model.
    # Previously only fixed defaults were used, so failure_probability never moved (e.g. always 0.178).
    # With fixed address + capped prior attempts, the weighted sum could not exceed ~0.46; we derive
    # address stress from the UI so severe scenarios can cross 0.5 (confirm_delivery_window threshold).
    if "weather_severity" in scenario:
        weather_severity = float(scenario["weather_severity"])
    else:
        weather = str(scenario.get("weather", "clear"))
        # Storm at 1.0 uses full weather term in delivery_failure (max 0.2).
        weather_severity = {"clear": 0.1, "rain": 0.45, "storm": 1.0}.get(weather, 0.2)

    traffic = str(scenario.get("traffic_level", "medium"))
    traffic_customer_adj = {"low": 0.02, "medium": 0.0, "high": -0.06}.get(traffic, 0.0)

    urgency = str(scenario.get("urgency_mix", "standard"))
    urgency_customer_adj = {"standard": 0.0, "express": -0.02, "same_day": -0.05}.get(urgency, 0.0)

    base_customer = float(scenario.get("customer_present_probability", 0.72))
    demand = float(scenario.get("demand_index", 1.0))
    demand_customer_adj = -0.04 * max(0.0, demand - 1.0)

    customer_present_probability = base_customer + traffic_customer_adj + urgency_customer_adj + demand_customer_adj
    customer_present_probability = max(0.05, min(0.99, customer_present_probability))

    if "prior_failed_attempts" in scenario:
        prior_failed_attempts = int(scenario["prior_failed_attempts"])
    else:
        fleet = float(scenario.get("fleet_health_index", 0.9))
        prior_failed_attempts = min(3, max(0, int(round((1.0 - fleet) * 3))))
        # Peak-load same-day is more likely to need reattempts.
        if urgency == "same_day" and prior_failed_attempts < 3:
            prior_failed_attempts += 1

    address_quality_score = _derive_address_quality_score(scenario)

    cod_order = bool(scenario.get("cod_order", False))
    if not cod_order and urgency == "same_day" and demand >= 1.4:
        cod_order = True

    req = DeliveryFailureRequest(
        delivery_id=scenario.get("delivery_id", "D-99271"),
        customer_present_probability=customer_present_probability,
        address_quality_score=address_quality_score,
        weather_severity=weather_severity,
        prior_failed_attempts=prior_failed_attempts,
        cod_order=cod_order,
    )
    return delivery_failure(req)


def _carbon_tool(scenario: Dict[str, Any]) -> Dict[str, Any]:
    req = CarbonRequest(
        route_distance_km=scenario.get("route_distance_km", 26.0),
        vehicle_type=scenario.get("vehicle_type", "diesel_van"),
        grid_carbon_intensity=scenario.get("grid_carbon_intensity", 0.45),
        delivery_urgency=scenario.get("urgency_mix", "standard"),
    )
    return carbon_optimization(req)


TOOL_REGISTRY: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "forecast": _forecast_tool,
    "optimize_route": _route_tool,
    "warehouse": _warehouse_tool,
    "maintenance": _maintenance_tool,
    "fraud": _fraud_tool,
    "chatbot": _chatbot_tool,
    "pricing": _pricing_tool,
    "delivery_failure": _delivery_failure_tool,
    "carbon": _carbon_tool,
}


def _merge_state(current: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(current)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        elif isinstance(value, list) and isinstance(merged.get(key), list):
            merged[key] = [*merged[key], *value]
        else:
            merged[key] = value
    return merged


def _call_with_retry(
    tool_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
    scenario: Dict[str, Any],
    tool_name: str,
    retries: int,
    timeout_s: float,
) -> Dict[str, Any]:
    last_error: str | None = None
    for attempt in range(1, retries + 2):
        started = time.perf_counter()
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(tool_fn, scenario)
                result = future.result(timeout=timeout_s)
            return {
                "status": "ok",
                "attempt": attempt,
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "data": result,
            }
        except FutureTimeoutError:
            last_error = f"timeout after {timeout_s}s"
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            last_error = str(exc)
    return {
        "status": "error",
        "attempt": retries + 1,
        "latency_ms": int((time.perf_counter() - started) * 1000),
        "error": f"{tool_name} failed: {last_error}",
    }


def _run_tool(state: OrchestrationState, tool_name: str) -> OrchestrationState:
    scenario = state["scenario"]
    retries = int(scenario.get("tool_retries", 1))
    timeout_s = float(scenario.get("tool_timeout_s", 3.0))
    tool_outputs = dict(state.get("tool_outputs", {}))
    tool_outputs[tool_name] = _call_with_retry(
        TOOL_REGISTRY[tool_name],
        scenario,
        tool_name,
        retries=retries,
        timeout_s=timeout_s,
    )
    return {"tool_outputs": tool_outputs}


def demand_agent_node(state: OrchestrationState) -> OrchestrationState:
    node_update = _run_tool(state, "forecast")
    notes = list(state.get("agent_notes", []))
    notes.append("Demand agent predicted shipment trend and required buffer.")
    node_update["agent_notes"] = notes
    return node_update


def route_agent_node(state: OrchestrationState) -> OrchestrationState:
    route_update = _run_tool(state, "optimize_route")
    carbon_update = _run_tool(state, "carbon")
    delivery_update = _run_tool(state, "delivery_failure")
    notes = list(state.get("agent_notes", []))
    notes.append("Route agent optimized ETA, carbon profile, and failure risk.")
    return {
        "tool_outputs": {
            **state.get("tool_outputs", {}),
            **route_update["tool_outputs"],
            **carbon_update["tool_outputs"],
            **delivery_update["tool_outputs"],
        },
        "agent_notes": notes,
    }


def warehouse_agent_node(state: OrchestrationState) -> OrchestrationState:
    warehouse_update = _run_tool(state, "warehouse")
    maintenance_update = _run_tool(state, "maintenance")
    notes = list(state.get("agent_notes", []))
    notes.append("Warehouse agent optimized picking and checked fleet readiness.")
    return {
        "tool_outputs": {
            **state.get("tool_outputs", {}),
            **warehouse_update["tool_outputs"],
            **maintenance_update["tool_outputs"],
        },
        "agent_notes": notes,
    }


def support_agent_node(state: OrchestrationState) -> OrchestrationState:
    chatbot_update = _run_tool(state, "chatbot")
    fraud_update = _run_tool(state, "fraud")
    notes = list(state.get("agent_notes", []))
    notes.append("Support agent prepared customer response and claims risk score.")
    return {
        "tool_outputs": {
            **state.get("tool_outputs", {}),
            **chatbot_update["tool_outputs"],
            **fraud_update["tool_outputs"],
        },
        "agent_notes": notes,
    }


def pricing_agent_node(state: OrchestrationState) -> OrchestrationState:
    pricing_update = _run_tool(state, "pricing")
    outputs = {**state.get("tool_outputs", {}), **pricing_update["tool_outputs"]}
    forecast_payload = outputs.get("forecast", {}).get("data", {}).get("prediction", {})
    route_payload = outputs.get("optimize_route", {}).get("data", {}).get("metrics", {})
    delivery_payload = outputs.get("delivery_failure", {}).get("data", {})
    pricing_payload = outputs.get("pricing", {}).get("data", {})
    forecast_volume = forecast_payload.get("volume", 0)
    final_plan = {
        "dispatch_buffer_pct": forecast_payload.get("recommended_buffer_pct", 0),
        "target_eta_min": route_payload.get("estimated_eta_min", -1),
        "price_quote": pricing_payload.get("price", -1),
        "failure_probability": delivery_payload.get("failure_probability", 1),
        "co2_kg_estimate": route_payload.get("co2_kg_estimate", -1),
        "forecast_volume": forecast_volume,
    }
    eta = float(final_plan["target_eta_min"]) if final_plan["target_eta_min"] != -1 else BASELINE_KPIS.target_eta_min
    price = float(final_plan["price_quote"]) if final_plan["price_quote"] != -1 else BASELINE_KPIS.price_quote
    failure = (
        float(final_plan["failure_probability"])
        if final_plan["failure_probability"] not in (-1, 1)
        else BASELINE_KPIS.failure_probability
    )
    co2 = float(final_plan["co2_kg_estimate"]) if final_plan["co2_kg_estimate"] != -1 else BASELINE_KPIS.co2_kg_estimate
    final_plan["kpi_deltas"] = {
        "eta_delta_min": round(eta - BASELINE_KPIS.target_eta_min, 2),
        "cost_delta": round(price - BASELINE_KPIS.price_quote, 2),
        "risk_delta": round(failure - BASELINE_KPIS.failure_probability, 3),
        "co2_delta_kg": round(co2 - BASELINE_KPIS.co2_kg_estimate, 3),
    }
    notes = list(state.get("agent_notes", []))
    notes.append("Pricing agent set quote with demand-aware guardrails.")
    meta = dict(state.get("execution_meta", {}))
    meta["risk_review_triggered"] = "risk_review" in notes
    return {"tool_outputs": outputs, "plan": final_plan, "agent_notes": notes, "execution_meta": meta}


def capacity_planning_node(state: OrchestrationState) -> OrchestrationState:
    notes = list(state.get("agent_notes", []))
    notes.append("Capacity planning node activated extra linehaul and sorting shifts.")
    return {"agent_notes": notes}


def risk_review_node(state: OrchestrationState) -> OrchestrationState:
    notes = list(state.get("agent_notes", []))
    notes.append("risk_review")
    notes.append("Risk review node escalated suspicious or fragile deliveries to human oversight.")
    return {"agent_notes": notes}


def _route_after_demand(state: OrchestrationState) -> str:
    forecast = state.get("tool_outputs", {}).get("forecast", {}).get("data", {}).get("prediction", {})
    capacity_risk = forecast.get("capacity_risk", "low")
    decision = "capacity_planning" if capacity_risk == "high" else "route_agent"
    _record_branch_decision(
        state,
        "post_demand",
        {
            "capacity_risk": capacity_risk,
            "selected_next_node": decision,
            "reason": "High capacity risk requires extra linehaul/sorting buffer",
        },
    )
    return decision


def _route_after_support(state: OrchestrationState) -> str:
    fraud_prob = state.get("tool_outputs", {}).get("fraud", {}).get("data", {}).get("fraud_probability", 0.0)
    failure_prob = state.get("tool_outputs", {}).get("delivery_failure", {}).get("data", {}).get("failure_probability", 0.0)
    risk_review_needed = (
        fraud_prob >= RISK_THRESHOLDS.fraud_probability_review
        or failure_prob >= RISK_THRESHOLDS.failure_probability_review
    )
    decision = "risk_review" if risk_review_needed else "pricing_agent"
    _record_branch_decision(
        state,
        "post_support",
        {
            "fraud_probability": fraud_prob,
            "failure_probability": failure_prob,
            "fraud_threshold": RISK_THRESHOLDS.fraud_probability_review,
            "failure_threshold": RISK_THRESHOLDS.failure_probability_review,
            "selected_next_node": decision,
            "reason": "Escalate to risk review when fraud/failure probability crosses threshold",
        },
    )
    return decision


def build_graph():
    if not LANGGRAPH_AVAILABLE:
        raise RuntimeError(
            "LangGraph is not installed. Run: pip install langgraph"
        )

    graph = StateGraph(OrchestrationState)
    graph.add_node("demand_agent", demand_agent_node)
    graph.add_node("route_agent", route_agent_node)
    graph.add_node("warehouse_agent", warehouse_agent_node)
    graph.add_node("support_agent", support_agent_node)
    graph.add_node("pricing_agent", pricing_agent_node)
    graph.add_node("capacity_planning", capacity_planning_node)
    graph.add_node("risk_review", risk_review_node)

    graph.add_edge(START, "demand_agent")
    graph.add_conditional_edges(
        "demand_agent",
        _route_after_demand,
        {"capacity_planning": "capacity_planning", "route_agent": "route_agent"},
    )
    graph.add_edge("capacity_planning", "route_agent")
    graph.add_edge("route_agent", "warehouse_agent")
    graph.add_edge("warehouse_agent", "support_agent")
    graph.add_conditional_edges(
        "support_agent",
        _route_after_support,
        {"risk_review": "risk_review", "pricing_agent": "pricing_agent"},
    )
    graph.add_edge("risk_review", "pricing_agent")
    graph.add_edge("pricing_agent", END)
    return graph.compile()


def run_simulation(scenario: Dict[str, Any]) -> Dict[str, Any]:
    compiled_graph = build_graph()
    initial_state: OrchestrationState = {
        "scenario": scenario,
        "tool_outputs": {},
        "agent_notes": [],
    }
    return compiled_graph.invoke(initial_state)


def run_simulation_with_trace(scenario: Dict[str, Any]) -> Dict[str, Any]:
    compiled_graph = build_graph()
    initial_state: OrchestrationState = {
        "scenario": scenario,
        "tool_outputs": {},
        "agent_notes": [],
        "execution_meta": {"mode": "replay"},
    }

    trace: List[Dict[str, Any]] = []
    current_state: Dict[str, Any] = dict(initial_state)
    started = time.time()
    step_index = 0
    for event in compiled_graph.stream(initial_state):
        if isinstance(event, dict):
            for node_name, node_payload in event.items():
                if isinstance(node_payload, dict):
                    current_state = _merge_state(current_state, node_payload)
                step_index += 1
                trace.append(
                    {
                        "step": step_index,
                        "node": node_name,
                        "timestamp": time.time(),
                        "elapsed_ms": int((time.time() - started) * 1000),
                        "keys_updated": list(node_payload.keys()) if isinstance(node_payload, dict) else [],
                    }
                )

    result = current_state
    meta = dict(result.get("execution_meta", {}))
    meta["trace"] = trace
    meta["total_steps"] = len(trace)
    result["execution_meta"] = meta
    return result


async def run_simulation_async(scenario: Dict[str, Any]) -> Dict[str, Any]:
    compiled_graph = build_graph()
    initial_state: OrchestrationState = {
        "scenario": scenario,
        "tool_outputs": {},
        "agent_notes": [],
        "execution_meta": {"mode": "async"},
    }
    if hasattr(compiled_graph, "ainvoke"):
        return await compiled_graph.ainvoke(initial_state)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, compiled_graph.invoke, initial_state)
