from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class CarbonRequest(BaseModel):
    route_distance_km: float
    vehicle_type: str  # diesel | EV | hybrid | van | motorcycle | diesel_van | ev_van | hybrid_truck
    grid_carbon_intensity: float = 0.45
    delivery_urgency: str = "standard"


@router.post("/optimize")
def carbon_optimization(request: CarbonRequest):
    aliases = {
        "diesel": "diesel_van",
        "ev": "ev_van",
        "hybrid": "hybrid_truck",
    }
    factors = {
        "van": 0.21,
        "diesel_van": 0.21,
        "motorcycle": 0.11,
        "ev_van": 0.08,
        "hybrid_truck": 0.14,
    }
    normalized_vehicle = aliases.get(request.vehicle_type.lower(), request.vehicle_type.lower())
    factor = factors.get(normalized_vehicle, 0.2)
    baseline = request.route_distance_km * 0.21
    emissions = request.route_distance_km * (
        factor if normalized_vehicle != "ev_van" else factor * request.grid_carbon_intensity / 0.45
    )
    saving_pct = round(max(0.0, (baseline - emissions) / baseline) * 100, 1) if baseline else 0.0

    recommendation = "switch_to_ev" if request.delivery_urgency == "standard" and request.route_distance_km <= 120 else "optimize_consolidation"
    return {
        "estimated_emissions_kg": round(emissions, 3),
        "estimated_saving_pct_vs_diesel": saving_pct,
        "recommendation": recommendation,
        "explainability": {
            "inputs": {
                "vehicle_type": request.vehicle_type,
                "normalized_vehicle_type": normalized_vehicle,
                "distance_km": float(request.route_distance_km),
                "delivery_urgency": request.delivery_urgency,
            },
            "components": {
                "emission_factor": factor,
                "baseline_factor_diesel_van": 0.21,
                "estimated_emissions_kg": round(emissions, 3),
                "estimated_saving_pct_vs_diesel": saving_pct,
            },
            "formula": "emissions = distance_km * factor (EV adjusted by grid intensity)",
            "thresholds": {
                "switch_to_ev_max_distance_km": 120,
            },
        },
    }
