"""
Central configuration for thresholds, regions, and business baselines.
"""

from __future__ import annotations

from dataclasses import dataclass


# Public company information extracted from Ninja Van website pages.
NINJA_VAN_CONTEXT = {
    "launched_year": 2014,
    "mission": "Connecting Southeast Asia to a world of possibilities, one delightful delivery at a time",
    "coverage_countries": ["SG", "MY", "PH", "ID", "TH", "VN"],
}


@dataclass(frozen=True)
class RiskThresholds:
    fraud_probability_review: float = 0.60
    failure_probability_review: float = 0.50


@dataclass(frozen=True)
class BaselineKpis:
    # Baselines are intentionally simple and explicit for demo KPI deltas.
    target_eta_min: float = 60.0
    price_quote: float = 18.0
    failure_probability: float = 0.30
    co2_kg_estimate: float = 8.0


RISK_THRESHOLDS = RiskThresholds()
BASELINE_KPIS = BaselineKpis()

