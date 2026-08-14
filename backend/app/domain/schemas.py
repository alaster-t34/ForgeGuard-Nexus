from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.enums import (
    AgentName,
    ApprovalDecision,
    AssetStatus,
    EdgeNodeStatus,
    EvidenceKind,
    IncidentStatus,
    RiskLevel,
    ToolRisk,
    WorkOrderStatus,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, use_enum_values=False)


class Asset(StrictModel):
    id: str
    name: str
    asset_class: str
    line: str
    location: str
    status: AssetStatus = AssetStatus.HEALTHY
    health_score: float = Field(ge=0, le=100)
    estimated_rul_hours: float | None = Field(default=None, ge=0)
    criticality: RiskLevel = RiskLevel.MEDIUM
    tags: list[str] = Field(default_factory=list)
    last_seen_at: datetime = Field(default_factory=utc_now)
    manufacturer: str | None = None
    model: str | None = None
    serial_number: str | None = None
    owner_team: str = "Reliability Engineering"
    safety_class: str = "standard"
    energy_baseline_kw: float = Field(default=8.0, ge=0)
    carbon_factor_kg_per_kwh: float = Field(default=0.55, ge=0)
    mtbf_hours: float = Field(default=6000.0, ge=0)


class SensorSnapshot(StrictModel):
    timestamp: datetime = Field(default_factory=utc_now)
    vibration_rms_g: float = Field(ge=0)
    vibration_kurtosis: float = Field(ge=0)
    crest_factor: float = Field(ge=0)
    temperature_c: float
    rotational_speed_rpm: float = Field(ge=0)
    load_percent: float = Field(ge=0, le=150)
    acoustic_rms_db: float | None = Field(default=None, ge=0)
    current_rms_a: float | None = Field(default=None, ge=0)
    energy_kw: float | None = Field(default=None, ge=0)
    ambient_temperature_c: float | None = None
    quality: float = Field(default=1.0, ge=0, le=1)


class VisionObservation(StrictModel):
    image_id: str
    anomaly_score: float = Field(ge=0, le=1)
    class_name: str | None = None
    confidence: float = Field(default=0, ge=0, le=1)
    region: tuple[float, float, float, float] | None = None
    heatmap_uri: str | None = None
    source: str = "simulator"


class IncidentInput(StrictModel):
    asset_id: str
    summary: str
    telemetry: SensorSnapshot
    vision: VisionObservation | None = None
    operator_note: str | None = None
    scenario_key: str | None = None
    scenario_category: str | None = None
    simulation_only: bool = False
    requested_action: Literal["diagnose", "plan_maintenance", "full_loop"] = "full_loop"


class EvidenceItem(StrictModel):
    id: str = Field(default_factory=lambda: f"ev_{uuid4().hex[:12]}")
    kind: EvidenceKind
    source: str
    title: str
    value: Any
    unit: str | None = None
    confidence: float = Field(default=1.0, ge=0, le=1)
    citation: str | None = None
    observed_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolCallRecord(StrictModel):
    id: str = Field(default_factory=lambda: f"tool_{uuid4().hex[:12]}")
    tool_name: str
    agent: AgentName
    risk: ToolRisk
    arguments: dict[str, Any]
    status: Literal["started", "succeeded", "failed", "blocked"]
    result_summary: str | None = None
    error: str | None = None
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None


