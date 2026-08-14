from __future__ import annotations

from app.agents.base import Agent
from app.domain.enums import AgentName, EvidenceKind
from app.domain.schemas import EvidenceItem, IncidentRecord


class EvidenceQualityAgent(Agent[list[EvidenceItem]]):
    name = AgentName.EVIDENCE_QUALITY

    @property
    def action_name(self) -> str:
        return "validate_sensor_integrity_and_cross_modal_consistency"

    def start_rationale(self, incident: IncidentRecord) -> str:
        return "Reject unsafe automation when acquisition quality or modal agreement is insufficient."

    async def execute(self, incident: IncidentRecord) -> list[EvidenceItem]:
        telemetry = incident.input.telemetry
        vision = incident.input.vision
        warnings: list[str] = []
        if telemetry.quality < 0.8:
            warnings.append("Telemetry quality is below the automatic-decision threshold")
        if telemetry.vibration_rms_g <= 0.001:
            warnings.append("Vibration amplitude is implausibly low")
        if telemetry.vibration_kurtosis > 20:
            warnings.append("Extreme impulsiveness may indicate sensor mounting or clipping")
        if vision and vision.confidence < 0.55:
            warnings.append("Visual model confidence is weak")
        if vision and vision.anomaly_score < 0.25 and telemetry.vibration_kurtosis > 7:
            warnings.append("Vision and vibration channels disagree")
        score = max(0.0, min(1.0, telemetry.quality - 0.08 * len(warnings)))
        return [
            EvidenceItem(
                kind=EvidenceKind.SIGNAL_FEATURE,
                source="evidence-quality-agent",
                title="Evidence quality gate",
                value={
                    "score": round(score, 3),
                    "warnings": warnings,
                    "decision": "accept" if score >= 0.72 and len(warnings) < 2 else "reacquire",
                },
                confidence=1.0,
                metadata={"safety_gate": True},
            )
        ]
