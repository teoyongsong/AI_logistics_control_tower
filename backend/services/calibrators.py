from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np


def _clamp01(x: float) -> float:
    return float(min(1.0, max(0.0, x)))


def _heuristic_forecast_from_baseline(baseline: float, promo_campaign: bool, holiday_period: bool) -> Dict[str, object]:
    multiplier = 1.0 + (0.12 if promo_campaign else 0.0) + (0.18 if holiday_period else 0.0)
    predicted_volume = int(round(baseline * multiplier))

    if predicted_volume >= baseline * 1.15:
        trend = "upward"
    elif predicted_volume <= baseline * 0.9:
        trend = "downward"
    else:
        trend = "stable"

    capacity_risk = "high" if predicted_volume > baseline * 1.2 else "medium" if predicted_volume > baseline else "low"
    recommended_buffer_pct = 15 if capacity_risk == "high" else 8 if capacity_risk == "medium" else 3

    return {
        "volume": predicted_volume,
        "trend": trend,
        "capacity_risk": capacity_risk,
        "recommended_buffer_pct": recommended_buffer_pct,
    }


def _heuristic_delivery_failure(
    customer_present_probability: float,
    address_quality_score: float,
    weather_severity: float,
    prior_failed_attempts: int,
    cod_order: bool,
) -> float:
    cpp = _clamp01(customer_present_probability)
    aqs = _clamp01(address_quality_score)
    ws = _clamp01(weather_severity)
    pfa_term = min(float(prior_failed_attempts) / 3.0, 1.0)
    cod_term = 0.05 if cod_order else 0.0

    failure_probability = (1 - cpp) * 0.35 + (1 - aqs) * 0.25 + ws * 0.2 + pfa_term * 0.15 + cod_term
    failure_probability = round(min(max(failure_probability, 0.0), 0.99), 3)
    return float(failure_probability)


@dataclass(frozen=True)
class ForecastCalibratorParams:
    # yhat = b0 + b1*baseline + b2*(baseline*promo) + b3*(baseline*holiday)
    coeffs: np.ndarray  # shape (4,) for [1, baseline, baseline*promo, baseline*holiday]
    trend_t_up: float
    trend_t_down: float
    risk_t_high: float
    risk_t_medium: float


