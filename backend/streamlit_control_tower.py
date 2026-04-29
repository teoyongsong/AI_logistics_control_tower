import json
import time
from urllib import error, parse, request

import streamlit as st

try:
    from backend.config import NINJA_VAN_CONTEXT
except ModuleNotFoundError:
    # Streamlit can execute this file with backend/ as import root.
    from config import NINJA_VAN_CONTEXT

# Market codes aligned to Ninja Van public SEA coverage.
REGION_OPTIONS = NINJA_VAN_CONTEXT["coverage_countries"]
AGENT_COUNT = 7
TOOL_COUNT = 9
AGENT_NAMES = [
    "demand_agent",
    "route_agent",
    "warehouse_agent",
    "support_agent",
    "pricing_agent",
    "capacity_planning",
    "risk_review",
]
TOOL_NAMES = [
    "forecast",
    "optimize_route",
    "warehouse",
    "maintenance",
    "fraud",
    "chatbot",
    "pricing",
    "delivery_failure",
    "carbon",
]

st.set_page_config(page_title="AI Logistics Control Tower", layout="wide")
st.title("AI Logistics Multi-Agent Simulator")
st.caption("Live simulator for LangGraph orchestration via FastAPI endpoints.")
st.caption("Coverage context: Ninja Van operates across SG, MY, PH, ID, TH, VN.")
agent_tooltip = "Agents:\\n- " + "\\n- ".join(AGENT_NAMES)
tool_tooltip = "Tools:\\n- " + "\\n- ".join(TOOL_NAMES)
st.markdown(
    f"""
<style>
.hover-wrap {{
  position: relative;
  display: inline-block;
  margin-right: 18px;
}}
.hover-label {{
  cursor: help;
  font-size: 20px;
  font-weight: 700;
}}
.hover-card {{
  display: none;
  position: absolute;
  top: 30px;
  left: 0;
  z-index: 9999;
  background: #111827;
  color: #f9fafb;
  border-radius: 8px;
  padding: 10px 12px;
  min-width: 220px;
  box-shadow: 0 6px 18px rgba(0,0,0,0.25);
  font-size: 16px;
  line-height: 1.5;
  white-space: pre-line;
}}
.hover-wrap:hover .hover-card {{
  display: block;
}}
</style>
<div style="display:flex; flex-direction:row; align-items:center; margin-bottom: 8px;">
  <div class="hover-wrap">
    <span class="hover-label">Agents ℹ️</span>
    <div class="hover-card">{agent_tooltip.replace("\\n", "<br/>")}</div>
  </div>
  <div class="hover-wrap">
    <span class="hover-label">Tools ℹ️</span>
    <div class="hover-card">{tool_tooltip.replace("\\n", "<br/>")}</div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

api_base = st.sidebar.text_input("FastAPI Base URL", value="http://127.0.0.1:8000")
endpoint_mode = st.sidebar.selectbox("Mode", options=["sync", "async", "replay"], index=0)
view_mode = st.sidebar.selectbox("View", options=["Classic Simulator", "10 Challenges Demo"], index=1)
show_raw_output = st.sidebar.toggle("Show existing raw JSON output", value=False)


def fetch_json(url: str, method: str = "GET", payload: dict | None = None, timeout: int = 20) -> dict:
    req_data = None
    if payload is not None:
        req_data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url=url,
        data=req_data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


if "show_eval_metrics_panel" not in st.session_state:
    st.session_state["show_eval_metrics_panel"] = False

if st.sidebar.button("Fetch Eval Metrics"):
    st.session_state["show_eval_metrics_panel"] = True
if st.sidebar.button("Hide Eval Metrics"):
    st.session_state["show_eval_metrics_panel"] = False

auto_refresh_eval = st.sidebar.toggle("Auto-refresh Eval Metrics", value=False)
auto_refresh_seconds = int(
    st.sidebar.number_input(
        "Eval refresh interval (seconds)",
        min_value=1,
        max_value=300,
        value=15,
        step=1,
        disabled=not auto_refresh_eval,
    )
)

if "generated_scenario_payload" not in st.session_state:
    st.session_state["generated_scenario_payload"] = {}
if "generated_scenario_explain" not in st.session_state:
    st.session_state["generated_scenario_explain"] = {}
if "generated_scenario_meta" not in st.session_state:
    st.session_state["generated_scenario_meta"] = {}
if "customer_chat_messages" not in st.session_state:
    st.session_state["customer_chat_messages"] = []
if "latest_simulation_result" not in st.session_state:
    st.session_state["latest_simulation_result"] = None
if "latest_simulation_mode" not in st.session_state:
    st.session_state["latest_simulation_mode"] = "sync"
if "last_customer_chat_ts" not in st.session_state:
    st.session_state["last_customer_chat_ts"] = 0.0
if "form_weather" not in st.session_state:
    st.session_state["form_weather"] = "clear"
if "form_traffic_level" not in st.session_state:
    st.session_state["form_traffic_level"] = "medium"

st.subheader("Real-life Scenario Builder")
start_point = st.text_input("Collection Point (Start)", value="Paya Lebar, Singapore")
destination_point = st.text_input("Delivery Point (Destination)", value="Jurong East, Singapore")
scenario_vehicle_type = st.selectbox(
    "Scenario Vehicle Type",
    options=["van", "motorcycle"],
    index=0,
    help="Used to estimate travel time based on selected vehicle.",
)
maps_link = (
    "https://www.google.com/maps/dir/?api=1"
    f"&origin={parse.quote_plus(start_point)}"
    f"&destination={parse.quote_plus(destination_point)}"
    "&travelmode=driving"
)
st.markdown(f"[Open Route Preview in Google Maps]({maps_link})")
if st.button("Create Scenario (Google Maps + Weather Forecast)"):
    try:
        simulation = fetch_json(
            f"{api_base}/scenario/simulate",
            method="POST",
            payload={
                "start": start_point,
                "destination": destination_point,
                "vehicle_type": scenario_vehicle_type,
            },
        )
        suggested = simulation.get("suggested_payload", {}) if isinstance(simulation, dict) else {}
        if isinstance(suggested, dict) and suggested:
            st.session_state["generated_scenario_payload"] = suggested
            st.session_state["generated_scenario_explain"] = simulation.get("estimated_indices", {})
            st.session_state["generated_scenario_meta"] = {
                "distance": simulation.get("distance", {}),
                "traffic_level": simulation.get("traffic_level"),
                "weather": simulation.get("weather", {}),
                "simulation_mode": simulation.get("simulation_mode"),
            }
            if str(suggested.get("weather", "")) in {"clear", "rain", "storm"}:
                st.session_state["form_weather"] = str(suggested.get("weather"))
            if str(suggested.get("traffic_level", "")) in {"low", "medium", "high"}:
                st.session_state["form_traffic_level"] = str(suggested.get("traffic_level"))
            explain = st.session_state.get("generated_scenario_explain", {})
            if isinstance(explain, dict) and explain:
                with st.expander("How Demand Index and Fleet Health Index were estimated"):
                    demand_exp = explain.get("demand_index", {})
                    fleet_exp = explain.get("fleet_health_index", {})
                    st.write(
                        f"- Demand Index: {demand_exp.get('value', '-')}"
                        f" using `{demand_exp.get('formula', '')}` "
                        f"with factors {demand_exp.get('factors', {})}"
                    )
                    st.write(
                        f"- Fleet Health Index: {fleet_exp.get('value', '-')}"
                        f" using `{fleet_exp.get('formula', '')}` "
                        f"with factors {fleet_exp.get('factors', {})}"
                    )
        else:
            st.warning("Scenario simulation returned no suggested payload.")
    except error.HTTPError as http_err:
        detail = http_err.read().decode("utf-8", errors="ignore")
        st.error(f"Scenario simulation API error: {http_err.code}")
        st.code(detail)
    except Exception as exc:
        st.error(f"Scenario simulation request failed: {exc}")

scenario_meta = st.session_state.get("generated_scenario_meta", {})
if isinstance(scenario_meta, dict) and scenario_meta:
    st.success("Scenario generated from maps distance/traffic and weather forecast.")
    dist = scenario_meta.get("distance", {}) if isinstance(scenario_meta.get("distance"), dict) else {}
    weather_meta = scenario_meta.get("weather", {}) if isinstance(scenario_meta.get("weather"), dict) else {}
    st.caption(
        f"Distance {dist.get('distance_km', '-') } km, "
        f"Time {dist.get('duration_in_traffic_min', '-') } min, "
        f"Traffic: {scenario_meta.get('traffic_level', '-')}, "
        f"Weather: {weather_meta.get('weather', '-')}"
    )
    if scenario_meta.get("simulation_mode") == "fallback_no_google_key":
        st.info("Using fallback mode (no GOOGLE_MAPS_API_KEY). Distance/traffic are estimated heuristics.")


def render_eval_metrics_panel(api_base: str) -> None:
    st.subheader("Eval Metrics")
    endpoint = "/agents/eval-metrics"
    try:
        result = fetch_json(f"{api_base}{endpoint}", method="GET")
        metrics = result.get("metrics", {}) if isinstance(result, dict) else {}
        c1, c2, c3 = st.columns(3)
        c1.metric("Forecast MAE", metrics.get("forecast_mae", "-"))
        c2.metric("Failure Brier-like", metrics.get("failure_brier_like", "-"))
        c3.metric("Samples", metrics.get("samples", "-"))
        if isinstance(result, dict):
            st.caption(result.get("notes", ""))
        with st.expander("Raw Eval Metrics JSON"):
            st.json(result)
    except error.HTTPError as http_err:
        detail = http_err.read().decode("utf-8", errors="ignore")
        st.error(f"Eval metrics API error: {http_err.code}")
        st.code(detail)
    except Exception as exc:
        st.error(f"Eval metrics request failed: {exc}")


def get_tool_data(tools: dict, key: str) -> dict:
    payload = tools.get(key, {})
    if isinstance(payload, dict) and "data" in payload and isinstance(payload["data"], dict):
        return payload["data"]
    return payload if isinstance(payload, dict) else {}


def render_explainability_block(title: str, explainability: dict) -> None:
    if not isinstance(explainability, dict) or not explainability:
        return
    with st.expander(title):
        inputs = explainability.get("inputs", {})
        components = explainability.get("components", {})
        formula = explainability.get("formula", "")
        thresholds = explainability.get("thresholds", {})

        st.markdown("**In simple terms**")
        for key, value in (inputs or {}).items():
            label = str(key).replace("_", " ")
            st.write(f"- We looked at **{label}** = `{value}`.")
        for key, value in (components or {}).items():
            label = str(key).replace("_", " ")
            st.write(f"- This contributed to the result through **{label}** = `{value}`.")
        if thresholds:
            st.write("- We also checked decision cutoffs (thresholds) to pick the final label/action.")

        st.markdown("---")
        st.markdown("**Technical Details**")
        if isinstance(inputs, dict) and inputs:
            st.markdown("**Inputs**")
            st.json(inputs)
        if isinstance(components, dict) and components:
            st.markdown("**Components**")
            st.json(components)
        if formula:
            st.markdown("**Formula**")
            st.code(str(formula))
        if isinstance(thresholds, dict) and thresholds:
            st.markdown("**Thresholds**")
            st.json(thresholds)


def render_classic_view(result: dict, endpoint_mode: str) -> None:
    plan = result.get("plan", {})
    a1, a2 = st.columns(2)
    a1.metric("Agents", AGENT_COUNT)
    a2.metric("Tools", TOOL_COUNT)
    c1, c2, c3 = st.columns(3)
    c1.metric("Target ETA (min)", plan.get("target_eta_min", "-"))
    c2.metric("Price Quote", plan.get("price_quote", "-"))
    c3.metric("Failure Probability", plan.get("failure_probability", "-"))
    deltas = plan.get("kpi_deltas", {})
    if isinstance(deltas, dict) and deltas:
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("ETA Delta (min)", deltas.get("eta_delta_min", "-"))
        d2.metric("Cost Delta", deltas.get("cost_delta", "-"))
        d3.metric("Risk Delta", deltas.get("risk_delta", "-"))
        d4.metric("CO2 Delta (kg)", deltas.get("co2_delta_kg", "-"))

    st.subheader("Agent Notes")
    for note in result.get("agent_notes", []):
        st.write(f"- {note}")

    st.subheader("Execution Summary")
    execution_meta = result.get("execution_meta", {})
    m1, m2 = st.columns(2)
    m1.metric("Risk Review Triggered", "Yes" if execution_meta.get("risk_review_triggered") else "No")
    m2.metric("Trace Steps", execution_meta.get("total_steps", 0) if endpoint_mode == "replay" else "-")
    decisions = execution_meta.get("branch_decisions", [])
    if isinstance(decisions, list) and decisions:
        with st.expander("Branch Decision Rationale"):
            for d in decisions:
                st.write(f"- {d.get('step')}: selected `{d.get('selected_next_node')}` ({d.get('reason')})")

    if endpoint_mode == "replay":
        trace = result.get("execution_meta", {}).get("trace", [])
        st.subheader("Replay Timeline")
        if trace:
            for step in trace:
                node = step.get("node", "unknown")
                elapsed = step.get("elapsed_ms", "-")
                updated = ", ".join(step.get("keys_updated", []))
                st.write(f"Step {step.get('step')}: `{node}` at {elapsed} ms (updated: {updated})")
        else:
            st.info("No trace events returned by replay endpoint.")

    if show_raw_output:
        st.subheader("Execution Meta (Raw)")
        st.json(execution_meta)
        st.subheader("Tool Outputs (Raw)")
        st.json(result.get("tool_outputs", {}))


def render_customer_service_chat(api_base: str) -> None:
    st.markdown("**Customer Service Chat (Simulation)**")
    tracking_id = st.text_input("Tracking ID (optional)", value="TRK-445901", key="customer_chat_tracking_id")
    confidence_threshold = st.slider(
        "Confidence threshold",
        min_value=0.10,
        max_value=0.95,
        value=0.65,
        step=0.05,
        key="customer_chat_confidence_threshold",
    )
    if st.button("Clear Chat", key="clear_customer_chat"):
        st.session_state["customer_chat_messages"] = []

    for msg in st.session_state["customer_chat_messages"]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    with st.form("customer_chat_form", clear_on_submit=True):
        draft = st.text_input(
            "Customer Question",
            value="",
            key="customer_chat_prompt_input",
            placeholder="Ask about delivery, refund, claims, etc.",
        )
        send = st.form_submit_button("Send")

    prompt = draft.strip() if send else ""
    if not prompt:
        return

    st.session_state["last_customer_chat_ts"] = time.time()
    st.session_state["customer_chat_messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    try:
        payload = {
            "query": prompt,
            "tracking_id": tracking_id or None,
            "confidence_threshold": float(confidence_threshold),
        }
        response = fetch_json(f"{api_base}/chatbot/query", method="POST", payload=payload)
        answer = str(response.get("answer", "I am unable to answer right now."))
        escalation = bool(response.get("escalate_to_human", False))
        suffix = "\n\n(Escalation: routed to human support)" if escalation else ""
        full_answer = f"{answer}{suffix}"
    except error.HTTPError as http_err:
        detail = http_err.read().decode("utf-8", errors="ignore")
        full_answer = f"API error: {http_err.code}\n{detail}"
    except Exception as exc:
        full_answer = f"Request failed: {exc}"

    st.session_state["customer_chat_messages"].append({"role": "assistant", "content": full_answer})
    with st.chat_message("assistant"):
        st.write(full_answer)


def render_challenges_demo(result: dict, endpoint_mode: str, api_base: str) -> None:
    st.subheader("10 AI Challenges Demonstration")
    plan = result.get("plan", {})
    h1, h2, h3, h4, h5, h6 = st.columns(6)
    h1.metric("Forecast Volume", plan.get("forecast_volume", "-"))
    h2.metric("ETA (min)", plan.get("target_eta_min", "-"))
    h3.metric("Price Quote", plan.get("price_quote", "-"))
    h4.metric("CO2 Estimate (kg)", plan.get("co2_kg_estimate", "-"))
    h5.metric("Agents", AGENT_COUNT)
    h6.metric("Tools", TOOL_COUNT)

    tools = result.get("tool_outputs", {})
    tabs = st.tabs(
        [
            "1 Demand",
            "2 Route",
            "3 Warehouse",
            "4 Maintenance",
            "5 Fraud",
            "6 Customer Service",
            "7 Pricing",
            "8 Delivery Failure",
            "9 Carbon",
            "10 Multi-Agent",
        ]
    )

    with tabs[0]:
        st.markdown("**Challenge 1: Demand Forecasting**")
        demand = get_tool_data(tools, "forecast")
        prediction = demand.get("prediction", {})
        c1, c2, c3 = st.columns(3)
        c1.metric("Predicted Volume", prediction.get("volume", "-"))
        c2.metric("Trend", prediction.get("trend", "-"))
        c3.metric("Capacity Risk", prediction.get("capacity_risk", "-"))
        st.caption(f"Recommended buffer: {prediction.get('recommended_buffer_pct', '-')}%")
        explain = demand.get("explainability", {})
        render_explainability_block("Forecast Explainability", explain)
        if show_raw_output:
            st.json(tools.get("forecast", {}))
    with tabs[1]:
        st.markdown("**Challenge 2: Intelligent Route Optimization**")
        route = get_tool_data(tools, "optimize_route")
        metrics = route.get("metrics", {})
        c1, c2, c3 = st.columns(3)
        c1.metric("ETA (min)", metrics.get("estimated_eta_min", "-"))
        c2.metric("Distance (km)", metrics.get("estimated_distance_km", "-"))
        c3.metric("Fuel (L)", metrics.get("estimated_fuel_liters", "-"))
        st.write(f"Route: {' -> '.join(route.get('route', []))}")
        explain = route.get("explainability", {})
        render_explainability_block("Route Explainability", explain)
        if show_raw_output:
            st.json(tools.get("optimize_route", {}))
    with tabs[2]:
        st.markdown("**Challenge 3: Warehouse Picking Optimization**")
        warehouse = get_tool_data(tools, "warehouse")
        st.metric("Estimated Walk Reduction", f"{warehouse.get('estimated_walk_reduction_pct', '-')}%")
        st.write("High-demand zones:", ", ".join(warehouse.get("high_demand_zones", [])) or "-")
        st.write("Optimized sequence:")
        for step in warehouse.get("optimized_sequence", []):
            st.write(f"- {step}")
        explain = warehouse.get("explainability", {})
        render_explainability_block("Warehouse Explainability", explain)
        if show_raw_output:
            st.json(tools.get("warehouse", {}))
    with tabs[3]:
        st.markdown("**Challenge 4: Predictive Maintenance**")
        maintenance = get_tool_data(tools, "maintenance")
        c1, c2 = st.columns(2)
        c1.metric("Risk", maintenance.get("risk", "-"))
        c2.metric("Risk Score", maintenance.get("risk_score", "-"))
        st.write("Action:", maintenance.get("action", "-"))
        explain = maintenance.get("explainability", {})
        render_explainability_block("Maintenance Explainability", explain)
        if show_raw_output:
            st.json(tools.get("maintenance", {}))
    with tabs[4]:
        st.markdown("**Challenge 5: Fraud Detection in Claims**")
        fraud = get_tool_data(tools, "fraud")
        c1, c2 = st.columns(2)
        c1.metric("Fraud Probability", fraud.get("fraud_probability", "-"))
        c2.metric("Decision", fraud.get("decision", "-"))
        explain = fraud.get("explainability", {})
        render_explainability_block("Fraud Explainability", explain)
        if show_raw_output:
            st.json(tools.get("fraud", {}))
    with tabs[5]:
        st.markdown("**Challenge 6: RAG Customer Service**")
        left_col, right_col = st.columns([1, 1.2])
        with left_col:
            st.markdown("**Tool Output Snapshot**")
            chatbot = get_tool_data(tools, "chatbot")
            st.write("Answer:", chatbot.get("answer", "-"))
            st.write("Escalate to human:", "Yes" if chatbot.get("escalate_to_human") else "No")
            retrieval = chatbot.get("retrieval", [])
            if isinstance(retrieval, list) and retrieval:
                with st.expander("Retrieval Evidence"):
                    st.json(retrieval)
            explain = chatbot.get("explainability", {})
            render_explainability_block("Chatbot Explainability", explain)
        with right_col:
            render_customer_service_chat(api_base)
        if show_raw_output:
            st.json(tools.get("chatbot", {}))
    with tabs[6]:
        st.markdown("**Challenge 7: Dynamic Pricing**")
        pricing = get_tool_data(tools, "pricing")
        st.metric("Recommended Price", pricing.get("price", "-"))
        explain = pricing.get("explainability", {})
        components = explain.get("components", {}) if isinstance(explain, dict) else {}
        st.caption(
            f"Base {components.get('base_component', '-')}, "
            f"Urgency x{components.get('urgency_multiplier', '-')}, "
            f"Demand x{components.get('demand_multiplier', '-')}"
        )
        render_explainability_block("Pricing Explainability", explain)
        if show_raw_output:
            st.json(tools.get("pricing", {}))
    with tabs[7]:
        st.markdown("**Challenge 8: Last-Mile Failure Prediction**")
        failure = get_tool_data(tools, "delivery_failure")
        c1, c2 = st.columns(2)
        c1.metric("Failure Probability", failure.get("failure_probability", "-"))
        c2.metric("Action", failure.get("recommended_action", "-"))
        explain = failure.get("explainability", {})
        render_explainability_block("Delivery Failure Explainability", explain)
        if show_raw_output:
            st.json(tools.get("delivery_failure", {}))
    with tabs[8]:
        st.markdown("**Challenge 9: Carbon Emission Optimization**")
        carbon = get_tool_data(tools, "carbon")
        c1, c2 = st.columns(2)
        c1.metric("Estimated Emissions (kg)", carbon.get("estimated_emissions_kg", "-"))
        c2.metric("Saving vs Diesel", f"{carbon.get('estimated_saving_pct_vs_diesel', '-')}%")
        st.write("Recommendation:", carbon.get("recommendation", "-"))
        explain = carbon.get("explainability", {})
        render_explainability_block("Carbon Explainability", explain)
        if show_raw_output:
            st.json(tools.get("carbon", {}))
    with tabs[9]:
        st.markdown("**Challenge 10: Multi-Agent Control Tower**")
        st.markdown("**Final Coordinated Plan**")
        p1, p2, p3 = st.columns(3)
        p1.metric("Dispatch Buffer", f"{plan.get('dispatch_buffer_pct', '-')}%")
        p2.metric("Final Price", plan.get("price_quote", "-"))
        p3.metric("Failure Probability", plan.get("failure_probability", "-"))
        st.markdown("**Agent Notes**")
        for note in result.get("agent_notes", []):
            st.write(f"- {note}")
        if endpoint_mode == "replay":
            st.markdown("**Replay Trace**")
            for step in result.get("execution_meta", {}).get("trace", []):
                st.write(f"Step {step.get('step')}: {step.get('node')} ({step.get('elapsed_ms')} ms)")
        if show_raw_output:
            st.markdown("**Raw Plan + Trace**")
            st.json({"plan": plan, "trace": result.get("execution_meta", {}).get("trace", [])})

with st.form("scenario_form"):
    generated = st.session_state.get("generated_scenario_payload", {})
    tool_retries = 1
    tool_timeout_s = 3.0
    col1, col2, col3 = st.columns(3)
    with col1:
        default_region = str(generated.get("region", "SG"))
        region_idx = REGION_OPTIONS.index(default_region) if default_region in REGION_OPTIONS else REGION_OPTIONS.index("SG")
        region = st.selectbox("Region", options=REGION_OPTIONS, index=region_idx)
        demand_index = st.slider(
            "Demand Index",
            min_value=0.6,
            max_value=1.8,
            value=float(generated.get("demand_index", 1.15)),
            step=0.05,
        )
        default_weather = str(generated.get("weather", "clear"))
        weather = st.selectbox(
            "Weather",
            options=["clear", "rain", "storm"],
            index=["clear", "rain", "storm"].index(default_weather) if default_weather in {"clear", "rain", "storm"} else 0,
            key="form_weather",
        )
    with col2:
        default_urgency = str(generated.get("urgency_mix", "express"))
        urgency_mix = st.selectbox(
            "Urgency Mix",
            options=["standard", "express", "same_day"],
            index=["standard", "express", "same_day"].index(default_urgency)
            if default_urgency in {"standard", "express", "same_day"}
            else 1,
        )
        fleet_health_index = st.slider(
            "Fleet Health Index",
            min_value=0.5,
            max_value=1.0,
            value=float(generated.get("fleet_health_index", 0.9)),
            step=0.01,
        )
        default_traffic = str(generated.get("traffic_level", "medium"))
        traffic_level = st.selectbox(
            "Traffic Level",
            options=["low", "medium", "high"],
            index=["low", "medium", "high"].index(default_traffic) if default_traffic in {"low", "medium", "high"} else 1,
            key="form_traffic_level",
        )
    with col3:
        # Carbon-optimization vehicle class is separate from scenario routing vehicle.
        default_vehicle = str(generated.get("vehicle_type", "diesel_van"))
        if default_vehicle == "ev_van":
            default_vehicle_label = "EV"
        elif default_vehicle == "hybrid_truck":
            default_vehicle_label = "hybrid"
        else:
            default_vehicle_label = "diesel"
        vehicle_type_label = st.selectbox(
            "Vehicle Type (for carbon saving)",
            options=["diesel", "EV", "hybrid"],
            index=["diesel", "EV", "hybrid"].index(default_vehicle_label) if default_vehicle_label in {"diesel", "EV", "hybrid"} else 0,
            help="This vehicle selection affects carbon/emissions calculations and recommendations.",
        )
        vehicle_type = {
            "diesel": "diesel_van",
            "EV": "ev_van",
            "hybrid": "hybrid_truck",
        }[vehicle_type_label]

    with st.expander("Advanced / Reliability Settings"):
        tool_retries = st.slider(
            "Tool Retries",
            min_value=0,
            max_value=3,
            value=1,
            help="How many extra attempts each tool gets after a timeout/error.",
        )
        tool_timeout_s = st.slider(
            "Tool Timeout (s)",
            min_value=1.0,
            max_value=10.0,
            value=3.0,
            step=0.5,
            help="Maximum allowed runtime per tool call before failing fast.",
        )

    submitted = st.form_submit_button("Run Simulation", type="primary")

if submitted:
    payload = {
        "region": region,
        "demand_index": demand_index,
        "weather": weather,
        "urgency_mix": urgency_mix,
        "fleet_health_index": fleet_health_index,
        "traffic_level": traffic_level,
        "vehicle_type": vehicle_type,
        "origin": str(generated.get("origin", "Hub-A")),
        "destination": str(generated.get("destination", "Region-Cluster-1")),
        "route_distance_km": float(generated.get("route_distance_km", 26.0)),
        "tool_retries": tool_retries,
        "tool_timeout_s": tool_timeout_s,
    }
    endpoint_lookup = {
        "sync": "/agents/control",
        "async": "/agents/control/async",
        "replay": "/agents/control/replay",
    }
    endpoint = endpoint_lookup[endpoint_mode]
    url = f"{api_base}{endpoint}"
    try:
        result = fetch_json(url=url, method="POST", payload=payload)
        st.session_state["latest_simulation_result"] = result
        st.session_state["latest_simulation_mode"] = endpoint_mode
        st.success(result.get("status", "ok"))
    except error.HTTPError as http_err:
        detail = http_err.read().decode("utf-8", errors="ignore")
        st.error(f"API error: {http_err.code}")
        st.code(detail)
    except Exception as exc:
        st.error(f"Request failed: {exc}")

latest_result = st.session_state.get("latest_simulation_result")
latest_mode = st.session_state.get("latest_simulation_mode", endpoint_mode)
if isinstance(latest_result, dict):
    if view_mode == "Classic Simulator":
        render_classic_view(latest_result, latest_mode)
    else:
        render_challenges_demo(latest_result, latest_mode, api_base)

if st.session_state.get("show_eval_metrics_panel", False):
    render_eval_metrics_panel(api_base)
    if auto_refresh_eval:
        # Prevent chat view from being interrupted immediately after user sends a message.
        chat_cooldown_s = 45
        since_chat_s = time.time() - float(st.session_state.get("last_customer_chat_ts", 0.0))
        if since_chat_s < chat_cooldown_s:
            st.caption(
                f"Auto-refresh paused while reading chat response "
                f"({int(chat_cooldown_s - since_chat_s)}s remaining)."
            )
        else:
            st.caption(f"Auto-refreshing eval metrics every {auto_refresh_seconds}s.")
            time.sleep(auto_refresh_seconds)
            st.rerun()
