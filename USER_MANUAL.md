# AI Logistics Simulator User Manual

This manual lists every control and every output metric, with **allowed values / ranges**, **units**, and **how to read** them in the prototype.

## 1) Before You Run

1. Start the FastAPI backend: `uvicorn backend.app:app --reload`
2. Start the simulator UI: `streamlit run backend/streamlit_control_tower.py`
3. Open the Streamlit URL from the terminal (commonly `http://localhost:8501`).

After you change backend logic, **restart the API** (or rely on `--reload`); the UI only needs a refresh if the page is stale.

---

## 2) Sidebar Controls

| Control | Range / values | Default | Interpretation |
|--------|------------------|---------|----------------|
| **FastAPI Base URL** | Any valid HTTP base URL for your API | `http://127.0.0.1:8000` | Where the UI sends `POST` requests. Must match the running `uvicorn` host and port. |
| **Mode** | `sync` · `async` · `replay` | `sync` | **sync:** standard orchestration. **async:** same flow via async runtime. **replay:** same result plus a **per-node execution trace** (timeline). |
| **View** | `Classic Simulator` · `10 Challenges Demo` | `10 Challenges Demo` | **Classic:** summary KPIs + notes + replay trace. **10 Challenges:** one tab per use case (demand, route, …) with detail. |
| **Show existing raw JSON output** | On / Off | Off | **On:** shows raw `execution_meta` and `tool_outputs` for debugging. **Off:** business-friendly view only. |
| **Fetch Eval Metrics** | Button | — | Fetches `GET /agents/eval-metrics` and displays offline calibration metrics. |
| **Auto-refresh Eval Metrics** | On / Off | Off | Periodically refreshes eval metrics with a short cooldown after chat activity. |

---

## 3) Real-life Scenario Builder (before form)

Use this first to auto-generate realistic conditions from route context:

- **Collection Point (Start)**
- **Delivery Point (Destination)**
- **Scenario Vehicle Type** (`van` or `motorcycle`)
- **Create Scenario (Google Maps + Weather Forecast)**

What it does:
- Computes distance/time/traffic and weather
- Estimates `demand_index` + `fleet_health_index`
- Auto-fills key simulation fields in the form

If Google key is missing, it uses fallback mode and shows a notice.

---

## 4) Scenario Form (Inputs)

All of these are sent in the JSON body when you click **Run Simulation**. Sliders use **inclusive** min/max as shown in the UI.

| Field | Type | Range / allowed values | Default | Step | Interpretation & effect in the prototype |
|-------|------|------------------------|---------|------|----------------------------------------|
| **Region** | Select | `SG` · `MY` · `PH` · `ID` · `TH` · `VN` | `SG` | — | Forecast context label and scenario market. |
| **Demand Index** | Slider | `0.60` – `1.80` (unitless index) | `1.15` | `0.05` | **1.0 = baseline demand.** Below 1.0 reduces pricing pressure; above 1.0 increases it (see **Demand multiplier** under outputs). Also nudges **last-mile failure** slightly when > 1.0. |
| **Weather** | Select | `clear` · `rain` · `storm` | `clear` | — | Affects **route ETA** (rain/storm = longer ETA) and **last-mile failure** (mapped to internal severity for the failure model). |
| **Urgency Mix** | Select | `standard` · `express` · `same_day` | `express` | — | Affects **dynamic price** (higher urgency → higher multiplier) and **carbon recommendation** text; nudges **last-mile failure** (tighter service = slightly higher risk in the prototype). |
| **Fleet Health Index** | Slider | `0.50` – `1.00` (0 = poor, 1 = excellent) | `0.90` | `0.01` | Drives **simulated prior failed delivery attempts** (lower health → more “prior attempts” in the failure model) and signals **maintenance** context in the story; maintenance tool still uses its own fixed demo inputs unless you extend the API. |
| **Traffic Level** | Select | `low` · `medium` · `high` | `medium` | — | Affects **route ETA and fuel** (higher traffic → longer ETA, more fuel) and nudges **customer presence** in the **last-mile failure** model. |
| **Vehicle Type (for carbon saving)** | Select | `diesel` · `EV` · `hybrid` | `diesel` | — | Used for carbon/emissions optimization and recommendation. |
| **Tool Retries** *(Advanced)* | Integer slider | `0` – `3` | `1` | `1` | Reliability setting under **Advanced / Reliability Settings**. |
| **Tool Timeout (s)** *(Advanced)* | Slider | `1.0` – `10.0` seconds | `3.0` | `0.5` | Reliability setting under **Advanced / Reliability Settings**. |

---

## 5) How to Run a Scenario

1. Set **Mode**, **View**, and optional **raw JSON** in the sidebar.
2. Adjust the scenario form.
3. Click **Run Simulation**.
4. Read the **status** line, then the **metrics** for your selected view (see sections 5–6).

