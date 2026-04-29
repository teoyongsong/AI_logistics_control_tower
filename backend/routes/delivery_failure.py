from fastapi import APIRouter
from pydantic import BaseModel

from backend.services.calibrators import calibrate_delivery_failure

router = APIRouter()

class DeliveryFailureRequest(BaseModel):
    delivery_id: str
    customer_present_probability: float
    address_quality_score: float
    weather_severity: float
    prior_failed_attempts: int
    cod_order: bool = False


@router.post("/predict")
def delivery_failure(request: DeliveryFailureRequest):
    failure_probability = calibrate_delivery_failure(
        customer_present_probability=float(request.customer_present_probability),
        address_quality_score=float(request.address_quality_score),
        weather_severity=float(request.weather_severity),
        prior_failed_attempts=int(request.prior_failed_attempts),
        cod_order=bool(request.cod_order),
    )
    intervention = "confirm_delivery_window" if failure_probability >= 0.5 else "normal_dispatch"
    return {
        "delivery_id": request.delivery_id,
        "failure_probability": failure_probability,
        "recommended_action": intervention,
        "explainability": {
            "inputs": {
                "customer_present_probability": float(request.customer_present_probability),
                "address_quality_score": float(request.address_quality_score),
                "weather_severity": float(request.weather_severity),
                "prior_failed_attempts": int(request.prior_failed_attempts),
                "cod_order": bool(request.cod_order),
            },
            "components": {
                "failure_probability": failure_probability,
                "recommended_action": intervention,
            },
            "formula": "calibrated_delivery_failure(inputs)",
            "thresholds": {
                "confirm_delivery_window_threshold": 0.5,
            },
        },
    }
