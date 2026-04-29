from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict

router = APIRouter()

class RouteRequest(BaseModel):
    origin: str
    destination: str
    traffic_level: str = "medium"  # low | medium | high
    weather: str = "clear"  # clear | rain | storm
    vehicle_type: str = "van"
    route_distance_km: float | None = None
    waypoints: List[str] = []
    constraints: Dict[str, str] = {}

@router.post("/")
def optimize_route(request: RouteRequest):
    traffic_penalty = {"low": 0.95, "medium": 1.0, "high": 1.2}.get(request.traffic_level.lower(), 1.0)
    weather_penalty = {"clear": 1.0, "rain": 1.1, "storm": 1.25}.get(request.weather.lower(), 1.0)
    distance_source = "scenario_distance" if request.route_distance_km is not None else "heuristic_distance"
    if request.route_distance_km is not None:
        # Use externally-computed scenario distance when available (e.g. map-based route simulation).
        base_distance_km = max(0.1, float(request.route_distance_km))
    else:
        base_distance_km = 20 + (4 * len(request.waypoints))
    eta_minutes = int(round((base_distance_km / 35) * 60 * traffic_penalty * weather_penalty))
    fuel_liters = round((base_distance_km / 12) * traffic_penalty * 1.1, 2)

    optimized_path = [request.origin] + request.waypoints + [request.destination]
    return {
        "origin": request.origin,
        "destination": request.destination,
        "route": optimized_path,
        "metrics": {
            "estimated_eta_min": eta_minutes,
            "estimated_distance_km": base_distance_km,
            "estimated_fuel_liters": fuel_liters,
            "co2_kg_estimate": round(fuel_liters * 2.68, 2),
        },
        "explainability": {
            "inputs": {
                "distance_km": base_distance_km,
                "traffic_level": request.traffic_level,
                "weather": request.weather,
                "vehicle_type": request.vehicle_type,
            },
            "components": {
                "distance_source": distance_source,
                "traffic_penalty": traffic_penalty,
                "weather_penalty": weather_penalty,
                "estimated_fuel_liters": fuel_liters,
            },
            "formula": "(distance/35)*60*traffic_penalty*weather_penalty",
            "thresholds": {
                "traffic_penalties": {"low": 0.95, "medium": 1.0, "high": 1.2},
                "weather_penalties": {"clear": 1.0, "rain": 1.1, "storm": 1.25},
            },
        },
        "notes": "Prototype heuristic. Replace with OR-Tools VRP solver + live traffic/weather features in production.",
    }
