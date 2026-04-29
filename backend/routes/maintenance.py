from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class MaintenanceRequest(BaseModel):
    vehicle_id: str
    engine_temp_c: float
    vibration_score: float
    mileage_km: int
    dtc_count: int  # Diagnostic trouble codes


@router.post("/predict")
def predictive_maintenance(request: MaintenanceRequest):
    temp_component = (request.engine_temp_c / 120) * 0.3
    vibration_component = min(request.vibration_score / 10, 1.0) * 0.25
    mileage_component = min(request.mileage_km / 300000, 1.0) * 0.25
    dtc_component = min(request.dtc_count / 10, 1.0) * 0.2
    risk_score = temp_component + vibration_component + mileage_component + dtc_component
    if risk_score >= 0.7:
        risk = "High"
        action = "Schedule maintenance within 24 hours"
    elif risk_score >= 0.45:
        risk = "Medium"
        action = "Inspect vehicle in next service window"
    else:
        risk = "Low"
        action = "Continue monitoring"

    return {
        "vehicle_id": request.vehicle_id,
        "risk": risk,
        "risk_score": round(risk_score, 3),
        "action": action,
        "explainability": {
            "inputs": {
                "engine_temp_c": request.engine_temp_c,
                "vibration_score": request.vibration_score,
                "mileage_km": request.mileage_km,
                "dtc_count": request.dtc_count,
            },
            "components": {
                "temp_component": round(temp_component, 3),
                "vibration_component": round(vibration_component, 3),
                "mileage_component": round(mileage_component, 3),
                "dtc_component": round(dtc_component, 3),
            },
            "formula": "temp_norm*0.3 + vibration_norm*0.25 + mileage_norm*0.25 + dtc_norm*0.2",
            "thresholds": {
                "high_risk": 0.7,
                "medium_risk": 0.45,
            },
        },
    }