class ForecastCalibrator:
    """
    Calibration approach:
    - Learn a linear regressor yhat(baseline, promo, holiday) to approximate predicted volume.
    - Learn decision thresholds (ratio = yhat/baseline) for trend + capacity risk.

    This turns the prototype’s fixed rules into learned parameters from a calibration dataset.
    """

    def __init__(self) -> None:
        self._params: ForecastCalibratorParams | None = None
        self._fit()

    def _fit(self) -> None:
        rng = np.random.default_rng(42)
        n = 6000
        baseline = rng.uniform(200.0, 2200.0, size=n)
        promo = rng.integers(0, 2, size=n).astype(bool)
        holiday = rng.integers(0, 2, size=n).astype(bool)

        y = np.zeros(n, dtype=float)
        for i in range(n):
            y[i] = _heuristic_forecast_from_baseline(float(baseline[i]), bool(promo[i]), bool(holiday[i]))["volume"]

        # Linear regression on features [1, baseline, baseline*promo, baseline*holiday]
        X = np.column_stack(
            [
                np.ones(n, dtype=float),
                baseline,
                baseline * promo.astype(float),
                baseline * holiday.astype(float),
            ]
        )
        coeffs, *_ = np.linalg.lstsq(X, y, rcond=None)

        # Decision thresholds learned to match heuristic labels
        def predict_ratio(i: int) -> float:
            # Use regressor output (not the heuristic y) when deriving thresholds.
            x = X[i]
            yhat = float(np.dot(x, coeffs))
            return yhat / float(baseline[i])

        ratios = np.array([predict_ratio(i) for i in range(n)], dtype=float)
        y_heur = np.array(
            [
                _heuristic_forecast_from_baseline(float(baseline[i]), bool(promo[i]), bool(holiday[i]))["volume"]
                for i in range(n)
            ],
            dtype=float,
        )
        trend_labels = np.array(
            ["stable"] * n,
            dtype=object,
        )
        for i in range(n):
            if y_heur[i] >= baseline[i] * 1.15:
                trend_labels[i] = "upward"
            elif y_heur[i] <= baseline[i] * 0.9:
                trend_labels[i] = "downward"

        risk_labels = np.array(["low"] * n, dtype=object)
        for i in range(n):
            if y_heur[i] > baseline[i] * 1.2:
                risk_labels[i] = "high"
            elif y_heur[i] > baseline[i]:
                risk_labels[i] = "medium"

        # Trend threshold search
        t_up_candidates = np.linspace(1.05, 1.25, 21)
        t_down_candidates = np.linspace(0.75, 0.95, 21)
        best_trend = (-1.0, 1.15, 0.90)
        for t_up in t_up_candidates:
            for t_down in t_down_candidates:
                if not (t_down < 1.0 < t_up):
                    continue
                pred = np.array(["stable"] * n, dtype=object)
                pred[ratios >= t_up] = "upward"
                pred[ratios <= t_down] = "downward"
                acc = float(np.mean(pred == trend_labels))
                if acc > best_trend[0]:
                    best_trend = (acc, float(t_up), float(t_down))

        # Capacity risk threshold search
        t_high_candidates = np.linspace(1.05, 1.35, 31)
        t_med_candidates = np.linspace(0.90, 1.10, 21)
        best_risk = (-1.0, 1.20, 1.00)
        for t_high in t_high_candidates:
            for t_med in t_med_candidates:
                if not (t_med < t_high):
                    continue
                pred = np.array(["low"] * n, dtype=object)
                pred[ratios > t_high] = "high"
                mid_mask = (ratios > t_med) & (ratios <= t_high)
                pred[mid_mask] = "medium"
                acc = float(np.mean(pred == risk_labels))
                if acc > best_risk[0]:
                    best_risk = (acc, float(t_high), float(t_med))

        self._params = ForecastCalibratorParams(
            coeffs=coeffs.astype(float),
            trend_t_up=best_trend[1],
            trend_t_down=best_trend[2],
            risk_t_high=best_risk[1],
            risk_t_medium=best_risk[2],
        )

    def predict(self, baseline: float, promo_campaign: bool, holiday_period: bool) -> Dict[str, object]:
        assert self._params is not None
        coeffs = self._params.coeffs
        x = np.array([1.0, baseline, baseline * float(promo_campaign), baseline * float(holiday_period)], dtype=float)
        predicted_volume = int(round(float(np.dot(x, coeffs))))

        ratio = predicted_volume / max(baseline, 1e-9)
        if ratio >= self._params.trend_t_up:
            trend = "upward"
        elif ratio <= self._params.trend_t_down:
            trend = "downward"
        else:
            trend = "stable"

        if ratio > self._params.risk_t_high:
            capacity_risk = "high"
            recommended_buffer_pct = 15
        elif ratio > self._params.risk_t_medium:
            capacity_risk = "medium"
            recommended_buffer_pct = 8
        else:
            capacity_risk = "low"
            recommended_buffer_pct = 3

        return {
            "volume": predicted_volume,
            "trend": trend,
            "capacity_risk": capacity_risk,
            "recommended_buffer_pct": recommended_buffer_pct,
        }


@dataclass(frozen=True)
class FailureCalibratorParams:
    # failure = b + sum(wi * feature_i)
    weights: np.ndarray  # shape (6,) for [f1,f2,f3,f4,f5,1]


