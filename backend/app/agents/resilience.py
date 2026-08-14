from __future__ import annotations

from app.agents.base import Agent
from app.domain.enums import AgentName, RiskLevel
from app.domain.schemas import IncidentRecord, ResilienceAssessment


class ResilienceAgent(Agent[ResilienceAssessment]):
    name = AgentName.RESILIENCE

    @property
    def action_name(self) -> str:
        return "evaluate_operational_resilience"

    def start_rationale(self, incident: IncidentRecord) -> str:
        return "Assess recovery time, spare-part exposure, workforce readiness and offline fallback."

    async def execute(self, incident: IncidentRecord) -> ResilienceAssessment:
        inventory = next(
            (item.value for item in incident.evidence if item.source == "inventory.query" and isinstance(item.value, dict)),
            {"items": []},
        )
        production = next(
            (item.value for item in incident.evidence if item.source == "production.context" and isinstance(item.value, dict)),
            {},
        )
        workforce = next(
            (item.value for item in incident.evidence if item.source == "workforce.query" and isinstance(item.value, dict)),
            {"available": 1, "qualified": 1},
        )
        items = inventory.get("items", [])
        inventory_ready = all(int(item.get("available", 0)) > 0 for item in items) if items else False
        qualified = int(workforce.get("qualified", 0))
        available = int(workforce.get("available", 0))
        readiness = min(1.0, (qualified / 2.0) * 0.7 + min(1.0, available / 2.0) * 0.3)
        buffer_minutes = int(production.get("downstream_buffer_minutes", 0))
        safe_transition = int(production.get("minutes_to_safe_transition", 30))
        score = 52.0 + min(18.0, buffer_minutes * 0.35) + readiness * 20.0
        if inventory_ready:
            score += 10
        else:
            score -= 15
        score = max(0.0, min(100.0, score))
        spare_risk = RiskLevel.LOW if inventory_ready else RiskLevel.HIGH
        fallback = (
            "Operate the edge safety policy offline, preserve evidence locally and synchronize after network recovery."
        )
        constraints = []
        if not inventory_ready:
            constraints.append("One or more required parts are unavailable")
        if readiness < 0.7:
            constraints.append("Qualified workforce coverage is limited")
        if buffer_minutes < 20:
            constraints.append("Downstream production buffer is narrow")
        return ResilienceAssessment(
            score=round(score, 1),
            recovery_time_minutes=max(20, safe_transition + 55),
            spare_part_risk=spare_risk,
            workforce_readiness=round(readiness, 3),
            production_buffer_minutes=max(0, buffer_minutes),
            offline_capable=True,
            fallback_plan=fallback,
            constraints=constraints,
        )