---

## 6) Top dashboard metrics (Plan + classic header)

These come from the orchestration **plan** and **execution_meta** and appear in **Classic** view and/or the **10 Challenges** header row.

| Metric | Typical range in prototype | Unit | Where it comes from | How to read it |
|--------|----------------------------|------|---------------------|----------------|
| **Target ETA (min)** | About **tens of minutes** (depends on scenario distance × traffic × weather) | Minutes | **Route** tool: distance + traffic penalty × weather penalty → `estimated_eta_min` | **Lower is faster.** Rises with **high traffic** and **rain/storm**. |
| **Price Quote** | **≥ 3.50** in the pricing heuristic (then scaled by urgency and demand) | Currency units (unnamed in demo) | **Pricing** tool: base distance + weight + **urgency multiplier** × **demand multiplier** + fuel surcharge | **Higher** urgency / distance / demand → **higher** quote. **Demand multiplier** = `1 + (demand_index - 1) × 0.2` (so at index **1.0** it is **1.0**). |
| **Failure Probability** | **0.000** – **0.990** (capped) | Probability (0–1) | **Last-mile / delivery failure** tool: weighted mix of **customer presence**, **address quality**, **weather severity**, **prior attempts**, **COD** | **Higher = more last-mile risk** in the toy model. Varies with **weather**, **traffic**, **fleet health**, **demand**, **urgency** (see section 3). |
| **Forecast Volume** | **Non-negative integer** (shipment count style) | Count / day (conceptual) | **Forecast** tool: rolling history + promo/holiday flags (defaults are fixed in orchestration) | **Higher** volume vs baseline tends to **higher** capacity risk. |
| **CO₂ Estimate (kg)** (10 Challenges header) | **≥ 0** | kg CO₂ (approximate) | Derived from carbon + route context with selected vehicle class (`diesel`/`EV`/`hybrid`) | **Lower is better** for the same trip; vehicle class has large impact. |
| **KPI Deltas** | Signed values | mixed | `plan.kpi_deltas` | Shows delta vs baseline for ETA, cost, risk, CO₂. |
| **Dispatch Buffer (%)** | **3**, **8**, or **15** in the current forecast rules | Percent | **Forecast** `recommended_buffer_pct` from **capacity_risk** | **Higher** buffer when **capacity_risk** is **high** (suggested extra operational slack). |
| **Risk Review Triggered** | **Yes** / **No** | Boolean | `execution_meta.risk_review_triggered` (tied to whether `"risk_review"` appears in **agent notes** in the current code) | **Yes** = risk path was noted in the trace; use **replay** + **raw JSON** to inspect. |
| **Trace Steps** (replay mode) | **Integer ≥ 1** | Count | **Replay** stream: one step per graph event | **Larger** = more node updates recorded in the trace. |
| **Agent Notes** | List of short strings | — | Appended by each agent node in the graph | **Narrative** of what the orchestration “did” in order. |
| **Replay Timeline** (replay mode) | Steps with **node name**, **elapsed ms**, **keys updated** | Time (ms) | **Replay** trace | **Explainability:** which node ran and which state keys changed. |

---

## 7) “10 Challenges Demo” tab metrics

Each tab shows tool output. Ranges below match the **prototype** math in the backend, not live production data.

### Tab 1 – Demand (forecast)

| Metric | Range / values | Unit | Interpretation |
|--------|------------------|------|----------------|
| **Predicted Volume** | Non-negative integer | Count | Model “next day” style volume from **historical** series + **promo/holiday** multipliers (defaults fixed unless scenario extended). |
| **Trend** | `upward` · `stable` · `downward` | — | Class vs recent baseline (**±15% / −10%** style thresholds in code). |
| **Capacity Risk** | `low` · `medium` · `high` | — | **high** if volume > baseline × **1.2**; **medium** if above baseline; else **low**. |
| **Recommended buffer %** | **3 / 8 / 15** | % | Tied to **capacity_risk** (**high → 15**, **medium → 8**, **low → 3**). |

### Tab 2 – Route (optimize_route)

| Metric | Range / values | Unit | Interpretation |
|--------|------------------|------|----------------|
| **ETA (min)** | Positive integer (prototype heuristic) | Minutes | Same as **Target ETA** drivers: traffic × weather × fixed distance/waypoints. |
| **Distance (km)** | Positive decimal | km | Uses scenario-generated route distance when available; otherwise heuristic distance. |
| **Fuel (L)** | Positive decimal | Liters | Heuristic from distance / efficiency × traffic; **not** a calibrated fleet figure. |
| **Route** | Ordered list of strings | — | **Origin → waypoints → destination** path labels. |

