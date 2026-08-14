from __future__ import annotations

import json
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.models.portable_hgb import PortableCalibratedHGB  # noqa: E402

CARD = ROOT / "backend" / "research" / "artifacts" / "selected_vibration_model.json"


def package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "not-installed"


def main() -> int:
    card = json.loads(CARD.read_text(encoding="utf-8"))
    artifact = ROOT / card["artifact"]
    print(f"Python: {sys.version.split()[0]}")
    print(f"NumPy: {np.__version__}")
    print(f"scikit-learn: {package_version('scikit-learn')} (benchmark/retraining)")
    print(f"Runtime artifact: {artifact.name}")
    print(f"Artifact format: {card.get('artifact_format')}")

    model = PortableCalibratedHGB(artifact)
    probabilities = model.predict_proba(np.zeros((1, model.n_features), dtype=np.float64))
    if probabilities.shape != (1, model.n_classes):
        print(f"FAIL: unexpected probability shape {probabilities.shape}")
        return 2
    if not np.all(np.isfinite(probabilities)) or not np.isclose(probabilities.sum(), 1.0):
        print("FAIL: portable model returned invalid probabilities")
        return 3

    print(f"Model: {card['model_id']}")
    print(f"Model class: {model.model_class}")
    print(f"Probability sum: {float(probabilities.sum()):.12f}")
    print("PASS: portable bundled model loaded without pickle/joblib")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
