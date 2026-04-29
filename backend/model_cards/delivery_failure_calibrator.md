# Delivery Failure Calibrator Model Card

## Purpose
Estimates last-mile failure probability for intervention routing.

## Inputs
- `customer_present_probability`
- `address_quality_score`
- `weather_severity`
- `prior_failed_attempts`
- `cod_order`

## Output
- `failure_probability` (0.0 to 0.99)
- `recommended_action` (`normal_dispatch` or `confirm_delivery_window`)

## Training / Calibration Data
Current version is calibrated on a reproducible synthetic dataset generated from the baseline weighted-risk formula.

## Evaluation
Run:

```bash
python -m backend.eval.run_eval
```

Primary metric:
- `failure_brier_like`

## Limitations
- Synthetic calibration only; no live delivery outcome labels yet.
- Thresholding is policy-driven and should be reviewed with operations.

## Retraining Guidance
- Use real delivery outcomes for supervised recalibration.
- Validate per market to avoid one-threshold-fits-all behavior.

