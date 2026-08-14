from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from app.models.portable_hgb import PortableCalibratedHGB

from app.benchmark.features import extract_vibration_features
from app.models.contracts import ModelAdapter, ModelMetadata


class SelectedVibrationAdapter(ModelAdapter[dict[str, Any], dict[str, Any]]):
    """Load the reproducibly selected vibration benchmark artifact.

    The adapter is optional. The API remains available when no benchmark has
    been run, but the runtime will then use explicit heuristic fallback logic.
    """

    def __init__(self, model_card_path: Path) -> None:
        card = json.loads(model_card_path.read_text(encoding="utf-8"))
        self.card = card
        self.model_card_path = model_card_path
        project_root = model_card_path.parents[3]
        self.artifact_path = project_root / card["artifact"]
        self.label_names = list(card["label_names"])
        self.feature_names = list(card["feature_names"])
        self.sample_rate_hz = float(card["sample_rate_hz"])
        self.model_id = str(card["model_id"])
        if self.artifact_path.suffix == ".pt":
            self._mode = "torch"
        elif self.artifact_path.suffix == ".npz":
            self._mode = "portable-hgb"
        else:
            self._mode = "sklearn-joblib"

        if self._mode == "portable-hgb":
            self.model = PortableCalibratedHGB(self.artifact_path)
        elif self._mode == "sklearn-joblib":
            # Research-only compatibility path. Production releases point to the
            # portable NPZ artifact so startup never depends on pickle internals
            # or the NumPy version used during training.
            import joblib
            import sklearn

            runtime_requirements = card.get("runtime_requirements", {})
            expected_sklearn = str(
                runtime_requirements.get("scikit_learn_training", "")
            ).strip()
            if expected_sklearn and sklearn.__version__ != expected_sklearn:
                raise RuntimeError(
                    "Research joblib model compatibility error: "
                    f"scikit-learn {expected_sklearn} is required, but "
                    f"{sklearn.__version__} is installed. Use the portable NPZ release "
                    "artifact or recreate the exact training environment."
                )
            self.model = joblib.load(self.artifact_path)
        else:
            import torch
            from app.benchmark.models import TinyResNet1DClassifier

            checkpoint = torch.load(self.artifact_path, map_location="cpu", weights_only=False)
            classifier = TinyResNet1DClassifier(
                classes=int(checkpoint["classes"]), epochs=1, seed=int(checkpoint.get("seed", 42))
            )
            classifier.model.load_state_dict(checkpoint["state_dict"])
            classifier.mean = float(checkpoint["mean"])
            classifier.std = float(checkpoint["std"])
            classifier.temperature = float(checkpoint.get("temperature", 1.0))
            self.model = classifier
        self.metadata = ModelMetadata(
            id="selected-vibration-model",
            role="vibration-fault-classification",
            version="0.2.1",
            license="Apache-2.0 for ForgeGuard artifact; training-source terms disclosed separately",
            runtime=("python", "cpu", self._mode),
            calibrated=self._mode in {"portable-hgb", "sklearn-joblib"},
            source=f"ForgeGuard benchmark selection: {self.model_id}",
        )

    async def infer(self, payload: dict[str, Any]) -> dict[str, Any]:
        samples = np.asarray(payload["samples"], dtype=np.float32).reshape(-1)
        sample_rate_hz = float(payload.get("sample_rate_hz", self.sample_rate_hz))
        features = extract_vibration_features(samples, sample_rate_hz)
        ordered = np.asarray([[features[name] for name in self.feature_names]], dtype=np.float64)
        raw = samples[None, :]
        if self._mode in {"portable-hgb", "sklearn-joblib"}:
            probabilities = np.asarray(self.model.predict_proba(ordered), dtype=np.float64)[0]
        else:
            probabilities = np.asarray(self.model.predict_proba(ordered, raw), dtype=np.float64)[0]
        prediction_index = int(np.argmax(probabilities))
        return {
            "model_id": self.model_id,
            "class_name": self.label_names[prediction_index],
            "confidence": float(probabilities[prediction_index]),
            "probabilities": {
                name: float(probabilities[index]) for index, name in enumerate(self.label_names)
            },
            "features": dict(features),
        }
