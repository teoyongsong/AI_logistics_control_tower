from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class PricingRequest(BaseModel):
    distance_km: float
    urgency: str  # standard | express | same_day
    demand_index: float  # 0-2
    fuel_price_per_liter: float
    package_weight_kg: float = 1.0


@router.post("/dynamic")
def dynamic_pricing(request: PricingRequest):
    base = 4.0 + (request.distance_km * 0.4) + (request.package_weight_kg * 0.25)
    urgency_multiplier = {"standard": 1.0, "express": 1.25, "same_day": 1.55}.get(request.urgency.lower(), 1.0)
    demand_multiplier = 1 + ((request.demand_index - 1.0) * 0.2)
    fuel_surcharge = max(0.0, (request.fuel_price_per_liter - 2.0) * 0.5)
    dynamic_price = round(max(3.5, base * urgency_multiplier * demand_multiplier + fuel_surcharge), 2)

    return {
        "inputs": request.model_dump(),
        "price": dynamic_price,
        "explainability": {
            "inputs": request.model_dump(),
            "components": {
                "base_component": round(base, 2),
                "urgency_multiplier": urgency_multiplier,
                "demand_multiplier": round(demand_multiplier, 3),
                "fuel_surcharge": round(fuel_surcharge, 2),
            },
            "formula": "max(3.5, base * urgency_multiplier * demand_multiplier + fuel_surcharge)",
            "thresholds": {
                "price_floor": 3.5,
            },
        },
    }
