from __future__ import annotations

import json

from backend.services.calibrators import evaluate_calibrators


def main() -> None:
    metrics = evaluate_calibrators(seed=99, n_samples=2000)
    print(json.dumps(metrics, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

