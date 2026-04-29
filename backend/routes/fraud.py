from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class FraudRequest(BaseModel):
    claim_id: str
    customer_id: str
    claim_amount: float
    claims_last_90_days: int
    missing_proof_docs: int
    account_age_days: int


@router.post("/detect")
def detect_fraud(request: FraudRequest):
    claim_amount_component = min(request.claim_amount / 300, 1.0) * 0.25
    claims_frequency_component = min(request.claims_last_90_days / 5, 1.0) * 0.3
    missing_docs_component = min(request.missing_proof_docs / 3, 1.0) * 0.25
    account_age_component = 0.2 if request.account_age_days < 90 else 0.0

    score = (
        claim_amount_component
        + claims_frequency_component
        + missing_docs_component
        + account_age_component
    )

    decision = "manual_review" if score >= 0.6 else "auto_process"
    return {
        "claim_id": request.claim_id,
        "customer_id": request.customer_id,
        "fraud_probability": round(min(score, 0.99), 3),
        "decision": decision,
        "explainability": {
            "inputs": {
                "claim_amount": request.claim_amount,
                "claims_last_90_days": request.claims_last_90_days,
                "missing_proof_docs": request.missing_proof_docs,
                "account_age_days": request.account_age_days,
            },
            "components": {
                "claim_amount_component": round(claim_amount_component, 3),
                "claims_frequency_component": round(claims_frequency_component, 3),
                "missing_docs_component": round(missing_docs_component, 3),
                "account_age_component": round(account_age_component, 3),
            },
            "formula": "claim_amount_norm*0.25 + claims_freq_norm*0.3 + missing_docs_norm*0.25 + young_account_bonus",
            "thresholds": {
                "manual_review_threshold": 0.6,
                "young_account_days": 90,
            },
        },
    }
