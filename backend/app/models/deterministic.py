from __future__ import annotations

from app.core.rules import compute_anomaly_probability
from app.domain.schemas import IncidentInput
from app.models.contracts import ModelAdapter, ModelMetadata


class DeterministicFusionAdapter(ModelAdapter[IncidentInput, dict[str, float]]):
    metadata = ModelMetadata(
        id="rules-calibrated-fallback",
        role="multimodal-anomaly-fusion",
        version="1.0.0",
        license="Apache-2.0",
        runtime=("python", "cpu", "edge"),
        calibrated=True,
        source="ForgeGuard Nexus",
    )

    async def infer(self, payload: IncidentInput) -> dict[str, float]:
        probability = compute_anomaly_probability(payload.telemetry, payload.vision)
        return {"anomaly_probability": probability, "confidence": payload.telemetry.quality}
