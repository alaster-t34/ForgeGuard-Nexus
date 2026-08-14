from __future__ import annotations

from app.core.rules import compute_anomaly_probability
from app.domain.enums import AgentName, EvidenceKind
from app.domain.schemas import EvidenceItem, IncidentRecord
from app.agents.base import Agent


class PerceptionAgent(Agent[list[EvidenceItem]]):
    name = AgentName.PERCEPTION

    @property
    def action_name(self) -> str:
        return "fuse_multimodal_observations"

    def start_rationale(self, incident: IncidentRecord) -> str:
        return "Normalize telemetry and visual observations into traceable evidence."

    async def execute(self, incident: IncidentRecord) -> list[EvidenceItem]:
        telemetry = incident.input.telemetry
        vision = incident.input.vision
        probability = compute_anomaly_probability(telemetry, vision)
        items = [
            EvidenceItem(
                kind=EvidenceKind.TELEMETRY,
                source="sensor-gateway",
                title="Vibration RMS",
                value=telemetry.vibration_rms_g,
                unit="g",
                confidence=telemetry.quality,
            ),
            EvidenceItem(
                kind=EvidenceKind.SIGNAL_FEATURE,
                source="signal-feature-service",
                title="Kurtosis",
                value=telemetry.vibration_kurtosis,
                confidence=telemetry.quality,
            ),
            EvidenceItem(
                kind=EvidenceKind.TELEMETRY,
                source="sensor-gateway",
                title="Bearing temperature",
                value=telemetry.temperature_c,
                unit="°C",
                confidence=telemetry.quality,
            ),
            EvidenceItem(
                kind=EvidenceKind.MODEL_OUTPUT,
                source="multimodal-fusion-v1",
                title="Fused anomaly probability",
                value=round(probability, 4),
                confidence=min(telemetry.quality, 0.95),
                metadata={"model_role": "decision-support", "calibrated": True},
            ),
        ]
        if vision:
            items.append(
                EvidenceItem(
                    kind=EvidenceKind.VISION,
                    source=vision.source,
                    title="Visual anomaly observation",
                    value={
                        "score": vision.anomaly_score,
                        "class": vision.class_name,
                        "confidence": vision.confidence,
                        "region": vision.region,
                    },
                    confidence=vision.confidence,
                    metadata={"image_id": vision.image_id, "heatmap_uri": vision.heatmap_uri},
                )
            )
        return items
