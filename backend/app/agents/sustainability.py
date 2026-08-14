from __future__ import annotations

from app.agents.base import Agent
from app.domain.enums import AgentName
from app.domain.schemas import IncidentRecord, SustainabilityAssessment


class SustainabilityAgent(Agent[SustainabilityAssessment]):
    name = AgentName.SUSTAINABILITY

    @property
    def action_name(self) -> str:
        return "estimate_energy_waste_and_lifecycle_impact"

    def start_rationale(self, incident: IncidentRecord) -> str:
        return "Quantify the environmental cost of abnormal operation and maintenance alternatives."

    async def execute(self, incident: IncidentRecord) -> SustainabilityAssessment:
        telemetry = incident.input.telemetry
        asset_evidence = next(
            (item for item in incident.evidence if item.source == "asset.query" and isinstance(item.value, dict)),
            None,
        )
        asset = asset_evidence.value if asset_evidence else {}
        baseline = float(asset.get("energy_baseline_kw", 8.0))
        measured = float(telemetry.energy_kw or baseline * (1 + max(0.0, telemetry.vibration_rms_g - 0.4) * 0.12))
        excess_kw = max(0.0, measured - baseline)
        excess_kwh_day = excess_kw * 20.0
        factor = float(asset.get("carbon_factor_kg_per_kwh", 0.55))
        co2e = excess_kwh_day * factor
        severity = incident.diagnosis.primary.probability if incident.diagnosis else 0.5
        scrap_risk = round(max(0.0, severity - 0.45) * telemetry.load_percent / 12.0, 2)
        avoided_waste = round(2.4 + severity * 2.8, 2)
        score = max(20.0, 100.0 - min(70.0, excess_kwh_day * 4.5 + scrap_risk * 5.0))
        return SustainabilityAssessment(
            score=round(score, 1),
            baseline_energy_kw=round(baseline, 2),
            abnormal_energy_kw=round(measured, 2),
            estimated_excess_energy_kwh_per_day=round(excess_kwh_day, 2),
            estimated_excess_co2e_kg_per_day=round(co2e, 2),
            estimated_scrap_risk_kg=scrap_risk,
            repair_avoided_waste_kg=avoided_waste,
            assumptions=[
                "Twenty productive operating hours per day",
                "Site carbon factor taken from the asset master record",
                "Waste estimate is a decision-support estimate, not a certified life-cycle assessment",
            ],
            confidence=round(min(0.92, telemetry.quality * 0.88), 3),
        )
