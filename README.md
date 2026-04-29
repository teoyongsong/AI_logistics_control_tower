# AI Logistics Control Tower

FastAPI + LangGraph prototype for a multi-agent logistics control tower covering:

- Demand forecasting
- Route optimization
- Warehouse picking optimization
- Predictive maintenance
- Fraud detection
- RAG-style customer support
- Dynamic pricing
- Last-mile failure prediction
- Carbon optimization
- Multi-agent orchestration and replay trace

## Domain Context (Ninja Van)

This simulator is aligned to publicly stated Ninja Van context:
- Tech-enabled express delivery company launched in 2014
- Mission: connecting Southeast Asia through delightful delivery experience
- Core SEA coverage across SG, MY, PH, ID, TH, VN

Reference:
- [Ninja Van homepage](https://www.ninjavan.co/)
- [Ninja Van about page](https://www.ninjavan.co/en-mm/company/about-us)

## Project Structure

- `backend/app.py` - FastAPI app entrypoint
- `backend/routes/` - Use-case APIs and control endpoints
- `backend/services/langgraph_orchestrator.py` - LangGraph workflow and tool wiring
- `backend/routes/agents.py` - Multi-agent control tower endpoints (`/agents/*`)
- `backend/streamlit_control_tower.py` - Simulator dashboard UI
- `backend/tests/` - Minimal API test suite
- `AI_TRANSFORMATION_STRATEGY.md` - Strategy/design deliverable

## Quick Start (Recommended: Isolated venv)

```bash
cd /home/teoyongsong/ninjavan
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
```

## Run the API

```bash
source .venv/bin/activate
python -m uvicorn backend.app:app --reload
```

API base URL: `http://127.0.0.1:8000`

Health check:
- `GET /` -> `{"message": "AI Logistics Control Tower API is running"}`

## Run the Streamlit Simulator

```bash
source .venv/bin/activate
streamlit run backend/streamlit_control_tower.py
```

The UI includes a `FastAPI Base URL` field (default: `http://127.0.0.1:8000`) and then calls the selected `/agents/control*` endpoint.

In the sidebar, choose mode:

- `sync` -> `/agents/control`
- `async` -> `/agents/control/async`
- `replay` -> `/agents/control/replay` (includes node timeline trace)

## Run Tests

```bash
source .venv/bin/activate
python -m pytest backend/tests -q
```

Current minimal suite validates:

- `/agents/control`
- `/agents/control/async`
- `/agents/control/replay`

## API Endpoints

### Multi-agent (LangGraph) control

These endpoints orchestrate tools under `backend/services/langgraph_orchestrator.py`.

- `POST /agents/control` - Run sync orchestration
- `POST /agents/control/async` - Run async orchestration
- `POST /agents/control/replay` - Run orchestration with per-node execution trace
- `POST /agents/tool-call` - Call a single registered tool
- `GET /agents/eval-metrics` - Return offline calibration metrics (`forecast_mae`, `failure_brier_like`, `samples`)
- `POST /scenario/simulate` - Build a real-life scenario from Google Maps distance/traffic + weather forecast

If `langgraph` is unavailable, the `/agents/control*` endpoints return an error payload explaining how to install it.

### Individual tool endpoints

You can also call each module directly:

- `POST /forecast/` - Demand forecasting
- `POST /route/` - Route optimization (+ carbon metrics)
- `POST /warehouse/optimize` - Warehouse picking optimization
- `POST /maintenance/predict` - Predictive maintenance
- `POST /fraud/detect` - Fraud detection
- `POST /chatbot/query` - RAG-style customer support (prototype)
- `POST /pricing/dynamic` - Dynamic pricing
- `POST /delivery/predict` - Last-mile failure prediction
- `POST /carbon/optimize` - Carbon optimization

## Example Request Payload

### `/agents/control*` payload (ControlTowerRequest)

```json
{
  "region": "SG",
  "demand_index": 1.2,
  "weather": "rain",
  "urgency_mix": "express",
  "fleet_health_index": 0.9,
  "date": "2026-04-29",
  "origin": "Hub-A",
  "destination": "Region-Cluster-1",
  "traffic_level": "medium",
  "vehicle_type": "diesel_van",
  "tool_retries": 1,
  "tool_timeout_s": 3.0
}
```

Required fields: `region`, `demand_index`, `weather`, `urgency_mix`, `fleet_health_index`.
Other fields have sensible defaults.

### `/agents/tool-call` payload (ToolCallRequest)

```json
{
  "tool_name": "chatbot",
  "scenario": {
    "support_query": "Where is my parcel?",
    "tracking_id": "TRK-445901",
    "chat_confidence_threshold": 0.65
  }
}
```

## Notes

- Dependencies are pinned for LangGraph/LangChain compatibility in `backend/requirements.txt`.
- This prototype does not require external LLM/API credentials (the tool logic is deterministic/mocked).
- If you have conflicting LangChain packages in your global Python env, use the project `.venv` to avoid resolver conflicts.
- To use `/scenario/simulate`, set `GOOGLE_MAPS_API_KEY` in your environment.
