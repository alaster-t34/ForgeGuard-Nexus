from __future__ import annotations

from app.core.rules import compute_anomaly_probability, compute_health_score
from app.domain.enums import AgentName
from app.domain.schemas import IncidentRecord, VerificationRequest, VerificationResult


class VerificationAgent:
    name = AgentName.VERIFICATION

    async def run(self, incident: IncidentRecord, request: VerificationRequest) -> VerificationResult:
        if not incident.reliability:
            raise ValueError("Reliability baseline is required")
        probability = compute_anomaly_probability(request.telemetry, request.vision)
        post_score = compute_health_score(probability, request.telemetry)
        pre_score = incident.reliability.health_score
        improvement = ((post_score - pre_score) / max(pre_score, 1.0)) * 100.0
        anomalies: list[str] = []
        if request.telemetry.vibration_rms_g > 1.8:
            anomalies.append("vibration remains above warning threshold")
        if request.telemetry.temperature_c > 72:
            anomalies.append("temperature remains above warning threshold")
        if request.vision and request.vision.anomaly_score > 0.55:
            anomalies.append("visual anomaly remains detectable")
        if request.telemetry.quality < 0.75:
            anomalies.append("post-maintenance evidence quality is insufficient")
        passed = not anomalies and post_score >= 75 and improvement >= 20
        verdict = "close" if passed else "reopen" if anomalies else "monitor"
        pre_vibration = max(incident.input.telemetry.vibration_rms_g, 1e-6)
        vibration_reduction = max(0.0, (pre_vibration - request.telemetry.vibration_rms_g) / pre_vibration * 100)
        pre_energy = incident.input.telemetry.energy_kw
        post_energy = request.telemetry.energy_kw
        energy_reduction = 0.0
        if pre_energy and post_energy and pre_energy > 0:
            energy_reduction = max(0.0, (pre_energy - post_energy) / pre_energy * 100)
        return VerificationResult(
            passed=passed,
            verdict=verdict,
            pre_health_score=pre_score,
            post_health_score=post_score,
            improvement_percent=round(improvement, 1),
            remaining_anomalies=anomalies,
            vibration_reduction_percent=round(vibration_reduction, 1),
            energy_reduction_percent=round(energy_reduction, 1),
            rationale=(
                "Post-maintenance evidence passed quality checks, vibration and thermal indicators returned below warning thresholds, and health improved materially."
                if passed
                else "Verification criteria were not all satisfied; the work order remains open and the incident is reopened."
            ),
        )