class DeliveryFailureCalibrator:
    """
    Learns a linear calibration from the prototype’s failure formula.

    Features:
      f1=(1-customer_present_probability), f2=(1-address_quality_score),
      f3=weather_severity, f4=min(prior_failed_attempts/3, 1), f5=cod_order
    """

    def __init__(self) -> None:
        self._params: FailureCalibratorParams | None = None
        self._fit()

    def _fit(self) -> None:
        rng = np.random.default_rng(123)
        n = 8000

        cpp = rng.uniform(0.0, 1.0, size=n)
        aqs = rng.uniform(0.0, 1.0, size=n)
        ws = rng.uniform(0.0, 1.0, size=n)
        pfa = rng.integers(0, 4, size=n)  # 0..3
        cod = rng.integers(0, 2, size=n).astype(float)

        f1 = (1.0 - cpp)
        f2 = (1.0 - aqs)
        f3 = ws
        f4 = np.minimum(pfa.astype(float) / 3.0, 1.0)
        f5 = cod

        y = np.zeros(n, dtype=float)
        for i in range(n):
            y[i] = _heuristic_delivery_failure(
                customer_present_probability=float(cpp[i]),
                address_quality_score=float(aqs[i]),
                weather_severity=float(ws[i]),
                prior_failed_attempts=int(pfa[i]),
                cod_order=bool(cod[i] > 0.5),
            )

        # Linear regression with intercept
        # weights correspond to [f1,f2,f3,f4,f5,1]
        X = np.column_stack([f1, f2, f3, f4, f5, np.ones(n, dtype=float)])
        weights, *_ = np.linalg.lstsq(X, y, rcond=None)
        self._params = FailureCalibratorParams(weights=weights.astype(float))

    def predict(
        self,
        customer_present_probability: float,
        address_quality_score: float,
        weather_severity: float,
        prior_failed_attempts: int,
        cod_order: bool,
    ) -> float:
        assert self._params is not None
        w = self._params.weights

        cpp = _clamp01(customer_present_probability)
        aqs = _clamp01(address_quality_score)
        ws = _clamp01(weather_severity)
        pfa_term = min(float(prior_failed_attempts) / 3.0, 1.0)
        cod_term = 1.0 if cod_order else 0.0

        f1 = 1.0 - cpp
        f2 = 1.0 - aqs
        f3 = ws
        f4 = pfa_term
        f5 = cod_term

        prob = float(np.dot(np.array([f1, f2, f3, f4, f5, 1.0], dtype=float), w))
        prob = float(min(max(prob, 0.0), 0.99))
        prob = float(round(prob, 3))
        return prob


_FORECAST_CALIBRATOR = ForecastCalibrator()
_FAILURE_CALIBRATOR = DeliveryFailureCalibrator()


def calibrate_forecast(baseline: float, promo_campaign: bool, holiday_period: bool) -> Dict[str, object]:
    return _FORECAST_CALIBRATOR.predict(baseline=float(baseline), promo_campaign=bool(promo_campaign), holiday_period=bool(holiday_period))


def calibrate_delivery_failure(
    customer_present_probability: float,
    address_quality_score: float,
    weather_severity: float,
    prior_failed_attempts: int,
    cod_order: bool,
) -> float:
    return _FAILURE_CALIBRATOR.predict(
        customer_present_probability=customer_present_probability,
        address_quality_score=address_quality_score,
        weather_severity=weather_severity,
        prior_failed_attempts=prior_failed_attempts,
        cod_order=cod_order,
    )


def evaluate_calibrators(seed: int = 99, n_samples: int = 1000) -> Dict[str, float]:
    """
    Returns compact offline evaluation metrics for calibration quality.
    """
    rng = np.random.default_rng(seed)

    # Forecast evaluation
    baseline = rng.uniform(200.0, 2200.0, size=n_samples)
    promo = rng.integers(0, 2, size=n_samples).astype(bool)
    holiday = rng.integers(0, 2, size=n_samples).astype(bool)

    y_true_forecast = np.array(
        [
            _heuristic_forecast_from_baseline(float(b), bool(p), bool(h))["volume"]
            for b, p, h in zip(baseline, promo, holiday, strict=False)
        ],
        dtype=float,
    )
    y_pred_forecast = np.array(
        [
            float(calibrate_forecast(float(b), bool(p), bool(h))["volume"])
            for b, p, h in zip(baseline, promo, holiday, strict=False)
        ],
        dtype=float,
    )
    forecast_mae = float(np.mean(np.abs(y_true_forecast - y_pred_forecast)))

    # Failure probability evaluation
    cpp = rng.uniform(0.0, 1.0, size=n_samples)
    aqs = rng.uniform(0.0, 1.0, size=n_samples)
    ws = rng.uniform(0.0, 1.0, size=n_samples)
    pfa = rng.integers(0, 4, size=n_samples)
    cod = rng.integers(0, 2, size=n_samples).astype(bool)
    y_true_fail = np.array(
        [
            _heuristic_delivery_failure(float(c), float(a), float(w), int(p), bool(cd))
            for c, a, w, p, cd in zip(cpp, aqs, ws, pfa, cod, strict=False)
        ],
        dtype=float,
    )
    y_pred_fail = np.array(
        [
            calibrate_delivery_failure(float(c), float(a), float(w), int(p), bool(cd))
            for c, a, w, p, cd in zip(cpp, aqs, ws, pfa, cod, strict=False)
        ],
        dtype=float,
    )
    brier_like = float(np.mean((y_true_fail - y_pred_fail) ** 2))

    return {
        "forecast_mae": round(forecast_mae, 4),
        "failure_brier_like": round(brier_like, 6),
        "samples": float(n_samples),
    }

