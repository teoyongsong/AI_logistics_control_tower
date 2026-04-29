# Forecast Calibrator Model Card

## Purpose
Calibrates shipment volume prediction in the Control Tower from baseline demand + campaign flags.

## Inputs
- `baseline`: mean of latest 7 daily volumes
- `promo_campaign`: boolean
- `holiday_period`: boolean

## Output
- `volume` (int)
- `trend` (`upward` | `stable` | `downward`)
- `capacity_risk` (`low` | `medium` | `high`)
- `recommended_buffer_pct` (3, 8, 15)

## Training / Calibration Data
Current version is calibrated on a reproducible synthetic dataset generated from the legacy prototype logic.

## Evaluation
Run:

```bash
python -m backend.eval.run_eval
```

Primary metric:
- `forecast_mae`

## Limitations
- Not yet trained on real operational data.
- Region is currently a context label (not a learned feature).

## Retraining Guidance
- Replace synthetic generation with anonymized historical shipments.
- Recompute coefficients and thresholds monthly or when demand regime shifts.

