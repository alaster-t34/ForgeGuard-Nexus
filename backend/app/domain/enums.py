from enum import Enum


class AssetStatus(str, Enum):
    HEALTHY = "healthy"
    WATCH = "watch"
    WARNING = "warning"
    CRITICAL = "critical"
    MAINTENANCE = "maintenance"
    DEGRADED = "degraded"
    OFFLINE = "offline"


class IncidentStatus(str, Enum):
    NEW = "new"
    ANALYZING = "analyzing"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    VERIFYING = "verifying"
    RESOLVED = "resolved"
    REOPENED = "reopened"
    ESCALATED = "escalated"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EvidenceKind(str, Enum):
    TELEMETRY = "telemetry"
    VISION = "vision"
    SIGNAL_FEATURE = "signal_feature"
    KNOWLEDGE = "knowledge"
    WORK_ORDER = "work_order"
    USER_INPUT = "user_input"
    MODEL_OUTPUT = "model_output"
    TOOL_RESULT = "tool_result"
    SAFETY = "safety"
    SUSTAINABILITY = "sustainability"
    PRODUCTION = "production"
    INVENTORY = "inventory"
    HUMAN_APPROVAL = "human_approval"
    EDGE_RUNTIME = "edge_runtime"


class WorkOrderStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    REOPENED = "reopened"
    CANCELLED = "cancelled"


class AgentName(str, Enum):
    COORDINATOR = "coordinator"
    EVIDENCE_QUALITY = "evidence_quality"
    PERCEPTION = "perception"
    KNOWLEDGE = "knowledge"
    DIAGNOSIS = "diagnosis"
    RELIABILITY = "reliability"
    SAFETY = "safety"
    SUSTAINABILITY = "sustainability"
    RESILIENCE = "resilience"
    PLANNER = "planner"
    WORK_ORDER = "work_order"
    VERIFICATION = "verification"
    GOVERNANCE = "governance"


class ToolRisk(str, Enum):
    READ_ONLY = "read_only"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ApprovalDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_EVIDENCE = "request_evidence"


class EdgeNodeStatus(str, Enum):
    ONLINE = "online"
    DEGRADED = "degraded"
    STALE = "stale"
    OFFLINE = "offline"