class TraceStep(StrictModel):
    id: str = Field(default_factory=lambda: f"step_{uuid4().hex[:12]}")
    agent: AgentName
    action: str
    status: Literal["queued", "running", "completed", "failed", "waiting"]
    rationale: str
    evidence_ids: list[str] = Field(default_factory=list)
    tool_call_ids: list[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None


class DiagnosticHypothesis(StrictModel):
    fault_mode: str
    probability: float = Field(ge=0, le=1)
    severity: RiskLevel
    rationale: str
    evidence_ids: list[str]
    contradictions: list[str] = Field(default_factory=list)


class DiagnosisResult(StrictModel):
    primary: DiagnosticHypothesis
    alternatives: list[DiagnosticHypothesis] = Field(default_factory=list)
    data_quality: float = Field(ge=0, le=1)
    needs_more_evidence: bool
    requested_evidence: list[str] = Field(default_factory=list)


class ReliabilityResult(StrictModel):
    health_score: float = Field(ge=0, le=100)
    rul_hours_p50: float = Field(ge=0)
    rul_hours_p10: float = Field(ge=0)
    rul_hours_p90: float = Field(ge=0)
    continuation_risk: RiskLevel
    confidence: float = Field(ge=0, le=1)
    limiting_factors: list[str] = Field(default_factory=list)
    degradation_rate_per_day: float = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_quantile_order(self):
        if not self.rul_hours_p10 <= self.rul_hours_p50 <= self.rul_hours_p90:
            raise ValueError("RUL quantiles must satisfy p10 <= p50 <= p90")
        return self


class SafetyAssessment(StrictModel):
    score: float = Field(ge=0, le=100)
    risk: RiskLevel
    hazards: list[str] = Field(default_factory=list)
    required_controls: list[str] = Field(default_factory=list)
    required_ppe: list[str] = Field(default_factory=list)
    loto_required: bool = True
    minimum_technicians: int = Field(default=1, ge=1)
    required_certifications: list[str] = Field(default_factory=list)
    approval_required: bool = True
    rationale: str


class SustainabilityAssessment(StrictModel):
    score: float = Field(ge=0, le=100)
    baseline_energy_kw: float = Field(ge=0)
    abnormal_energy_kw: float = Field(ge=0)
    estimated_excess_energy_kwh_per_day: float
    estimated_excess_co2e_kg_per_day: float
    estimated_scrap_risk_kg: float = Field(ge=0)
    repair_avoided_waste_kg: float = Field(ge=0)
    assumptions: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class ResilienceAssessment(StrictModel):
    score: float = Field(ge=0, le=100)
    recovery_time_minutes: int = Field(ge=0)
    spare_part_risk: RiskLevel
    workforce_readiness: float = Field(ge=0, le=1)
    production_buffer_minutes: int = Field(ge=0)
    offline_capable: bool
    fallback_plan: str
    constraints: list[str] = Field(default_factory=list)


class MaintenanceOption(StrictModel):
    id: str
    title: str
    description: str
    risk: RiskLevel
    estimated_downtime_minutes: int = Field(ge=0)
    estimated_cost: float = Field(ge=0)
    production_impact: str
    required_parts: list[str]
    required_skills: list[str]
    rationale: str
    approval_required: bool = True
    score: float = Field(ge=0, le=100)
    safety_score: float = Field(default=50, ge=0, le=100)
    resilience_score: float = Field(default=50, ge=0, le=100)
    sustainability_score: float = Field(default=50, ge=0, le=100)
    energy_impact_kwh: float = 0
    co2e_impact_kg: float = 0
    waste_impact_kg: float = 0
    human_exposure_minutes: int = Field(default=0, ge=0)
    contraindications: list[str] = Field(default_factory=list)


class MaintenancePlan(StrictModel):
    recommended_option_id: str
    options: list[MaintenanceOption]
    schedule_window: str
    inventory_ready: bool
    assigned_team: str
    approval_reason: str
    decision_dimensions: dict[str, float] = Field(default_factory=dict)


class HumanApproval(StrictModel):
    decision: ApprovalDecision
    option_id: str
    approved_by: str
    role: str = "authorized operator"
    comment: str | None = None
    decided_at: datetime = Field(default_factory=utc_now)


class WorkOrder(StrictModel):
    id: str = Field(default_factory=lambda: f"WO-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}")
    incident_id: str
    asset_id: str
    title: str
    status: WorkOrderStatus = WorkOrderStatus.DRAFT
    priority: RiskLevel
    selected_option_id: str
    assignee_team: str
    required_parts: list[str]
    checklist: list[str]
    mobile_steps: list[str] = Field(default_factory=list)
    safety_controls: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    approved_at: datetime | None = None
    completed_at: datetime | None = None


class VerificationResult(StrictModel):
    passed: bool
    verdict: Literal["close", "monitor", "reopen", "escalate"]
    pre_health_score: float = Field(ge=0, le=100)
    post_health_score: float = Field(ge=0, le=100)
    improvement_percent: float
    remaining_anomalies: list[str]
    rationale: str
    vibration_reduction_percent: float = 0
    energy_reduction_percent: float = 0
    evidence_package_id: str = Field(default_factory=lambda: f"PKG-{uuid4().hex[:10].upper()}")


class SearchCitation(StrictModel):
    title: str
    url: str
    snippet: str
    source: str
    published_at: str | None = None


class SearchResult(StrictModel):
    query: str
    citations: list[SearchCitation]
    provider: str
    policy_notes: list[str] = Field(default_factory=list)


class IncidentRecord(StrictModel):
    id: str = Field(default_factory=lambda: f"INC-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}")
    asset_id: str
    summary: str
    status: IncidentStatus = IncidentStatus.NEW
    risk: RiskLevel = RiskLevel.MEDIUM
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    input: IncidentInput
    evidence: list[EvidenceItem] = Field(default_factory=list)
    diagnosis: DiagnosisResult | None = None
    reliability: ReliabilityResult | None = None
    safety: SafetyAssessment | None = None
    sustainability: SustainabilityAssessment | None = None
    resilience: ResilienceAssessment | None = None
    plan: MaintenancePlan | None = None
    approval: HumanApproval | None = None
    work_order: WorkOrder | None = None
    verification: VerificationResult | None = None
    trace: list[TraceStep] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    audit_notes: list[str] = Field(default_factory=list)


class ApprovalRequest(StrictModel):
    option_id: str
    approved_by: str = Field(min_length=2)
    role: str = "authorized operator"
    comment: str | None = None
    decision: ApprovalDecision = ApprovalDecision.APPROVE


class VerificationRequest(StrictModel):
    telemetry: SensorSnapshot
    vision: VisionObservation | None = None
    technician_note: str | None = None


class DemoScenarioRequest(StrictModel):
    scenario: str = Field(default="outer_race_spall", min_length=2, max_length=80)
    asset_id: str = "FG-BRG-001"


class InventoryItem(StrictModel):
    id: str
    name: str
    quantity_on_hand: int = Field(ge=0)
    quantity_reserved: int = Field(default=0, ge=0)
    reorder_point: int = Field(default=2, ge=0)
    supplier: str
    lead_time_days: int = Field(ge=0)
    unit_cost: float = Field(ge=0)
    circularity: Literal["new", "remanufactured", "recyclable", "consumable"] = "new"

    @property
    def available(self) -> int:
        return max(0, self.quantity_on_hand - self.quantity_reserved)


class ProductionOrder(StrictModel):
    id: str
    line: str
    product: str
    quantity: int = Field(ge=0)
    completed_quantity: int = Field(default=0, ge=0)
    due_at: datetime
    safe_transition_minutes: int = Field(ge=0)
    downstream_buffer_minutes: int = Field(ge=0)
    priority: RiskLevel = RiskLevel.MEDIUM
    status: Literal["planned", "running", "paused", "completed"] = "running"


class TechnicianProfile(StrictModel):
    id: str
    name: str
    team: str
    skills: list[str]
    certifications: list[str]
    shift: str
    available: bool = True
    fatigue_risk: RiskLevel = RiskLevel.LOW
    active_work_orders: int = Field(default=0, ge=0)


class AuditEvent(StrictModel):
    id: str = Field(default_factory=lambda: f"AUD-{uuid4().hex[:10].upper()}")
    category: str
    actor: str
    action: str
    object_id: str
    detail: str
    severity: RiskLevel = RiskLevel.LOW
    timestamp: datetime = Field(default_factory=utc_now)


class AgentRuntimeStatus(StrictModel):
    agent: AgentName
    status: Literal["idle", "running", "waiting", "degraded", "offline"]
    current_task: str | None = None
    last_run_at: datetime | None = None
    success_rate: float = Field(default=1.0, ge=0, le=1)
    average_latency_ms: float = Field(default=0, ge=0)


class EdgeNodeSummary(StrictModel):
    id: str
    name: str
    status: EdgeNodeStatus
    platform: str
    modalities: list[str]
    last_seen_at: datetime
    cpu_percent: float = Field(default=0, ge=0, le=100)
    memory_percent: float = Field(default=0, ge=0, le=100)
    gpu_percent: float | None = Field(default=None, ge=0, le=100)
    power_w: float | None = Field(default=None, ge=0)


class DashboardSummary(StrictModel):
    total_assets: int
    healthy_assets: int
    warning_assets: int
    critical_assets: int
    open_incidents: int
    pending_approvals: int
    active_work_orders: int
    edge_nodes_online: int
    fleet_health_score: float = Field(ge=0, le=100)
    resilience_index: float = Field(ge=0, le=100)
    human_safety_index: float = Field(ge=0, le=100)
    sustainability_index: float = Field(ge=0, le=100)
    avoided_downtime_hours: float = Field(ge=0)
    avoided_waste_kg: float = Field(ge=0)
    energy_saved_kwh: float = Field(ge=0)


class SustainabilitySummary(StrictModel):
    energy_today_kwh: float
    excess_energy_kwh: float
    avoided_energy_kwh: float
    avoided_co2e_kg: float
    avoided_waste_kg: float
    assets_with_energy_drift: int
    circular_parts_used: int


class HealthResponse(StrictModel):
    status: str
    app: str
    version: str

class AssistantRequest(StrictModel):
    query: str = Field(min_length=2, max_length=2000)
    asset_id: str | None = None
    incident_id: str | None = None
    language: Literal["zh-CN", "en"] = "zh-CN"


class AssistantResponse(StrictModel):
    answer: str
    reasoning_mode: str
    recommended_actions: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    citations: list[SearchCitation] = Field(default_factory=list)
    safety_notice: str
