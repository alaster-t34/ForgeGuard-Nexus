from __future__ import annotations

from app.agents.base import Agent
from app.domain.enums import AgentName, RiskLevel
from app.domain.schemas import IncidentRecord, SafetyAssessment


class HumanSafetyAgent(Agent[SafetyAssessment]):
    name = AgentName.SAFETY

    @property
    def action_name(self) -> str:
        return "assess_human_safety_and_authorization"

    def start_rationale(self, incident: IncidentRecord) -> str:
        return "Protect workers by identifying exposure, isolation, competence and approval constraints."

    async def execute(self, incident: IncidentRecord) -> SafetyAssessment:
        telemetry = incident.input.telemetry
        severity = incident.reliability.continuation_risk if incident.reliability else incident.risk
        hazards = ["rotating machinery", "stored mechanical energy"]
        controls = [
            "Stop at an authorized safe transition",
            "Apply lockout/tagout and verify zero-energy state",
            "Keep guards installed until the shaft is stationary",
        ]
        ppe = ["safety glasses", "cut-resistant gloves", "safety footwear"]
        certifications = ["LOTO authorization", "mechanical maintenance competency"]
        minimum_technicians = 1
        score = 88.0

        if telemetry.temperature_c >= 70:
            hazards.append("hot surface exposure")
            controls.append("Verify bearing housing temperature before contact")
            ppe.append("heat-resistant gloves")
            score -= 8
        if telemetry.rotational_speed_rpm >= 2500:
            hazards.append("high-speed ejection risk")
            controls.append("Require full stop and guard integrity confirmation")
            score -= 8
        if severity in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
            hazards.append("secondary damage during continued operation")
            minimum_technicians = 2
            controls.append("Use a two-person verification before restart")
            score -= 10 if severity == RiskLevel.HIGH else 18
        if incident.diagnosis and incident.diagnosis.needs_more_evidence:
            controls.append("Do not authorize intrusive maintenance until evidence is reacquired")
            score -= 5

        risk = RiskLevel.LOW
        if score < 55:
            risk = RiskLevel.CRITICAL
        elif score < 70:
            risk = RiskLevel.HIGH
        elif score < 84:
            risk = RiskLevel.MEDIUM

        return SafetyAssessment(
            score=max(0.0, round(score, 1)),
            risk=risk,
            hazards=hazards,
            required_controls=controls,
            required_ppe=sorted(set(ppe)),
            loto_required=True,
            minimum_technicians=minimum_technicians,
            required_certifications=certifications,
            approval_required=True,
            rationale=(
                "The platform may recommend work, but an authorized person must confirm isolation, "
                "competence and production release before execution."
            ),
        )
