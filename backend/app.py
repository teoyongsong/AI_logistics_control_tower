from fastapi import FastAPI
from backend.routes import (
    forecast, optimize_route, warehouse, maintenance,
    fraud, chatbot, pricing, delivery_failure, carbon, agents, scenario
)


app = FastAPI(title="AI Logistics Control Tower")

# Include routers for each module
app.include_router(forecast.router, prefix="/forecast", tags=["Forecasting"])
app.include_router(optimize_route.router, prefix="/route", tags=["Route Optimization"])
app.include_router(warehouse.router, prefix="/warehouse", tags=["Warehouse Picking"])
app.include_router(maintenance.router, prefix="/maintenance", tags=["Predictive Maintenance"])
app.include_router(fraud.router, prefix="/fraud", tags=["Fraud Detection"])
app.include_router(chatbot.router, prefix="/chatbot", tags=["Customer Service"])
app.include_router(pricing.router, prefix="/pricing", tags=["Dynamic Pricing"])
app.include_router(delivery_failure.router, prefix="/delivery", tags=["Delivery Failure"])
app.include_router(carbon.router, prefix="/carbon", tags=["Carbon Optimization"])
app.include_router(agents.router, prefix="/agents", tags=["Multi-Agent Control Tower"])
app.include_router(scenario.router, prefix="/scenario", tags=["Scenario Simulation"])

@app.get("/")
def root():
    return {"message": "AI Logistics Control Tower API is running"}
