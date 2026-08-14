from __future__ import annotations

from app.core.rules import compute_anomaly_probability, compute_health_score, infer_risk
from app.domain.enums import AgentName, RiskLevel
from app.domain.schemas import IncidentRecord, ReliabilityResult
from app.agents.base import Agent


class ReliabilityAgent(Agent[ReliabilityResult]):
    name = AgentName.RELIABILITY

    @property
    def action_name(self) -> str:
        return "estimate_health_and_remaining_useful_life"

    def start_rationale(self, incident: IncidentRecord) -> str:
        return "Estimate a conservative RUL interval and continuation risk from calibrated health evidence."

    async def execute(self, incident: IncidentRecord) -> ReliabilityResult:
        telemetry = incident.input.telemetry
        probability = compute_anomaly_probability(telemetry, incident.input.vision)
        health = compute_health_score(probability, telemetry)
        risk = infer_risk(probability, telemetry)

        # Deterministic calibrated fallback. A production model adapter may replace
        # this calculation, but the quantile contract and uncertainty gate remain.
        base_hours = max(2.0, (health / 100.0) ** 2.2 * 720.0)
        load_penalty = max(0.45, 1.0 - max(0, telemetry.load_percent - 70) / 140.0)
        p50 = base_hours * load_penalty
        uncertainty = 0.52 if telemetry.quality < 0.8 else 0.32
        p10 = max(1.0, p50 * (1.0 - uncertainty))
        p90 = p50 * (1.0 + uncertainty * 1.5)
        confidence = min(0.94, telemetry.quality * (0.95 if incident.input.vision else 0.78))

        factors = []
        if telemetry.temperature_c > 72:
            factors.append("elevated temperature")
        if telemetry.vibration_kurtosis > 5:
            factors.append("impulsive vibration")
        if telemetry.load_percent > 80:
            factors.append("high operating load")
        if telemetry.quality < 0.8:
            factors.append("reduced sensor confidence")

        continuation_risk = risk
        if p10 < 8 and risk == RiskLevel.HIGH:
            continuation_risk = RiskLevel.CRITICAL

        return ReliabilityResult(
            health_score=health,
            rul_hours_p50=round(p50, 1),
            rul_hours_p10=round(p10, 1),
            rul_hours_p90=round(p90, 1),
            continuation_risk=continuation_risk,
            confidence=round(confidence, 3),
            limiting_factors=factors,
        )
