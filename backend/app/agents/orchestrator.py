from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.agents.diagnosis import DiagnosisAgent
from app.agents.perception import PerceptionAgent
from app.agents.planner import MaintenancePlannerAgent
from app.agents.quality import EvidenceQualityAgent
from app.agents.reliability import ReliabilityAgent
from app.agents.resilience import ResilienceAgent
from app.agents.safety import HumanSafetyAgent
from app.agents.sustainability import SustainabilityAgent
from app.agents.verification import VerificationAgent
from app.domain.enums import (
    AgentName,
    ApprovalDecision,
    AssetStatus,
    EvidenceKind,
    IncidentStatus,
    RiskLevel,
    WorkOrderStatus,
)
from app.domain.schemas import (
    ApprovalRequest,
    AuditEvent,
    EvidenceItem,
    HumanApproval,
    IncidentInput,
    IncidentRecord,
    TraceStep,
    VerificationRequest,
    WorkOrder,
)
from app.services.tools import ToolRegistry


class IncidentOrchestrator:
    """Governed multi-agent state machine for Industrial 5.0 maintenance.

    Perception and ML output never bypass evidence quality, safety assessment or
    human approval. Every state transition is auditable and deterministic when
    no local reasoning model is configured.
    """

    def __init__(self, store: Any, tools: ToolRegistry) -> None:
        self.store = store
        self.tools = tools
        self.quality = EvidenceQualityAgent()
        self.perception = PerceptionAgent()
        self.diagnosis = DiagnosisAgent()
        self.reliability = ReliabilityAgent()
        self.safety = HumanSafetyAgent()
        self.sustainability = SustainabilityAgent()
        self.resilience = ResilienceAgent()
        self.planner = MaintenancePlannerAgent()
        self.verification = VerificationAgent()

    async def _call_tool(
        self,
        incident: IncidentRecord,
        name: str,
        agent: AgentName,
        arguments: dict[str, Any],
        *,
        approved: bool = False,
        evidence_kind: EvidenceKind = EvidenceKind.TOOL_RESULT,
        title: str | None = None,
    ) -> Any | None:
        call, result = await self.tools.call(
            name,
            agent=agent,
            arguments=arguments,
            approved=approved,
        )
        incident.tool_calls.append(call)
        if result is not None:
            incident.evidence.append(
                EvidenceItem(
                    kind=evidence_kind,
                    source=name,
                    title=title or name,
                    value=result,
                    confidence=1.0,
                )
            )
        return result

    async def create_and_analyze(self, payload: IncidentInput) -> IncidentRecord:
        asset = self.store.get_asset(payload.asset_id)
        if asset is None:
            raise KeyError(f"Unknown asset: {payload.asset_id}")
        incident = IncidentRecord(asset_id=payload.asset_id, summary=payload.summary, input=payload)
        incident.status = IncidentStatus.ANALYZING

        await self._call_tool(
            incident,
            "asset.query",
            AgentName.COORDINATOR,
            {"asset_id": payload.asset_id},
            evidence_kind=EvidenceKind.TOOL_RESULT,
            title="Asset master data",
        )

        quality_items, quality_step = await self.quality.run(incident)
        incident.evidence.extend(quality_items)
        quality_step.evidence_ids = [item.id for item in quality_items]
        incident.trace.append(quality_step)

        perception_items, perception_step = await self.perception.run(incident)
        incident.evidence.extend(perception_items)
        perception_step.evidence_ids = [item.id for item in perception_items]
        incident.trace.append(perception_step)

        await self._call_tool(
            incident,
            "knowledge.failure_modes",
            AgentName.KNOWLEDGE,
            {"query": f"{payload.summary} bearing failure safety maintenance", "limit": 5},
            evidence_kind=EvidenceKind.KNOWLEDGE,
            title="Retrieved FMEA, manuals and safety guidance",
        )

        diagnosis, step = await self.diagnosis.run(incident)
        incident.diagnosis = diagnosis
        step.evidence_ids = diagnosis.primary.evidence_ids
        incident.trace.append(step)

        reliability, step = await self.reliability.run(incident)
        incident.reliability = reliability
        incident.risk = reliability.continuation_risk
        incident.trace.append(step)

        await self._call_tool(
            incident,
            "production.context",
            AgentName.RESILIENCE,
            {"asset_id": payload.asset_id},
            evidence_kind=EvidenceKind.PRODUCTION,
            title="Production schedule and buffer",
        )
        await self._call_tool(
            incident,
            "inventory.query",
            AgentName.RESILIENCE,
            {
                "part_numbers": [
                    "6205-2RS-C3 bearing",
                    "approved grease cartridge",
                    "locking washer",
                ]
            },
            evidence_kind=EvidenceKind.INVENTORY,
            title="Spare-parts availability",
        )
        await self._call_tool(
            incident,
            "workforce.query",
            AgentName.SAFETY,
            {"skills": ["mechanical maintenance", "LOTO authorization"]},
            evidence_kind=EvidenceKind.SAFETY,
            title="Qualified workforce availability",
        )

        safety, step = await self.safety.run(incident)
        incident.safety = safety
        incident.trace.append(step)
        incident.evidence.append(
            EvidenceItem(
                kind=EvidenceKind.SAFETY,
                source="human-safety-agent",
                title="Human safety assessment",
                value=safety.model_dump(mode="json"),
                confidence=1.0,
            )
        )

        sustainability, step = await self.sustainability.run(incident)
        incident.sustainability = sustainability
        incident.trace.append(step)
        incident.evidence.append(
            EvidenceItem(
                kind=EvidenceKind.SUSTAINABILITY,
                source="sustainability-agent",
                title="Energy, carbon and waste assessment",
                value=sustainability.model_dump(mode="json"),
                confidence=sustainability.confidence,
            )
        )

        resilience, step = await self.resilience.run(incident)
        incident.resilience = resilience
        incident.trace.append(step)

        plan, step = await self.planner.run(incident)
        incident.plan = plan
        incident.trace.append(step)
        incident.status = IncidentStatus.AWAITING_APPROVAL
        incident.updated_at = datetime.now(timezone.utc)
        incident.audit_notes.extend(
            [
                "Decision support only: the platform cannot directly control production equipment.",
                "Any production or maintenance action requires authorized human approval.",
                "Data, model, tool and policy evidence are retained for later review.",
            ]
        )

        asset.status = AssetStatus.CRITICAL if incident.risk == RiskLevel.CRITICAL else AssetStatus.WARNING
        asset.health_score = reliability.health_score
        asset.estimated_rul_hours = reliability.rul_hours_p50
        asset.last_seen_at = datetime.now(timezone.utc)
        self.store.upsert_asset(asset)
        saved = self.store.save_incident(incident)
        self.store.append_audit(
            AuditEvent(
                category="incident",
                actor="ForgeGuard Coordinator",
                action="analysis_completed",
                object_id=incident.id,
                detail=f"Incident reached {incident.status.value}; recommendation={plan.recommended_option_id}",
                severity=incident.risk,
            )
        )
        return saved

    async def approve(self, incident_id: str, request: ApprovalRequest) -> IncidentRecord:
        incident = self._require_incident(incident_id)
        if incident.status != IncidentStatus.AWAITING_APPROVAL or not incident.plan:
            raise ValueError("Incident is not awaiting approval")
        option = next((item for item in incident.plan.options if item.id == request.option_id), None)
        if option is None:
            raise ValueError("Unknown maintenance option")

        incident.approval = HumanApproval(
            decision=request.decision,
            option_id=request.option_id,
            approved_by=request.approved_by,
            role=request.role,
            comment=request.comment,
        )
        incident.trace.append(
            TraceStep(
                agent=AgentName.GOVERNANCE,
                action="human_authorization_decision",
                status="completed",
                rationale=f"{request.approved_by} selected {request.decision.value} for option {option.id}.",
                finished_at=datetime.now(timezone.utc),
            )
        )

        if request.decision == ApprovalDecision.REJECT:
            incident.status = IncidentStatus.ESCALATED
            incident.audit_notes.append(f"Rejected by {request.approved_by}: {request.comment or 'No comment'}")
            self.store.save_incident(incident)
            self.store.append_audit(
                AuditEvent(
                    category="governance",
                    actor=request.approved_by,
                    action="plan_rejected",
                    object_id=incident.id,
                    detail=request.comment or "Maintenance plan rejected",
                    severity=RiskLevel.HIGH,
                )
            )
            return incident
        if request.decision == ApprovalDecision.REQUEST_EVIDENCE:
            incident.status = IncidentStatus.REOPENED
            incident.audit_notes.append("Approver requested additional evidence before intervention.")
            return self.store.save_incident(incident)

        tool_result = await self._call_tool(
            incident,
            "work_order.issue",
            AgentName.WORK_ORDER,
            {"incident_id": incident.id, "selected_option_id": option.id},
            approved=True,
            evidence_kind=EvidenceKind.WORK_ORDER,
            title="Work-order service response",
        )
        if not tool_result:
            raise RuntimeError("Work-order tool failed after approval")

        safety_controls = incident.safety.required_controls if incident.safety else []
        work_order = WorkOrder(
            incident_id=incident.id,
            asset_id=incident.asset_id,
            title=option.title,
            status=WorkOrderStatus.APPROVED,
            priority=incident.risk,
            selected_option_id=option.id,
            assignee_team=incident.plan.assigned_team,
            required_parts=option.required_parts,
            checklist=[
                "确认生产释放、作业边界和授权人员",
                "执行锁定挂牌并验证零能量状态",
                "保存维修前证据包和关键工况",
                "按批准方案执行维修、校正、清洁或补采任务",
                "记录实际故障模式、发现项、用料和测量值",
                "运行维修后多模态验证并满足关闭条件",
            ],
            mobile_steps=[
                "扫描资产身份并确认工单范围",
                "完成 PPE、LOTO 和现场风险检查",
                "拍摄维修前证据并记录工况",
                "执行批准的维修、校正、清洁或补采步骤",
                "记录扭矩、润滑、测量和检查结果",
                "采集维修后信号与图像并提交验证",
            ],
            safety_controls=safety_controls,
            approved_at=datetime.now(timezone.utc),
        )
        incident.work_order = work_order
        incident.status = IncidentStatus.IN_PROGRESS
        incident.updated_at = datetime.now(timezone.utc)
        incident.audit_notes.append(
            f"Approved by {request.approved_by} ({request.role}): {request.comment or 'No additional comment.'}"
        )
        asset = self.store.get_asset(incident.asset_id)
        if asset:
            asset.status = AssetStatus.MAINTENANCE
            self.store.upsert_asset(asset)
        saved = self.store.save_incident(incident)
        self.store.append_audit(
            AuditEvent(
                category="governance",
                actor=request.approved_by,
                action="plan_approved_and_work_order_created",
                object_id=work_order.id,
                detail=f"Incident {incident.id}; option={option.id}",
                severity=incident.risk,
            )
        )
        return saved

    async def verify(self, incident_id: str, request: VerificationRequest) -> IncidentRecord:
        incident = self._require_incident(incident_id)
        if not incident.work_order:
            raise ValueError("No work order exists for this incident")
        incident.status = IncidentStatus.VERIFYING
        incident.work_order.status = WorkOrderStatus.VERIFYING
        result = await self.verification.run(incident, request)
        incident.verification = result
        incident.trace.append(
            TraceStep(
                agent=AgentName.VERIFICATION,
                action="compare_pre_and_post_maintenance_evidence",
                status="completed",
                rationale=result.rationale,
                finished_at=datetime.now(timezone.utc),
            )
        )
        asset = self.store.get_asset(incident.asset_id)
        if result.passed:
            incident.status = IncidentStatus.RESOLVED
            incident.risk = RiskLevel.LOW
            incident.work_order.status = WorkOrderStatus.COMPLETED
            incident.work_order.completed_at = datetime.now(timezone.utc)
            if incident.reliability:
                incident.reliability.health_score = result.post_health_score
                incident.reliability.rul_hours_p10 = 620.0
                incident.reliability.rul_hours_p50 = 680.0
                incident.reliability.rul_hours_p90 = 760.0
                incident.reliability.continuation_risk = RiskLevel.LOW
                incident.reliability.confidence = max(incident.reliability.confidence, 0.96)
                incident.reliability.limiting_factors = []
            if asset:
                asset.status = AssetStatus.HEALTHY
                asset.health_score = result.post_health_score
                asset.estimated_rul_hours = 680.0
        else:
            incident.status = IncidentStatus.REOPENED
            incident.work_order.status = WorkOrderStatus.REOPENED
            if asset:
                asset.status = AssetStatus.WARNING
                asset.health_score = result.post_health_score
        incident.updated_at = datetime.now(timezone.utc)
        if asset:
            self.store.upsert_asset(asset)
        saved = self.store.save_incident(incident)
        self.store.append_audit(
            AuditEvent(
                category="verification",
                actor="Verification Agent",
                action="maintenance_verified" if result.passed else "maintenance_reopened",
                object_id=incident.id,
                detail=f"Evidence package {result.evidence_package_id}; verdict={result.verdict}",
                severity=RiskLevel.LOW if result.passed else RiskLevel.HIGH,
            )
        )
        return saved

    def _require_incident(self, incident_id: str) -> IncidentRecord:
        incident = self.store.get_incident(incident_id)
        if incident is None:
            raise KeyError(f"Unknown incident: {incident_id}")
        return incident