### Tab 3 – Warehouse

| Metric | Range / values | Unit | Interpretation |
|--------|------------------|------|----------------|
| **Estimated Walk Reduction** | **≤ 35** (cap), grows with task count in prototype | % | Illustrative **pick-path** savings vs naive ordering. |
| **High-demand zones** | List of aisle labels | — | Zones where **demand_score ≥ 0.8** on demo tasks. |
| **Optimized sequence** | Ordered steps | — | Pick tour order for the demo SKU list. |

### Tab 4 – Maintenance

| Metric | Range / values | Unit | Interpretation |
|--------|------------------|------|----------------|
| **Risk** | `Low` · `Medium` · `High` | — | From **risk_score** thresholds: **≥ 0.7** High, **≥ 0.45** Medium, else Low (demo inputs fixed in orchestrator). |
| **Risk Score** | **0 – ~1+** before clamping-style bands | Score | Weighted blend of **temperature**, **vibration**, **mileage**, **DTC count** (prototype weights). |
| **Action** | Text | — | Recommended next step for that score band. |

### Tab 5 – Fraud

| Metric | Range / values | Unit | Interpretation |
|--------|------------------|------|----------------|
| **Fraud Probability** | **0.000 – 0.990** | Probability | Blended score from **claim size**, **claim frequency**, **missing docs**, **account age** (fixed demo claim in orchestration). |
| **Decision** | `auto_process` · `manual_review` | — | **manual_review** if fraud probability **≥ 0.6**. |

### Tab 6 – Customer Service (chatbot)

| Metric | Range / values | Unit | Interpretation |
|--------|------------------|------|----------------|
| **Answer** | Text | — | Retrieval-grounded response from local offline RAG index. |
| **Escalate to human** | **Yes** / **No** | — | Triggered by confidence threshold or complaint signal. |
| **Customer Service Chat** | Interactive | — | Chat-style demo window allows repeated user questions and assistant replies. |

### Tab 7 – Pricing

| Metric | Range / values | Unit | Interpretation |
|--------|------------------|------|----------------|
| **Recommended Price** | **≥ 3.5** after rounding | Currency (demo) | Final **dynamic price**. |
| **Explainability** | Layman + technical details | — | Presented as **Inputs / Components / Formula / Thresholds**. |

### Tab 8 – Last-Mile Failure

| Metric | Range / values | Unit | Interpretation |
|--------|------------------|------|----------------|
| **Failure Probability** | **0.000 – 0.990** | Probability | Same model as dashboard **Failure Probability** (see section 5). |
| **Action** | `normal_dispatch` · `confirm_delivery_window` | — | **confirm_delivery_window** if failure probability **≥ 0.5**. |

### Tab 9 – Carbon

| Metric | Range / values | Unit | Interpretation |
|--------|------------------|------|----------------|
| **Estimated Emissions (kg)** | **≥ 0** | kg | Distance × per-**vehicle_type** factor (EV uses **grid_carbon_intensity** scaling). |
| **Saving vs Diesel** | **0 – 100** (percentage points) | % | Improvement vs a **diesel baseline** for the same distance. |
| **Recommendation** | `switch_to_ev` · `optimize_consolidation` | — | **switch_to_ev** when urgency is **standard** and distance **≤ 120 km** in the prototype; otherwise consolidation hint. |

### Tab 10 – Multi-Agent (summary)

Repeats **Dispatch Buffer**, **Final Price**, **Failure Probability**, **Agent Notes**, and optionally **Replay Trace** — same interpretation as in sections 5–6.

---

## 8) Recommended Usage Patterns

- **A/B testing:** Fix all inputs except one (e.g. only **Weather**) and compare **ETA**, **Price**, **Failure Probability**, **CO₂**.
- **Reliability:** Sweep **Tool Retries** (0 → 3) and observe errors/timeouts in **raw JSON**.
- **Latency stress:** Lower **Tool Timeout** toward **1.0 s** and combine with high **Traffic** / **storm**.
- **Explainability:** **Mode = replay** + **Show raw JSON** to align numbers with **trace** steps.

---

## 9) Troubleshooting

| Issue | What to check |
|-------|----------------|
| Connection errors | **FastAPI Base URL** matches `uvicorn`; firewall/host binding. |
| HTTP errors | Enable **raw JSON**; read response body from API. |
| Empty replay trace | **Mode** must be **replay**; backend must expose `/agents/control/replay`. |
| Metrics unchanged after code edits | Restart **backend** (or confirm `--reload` picked up files). |
| Scenario uses fallback estimates | `GOOGLE_MAPS_API_KEY` may be missing; app falls back to heuristic mode by design. |

---

For onboarding, **change one input at a time** and compare the **plan** metrics (section 5) before diving into every challenge tab.
