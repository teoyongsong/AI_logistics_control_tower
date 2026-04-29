from fastapi import APIRouter
from pydantic import BaseModel

from backend.services.offline_rag import rag_chatbot_query

router = APIRouter()

class ChatbotRequest(BaseModel):
    query: str
    tracking_id: str | None = None
    confidence_threshold: float = 0.65


@router.post("/query")
def chatbot_query(request: ChatbotRequest):
    q = request.query.lower()
    rag = rag_chatbot_query(request.query, top_k=2)
    retrieved_docs = rag["retrieval"]
    top_confidence = float(rag["top_confidence"])

    # Keep the existing escalation behavior but base it on retrieval confidence.
    escalated = top_confidence < request.confidence_threshold or ("complaint" in q)
    return {
        "query": request.query,
        "answer": str(rag["answer"]),
        "retrieval": retrieved_docs,
        "escalate_to_human": escalated,
        "explainability": {
            "inputs": {
                "query": request.query,
                "tracking_id_present": request.tracking_id is not None,
            },
            "components": {
                "top_retrieval_confidence": round(top_confidence, 3),
                "complaint_keyword_detected": "complaint" in q,
            },
            "formula": "escalate = top_confidence < threshold OR complaint_keyword_detected",
            "thresholds": {
                "confidence_threshold": float(request.confidence_threshold),
            },
        },
    }
