from __future__ import annotations

from pathlib import Path
from typing import Any

from app.models.contracts import ModelAdapter, ModelMetadata


class AnomalibAdapter(ModelAdapter[Path, dict[str, Any]]):
    """Optional adapter for Anomalib 2.x models.

    Import is delayed so the core demo remains lightweight and reproducible. The
    adapter accepts exported OpenVINO/PyTorch artifacts selected through the model
    catalog. No one model is described as universally best; selection is benchmarked
    on the actual camera, lighting, part geometry, and latency target.
    """

    metadata = ModelMetadata(
        id="anomalib-runtime",
        role="visual-anomaly-detection",
        version="2.x",
        license="Apache-2.0",
        runtime=("pytorch", "openvino", "cuda", "cpu"),
        calibrated=False,
        source="https://github.com/open-edge-platform/anomalib",
    )

    def __init__(self, model_path: Path, threshold: float = 0.5) -> None:
        self.model_path = model_path
        self.threshold = threshold

    async def infer(self, payload: Path) -> dict[str, Any]:
        try:
            from anomalib.deploy import OpenVINOInferencer  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional integration
            raise RuntimeError("Install the optional anomalib/OpenVINO runtime") from exc
        inferencer = OpenVINOInferencer(path=self.model_path)
        prediction = inferencer.predict(image=payload)
        score = float(prediction.pred_score)
        return {
            "anomaly_score": score,
            "is_anomalous": score >= self.threshold,
            "anomaly_map": getattr(prediction, "anomaly_map", None),
        }
