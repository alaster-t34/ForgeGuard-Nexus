from __future__ import annotations

from app.agents.base import Agent
from app.domain.enums import AgentName, RiskLevel
from app.domain.schemas import IncidentRecord, MaintenanceOption, MaintenancePlan
from app.services.scenario_catalog import get_scenario


class MaintenancePlannerAgent(Agent[MaintenancePlan]):
    name = AgentName.PLANNER

    @property
    def action_name(self) -> str:
        return "compare_multi_objective_maintenance_strategies"

    def start_rationale(self, incident: IncidentRecord) -> str:
        return "Balance human safety, operational resilience, sustainability, downtime, cost and evidence quality."

    @staticmethod
    def _overall(safety: float, resilience: float, sustainability: float, cost: float, downtime: int) -> float:
        cost_score = max(0.0, 100.0 - cost / 8.0)
        downtime_score = max(0.0, 100.0 - downtime * 0.9)
        return round(
            0.34 * safety + 0.24 * resilience + 0.18 * sustainability + 0.12 * cost_score + 0.12 * downtime_score,
            1,
        )

    @staticmethod
    def _profile(incident: IncidentRecord) -> dict:
        if incident.input.scenario_key:
            try:
                return get_scenario(incident.input.scenario_key)["maintenance"]
            except ValueError:
                pass
        return {
            "title": "受控停机并执行针对性检修",
            "description": "在最近安全生产窗口停机隔离，依据诊断结果完成检查、维修和复测。",
            "parts": ["approved maintenance kit"],
            "skills": ["mechanical maintenance", "LOTO authorization", "verification acquisition"],
            "downtime": 60,
            "cost": 600.0,
            "team": "设备可靠性组",
            "constrained_title": "降载运行至最近安全窗口",
            "constrained_description": "降低负载、提高采样频率，并在硬停机阈值触发前转入维修。",
        }

    async def execute(self, incident: IncidentRecord) -> MaintenancePlan:
        if not all([incident.diagnosis, incident.reliability, incident.safety, incident.sustainability, incident.resilience]):
            raise ValueError("Diagnosis, reliability, safety, sustainability and resilience results are required")

        profile = self._profile(incident)
        continuation = incident.reliability.continuation_risk
        critical = continuation == RiskLevel.CRITICAL
        high = continuation == RiskLevel.HIGH
        energy_excess = incident.sustainability.estimated_excess_energy_kwh_per_day
        co2e_excess = incident.sustainability.estimated_excess_co2e_kg_per_day
        inventory_ready = incident.resilience.spare_part_risk == RiskLevel.LOW
        parts = list(profile.get("parts", []))
        primary_downtime = int(profile.get("downtime", 60))
        primary_cost = float(profile.get("cost", 600.0))

        primary = MaintenanceOption(
            id="replace-now",
            title=profile["title"],
            description=profile["description"],
            risk=RiskLevel.LOW,
            estimated_downtime_minutes=primary_downtime,
            estimated_cost=primary_cost,
            production_impact="在受控窗口执行；生产影响由排产缓冲、备用资源和工单步骤共同约束。",
            required_parts=parts,
            required_skills=list(profile.get("skills", [])),
            rationale="该方案对人员安全、故障消除概率和维修后可验证性最优。",
            score=0,
            safety_score=94.0,
            resilience_score=91.0 if inventory_ready or not parts else 58.0,
            sustainability_score=88.0,
            energy_impact_kwh=-energy_excess,
            co2e_impact_kg=-co2e_excess,
            waste_impact_kg=max(0.0, min(4.0, primary_cost / 900.0)),
            human_exposure_minutes=max(8, round(primary_downtime * 0.45)),
            contraindications=[] if inventory_ready or not parts else ["所需备件当前不可用或尚未完成替代件认证"],
        )
        primary.score = self._overall(
            primary.safety_score,
            primary.resilience_score,
            primary.sustainability_score,
            primary.estimated_cost,
            primary.estimated_downtime_minutes,
        )

        constrained = MaintenanceOption(
            id="constrained-operation",
            title=profile.get("constrained_title", "降载运行至最近安全窗口"),
            description=profile.get("constrained_description", "降低负载、提高采样频率，并在硬停机阈值触发前转入维修。"),
            risk=RiskLevel.CRITICAL if critical else RiskLevel.HIGH if high else RiskLevel.MEDIUM,
            estimated_downtime_minutes=max(10, round(primary_downtime * 0.7)),
            estimated_cost=max(40.0, primary_cost * 0.82),
            production_impact="保护当前批次或等待资源，但存在受控的继续运行暴露。",
            required_parts=parts,
            required_skills=list(profile.get("skills", [])) + ["authorized production supervisor"],
            rationale="仅在生产后果显著、硬停机阈值已启用且人员授权完整时可接受。",
            score=0,
            safety_score=32.0 if critical else 58.0,
            resilience_score=76.0,
            sustainability_score=46.0,
            energy_impact_kwh=energy_excess * 0.18,
            co2e_impact_kg=co2e_excess * 0.18,
            waste_impact_kg=incident.sustainability.estimated_scrap_risk_kg,
            human_exposure_minutes=12,
            contraindications=["RUL 下界小于继续运行窗口"] if incident.reliability.rul_hours_p10 < 3 else [],
        )
        constrained.score = self._overall(
            constrained.safety_score,
            constrained.resilience_score,
            constrained.sustainability_score,
            constrained.estimated_cost,
            constrained.estimated_downtime_minutes,
        )

        reacquire_safety = 94.0 if incident.diagnosis.needs_more_evidence else 42.0 if critical else 64.0 if high else 80.0
        reacquire_resilience = 90.0 if incident.diagnosis.needs_more_evidence else 38.0 if critical else 58.0 if high else 76.0
        reacquire = MaintenanceOption(
            id="acquire-more",
            title="重新采集并验证证据",
            description="校验传感器安装、时间同步、单位和工况，补充第二模态后重新运行诊断。",
            risk=RiskLevel.MEDIUM,
            estimated_downtime_minutes=15,
            estimated_cost=60.0,
            production_impact="短时检查暂停，不消耗主要备件。",
            required_parts=[],
            required_skills=["condition monitoring", "data acquisition validation"],
            rationale="当证据质量、跨模态一致性或模型置信度不足时，这是唯一允许的自动推荐。",
            score=0,
            safety_score=reacquire_safety,
            resilience_score=reacquire_resilience,
            sustainability_score=96.0,
            energy_impact_kwh=0.4,
            co2e_impact_kg=0.2,
            waste_impact_kg=0.0,
            human_exposure_minutes=8,
        )
        reacquire.score = self._overall(
            reacquire.safety_score,
            reacquire.resilience_score,
            reacquire.sustainability_score,
            reacquire.estimated_cost,
            reacquire.estimated_downtime_minutes,
        )

        options = [primary, constrained, reacquire]
        if incident.diagnosis.needs_more_evidence:
            recommended = reacquire.id
            reason = "证据冲突、质量不足或模型置信度不够，必须先补采并重新诊断。"
        else:
            feasible = [item for item in options if not item.contraindications and item.id != "acquire-more"]
            recommended = max(feasible or options, key=lambda item: item.score).id
            reason = "推荐项在人员安全、运行韧性、环境影响、成本和停机时间的受治理评分中最优，仍需人工批准。"

        return MaintenancePlan(
            recommended_option_id=recommended,
            options=options,
            schedule_window="最近安全生产切换窗口（目标 30 分钟内确认）",
            inventory_ready=inventory_ready or not parts,
            assigned_team=profile.get("team", "设备可靠性组"),
            approval_reason=reason,
            decision_dimensions={
                "human_safety": 0.34,
                "operational_resilience": 0.24,
                "sustainability": 0.18,
                "cost": 0.12,
                "downtime": 0.12,
            },
        )
