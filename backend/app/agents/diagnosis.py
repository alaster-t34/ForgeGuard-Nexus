from __future__ import annotations

from app.core.rules import compute_anomaly_probability, infer_risk
from app.domain.enums import AgentName, RiskLevel
from app.domain.schemas import DiagnosticHypothesis, DiagnosisResult, IncidentRecord
from app.agents.base import Agent
from app.services.scenario_catalog import get_scenario


class DiagnosisAgent(Agent[DiagnosisResult]):
    name = AgentName.DIAGNOSIS

    @property
    def action_name(self) -> str:
        return "generate_evidence_grounded_diagnosis"

    def start_rationale(self, incident: IncidentRecord) -> str:
        return "Compare multimodal evidence against industrial failure modes, operating context and contradictions."

    async def execute(self, incident: IncidentRecord) -> DiagnosisResult:
        telemetry = incident.input.telemetry
        vision = incident.input.vision
        probability = compute_anomaly_probability(telemetry, vision)
        risk = infer_risk(probability, telemetry)
        evidence_ids = [item.id for item in incident.evidence]
        visual_class = vision.class_name if vision else None
        contradictions: list[str] = []

        if telemetry.quality < 0.75:
            contradictions.append("Telemetry quality is below the automatic-decision threshold.")
        if vision and vision.anomaly_score < 0.3 and telemetry.vibration_kurtosis > 7:
            contradictions.append("Vision appears normal while impact features are severe.")

        scenario = None
        if incident.input.scenario_key:
            try:
                scenario = get_scenario(incident.input.scenario_key)
            except ValueError:
                scenario = None

        if scenario is not None:
            fault_mode = scenario["fault_mode"]
            rationale = scenario["rationale"]
            force_reacquire = bool(scenario.get("force_reacquire"))
            primary_probability = min(0.97, max(0.66, probability + (0.04 if not force_reacquire else -0.08)))
            if force_reacquire:
                primary_probability = min(primary_probability, 0.64)
                contradictions.append("The scenario is governed as an evidence-quality or cross-modal conflict case.")
            alternative_names = scenario.get("alternatives") or ["unresolved rotating-component anomaly"]
            alternatives = [
                DiagnosticHypothesis(
                    fault_mode=name,
                    probability=max(0.05, round(primary_probability - 0.22 - index * 0.09, 3)),
                    severity=RiskLevel.MEDIUM if risk == RiskLevel.LOW else risk,
                    rationale="Alternative hypothesis retained until targeted evidence or inspection rules it out.",
                    evidence_ids=evidence_ids,
                    contradictions=[],
                )
                for index, name in enumerate(alternative_names[:3])
            ]
        else:
            if telemetry.temperature_c >= 86 and (not vision or vision.anomaly_score < 0.55):
                fault_mode = "lubrication degradation or excessive friction"
                rationale = (
                    "Critical thermal rise with moderate broadband vibration and no localized visual defect "
                    "is most consistent with lubrication or friction-related degradation."
                )
                primary_probability = min(0.94, probability + 0.08)
            elif visual_class in {"pitted_surface", "spall", "outer_race_spall"} or (
                telemetry.vibration_kurtosis >= 6.5 and telemetry.crest_factor >= 4.8
            ):
                fault_mode = "outer-race localized spalling"
                rationale = (
                    "High kurtosis and crest factor indicate repetitive impacts; the localized surface anomaly "
                    "provides independent visual support for outer-race damage."
                )
                primary_probability = min(0.96, probability + 0.05)
            else:
                fault_mode = "unresolved rotating-component anomaly"
                rationale = (
                    "The available evidence indicates abnormal behavior but is insufficient to resolve a single "
                    "failure mode without additional acquisition."
                )
                primary_probability = max(0.45, probability)

            alternatives = [
                DiagnosticHypothesis(
                    fault_mode="inner-race localized defect",
                    probability=max(0.05, primary_probability - 0.28),
                    severity=RiskLevel.HIGH if risk in {RiskLevel.HIGH, RiskLevel.CRITICAL} else RiskLevel.MEDIUM,
                    rationale="Impact-dominant vibration can also arise from an inner-race defect; speed-order evidence is needed.",
                    evidence_ids=evidence_ids,
                    contradictions=["Current visual evidence does not localize the inner race."],
                ),
                DiagnosticHypothesis(
                    fault_mode="sensor mounting or acquisition artifact",
                    probability=0.38 if telemetry.quality < 0.75 else 0.08,
                    severity=RiskLevel.MEDIUM,
                    rationale="Low signal quality and channel disagreement can imitate impulsive features.",
                    evidence_ids=evidence_ids,
                ),
            ]

        needs_more = bool(contradictions) or telemetry.quality < 0.8 or primary_probability < 0.65
        requested = []
        if needs_more:
            requested = [
                "Repeat acquisition after sensor mounting and timestamp validation",
                "Capture an independent second modality or inspection angle",
                "Confirm speed, load, process state and unit metadata during acquisition",
            ]

        return DiagnosisResult(
            primary=DiagnosticHypothesis(
                fault_mode=fault_mode,
                probability=round(primary_probability, 3),
                severity=risk,
                rationale=rationale,
                evidence_ids=evidence_ids,
                contradictions=contradictions,
            ),
            alternatives=alternatives,
            data_quality=round(telemetry.quality, 3),
            needs_more_evidence=needs_more,
            requested_evidence=requested,
        )
