from fastapi import APIRouter
from pydantic import BaseModel
from typing import List

from backend.services.calibrators import calibrate_forecast

router = APIRouter()

class ForecastRequest(BaseModel):
    region: str
    date: str
    historical_daily_volume: List[int]
    promo_campaign: bool = False
    holiday_period: bool = False

@router.post("/")
def forecast_shipments(request: ForecastRequest):
    baseline = sum(request.historical_daily_volume[-7:]) / max(1, min(len(request.historical_daily_volume), 7))
    prediction = calibrate_forecast(
        baseline=baseline,
        promo_campaign=bool(request.promo_campaign),
        holiday_period=bool(request.holiday_period),
    )
    return {
        "region": request.region,
        "date": request.date,
        "prediction": prediction,
        "explainability": {
            "inputs": {
                "baseline_volume_last_7d": round(baseline, 2),
                "promo_campaign": bool(request.promo_campaign),
                "holiday_period": bool(request.holiday_period),
            },
            "components": {
                "model_type": "calibrated_linear_with_thresholds",
                "predicted_volume": prediction.get("volume"),
            },
            "formula": "calibrated_forecast(baseline, promo_campaign, holiday_period)",
            "thresholds": {
                "trend_labels": ["upward", "stable", "downward"],
                "capacity_risk_labels": ["low", "medium", "high"],
            },
        },
    }
