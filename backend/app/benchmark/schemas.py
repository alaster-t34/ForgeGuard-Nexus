from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class PublicDatasetSpec(BaseModel):
    id: str
    name: str
    modalities: list[str]
    task: list[str]
    source_url: str
    license: str
    redistribution: Literal["included", "manifest_only", "download_by_user"]
    notes: str
    citation: str | None = None


class OpenEvalManifest(BaseModel):
    name: str
    version: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    license: str
    description: str
    sample_rate_hz: float
    signal_length: int
    labels: list[str]
    split_policy: str
    generator_commit: str
    dataset_sha256: str | None = None
    samples: int
    external_benchmarks: list[PublicDatasetSpec]


class RobustnessSliceResult(BaseModel):
    slice_name: str
    accuracy: float
    macro_f1: float
    balanced_accuracy: float
    mean_confidence: float
    abstention_rate: float
    accepted_accuracy: float | None = None


class BenchmarkModelResult(BaseModel):
    model_id: str
    family: str
    train_seconds: float
    latency_p50_ms: float
    latency_p95_ms: float
    accuracy: float
    macro_f1: float
    balanced_accuracy: float
    log_loss: float
    brier_score: float
    expected_calibration_error: float
    abstention_rate: float
    accepted_accuracy: float | None = None
    model_size_bytes: int | None = None
    robustness: list[RobustnessSliceResult]
    notes: list[str] = Field(default_factory=list)


class BenchmarkReport(BaseModel):
    id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    dataset_name: str
    dataset_version: str
    train_samples: int
    validation_samples: int
    test_samples: int
    labels: list[str]
    split_policy: str
    seed: int
    environment: dict[str, str]
    models: list[BenchmarkModelResult]
    best_model_id: str
    selection_rule: str
    artifact_paths: dict[str, str]
    limitations: list[str]


class BenchmarkRunRequest(BaseModel):
    samples_per_class: int = Field(default=56, ge=16, le=300)
    signal_length: int = Field(default=2048, ge=512, le=16384)
    sample_rate_hz: float = Field(default=12_000.0, ge=1000, le=100_000)
    seed: int = 42
    include_cnn: bool = True
    cnn_epochs: int = Field(default=8, ge=1, le=50)
    confidence_threshold: float = Field(default=0.62, ge=0.0, le=1.0)


class FaultInjectionRequest(BaseModel):
    physical_fault: str = "normal"
    sensor_fault: str = "none"
    sample_rate_hz: float = Field(default=12_000.0, ge=1000, le=100_000)
    duration_seconds: float = Field(default=0.25, ge=0.05, le=5.0)
    rpm: float = Field(default=1800.0, ge=60, le=30_000)
    load_percent: float = Field(default=70.0, ge=0, le=150)
    physical_severity: float = Field(default=0.55, ge=0, le=1)
    sensor_severity: float = Field(default=0.5, ge=0, le=1)
    seed: int = 0


class FaultInjectionResult(BaseModel):
    samples: list[float]
    features: dict[str, float]
    metadata: dict[str, Any]


class WorkflowFaultRequest(BaseModel):
    tool_name: str
    mode: Literal["error", "timeout", "empty_result"]
    remaining_calls: int = Field(default=1, ge=1, le=100)
    delay_seconds: float = Field(default=0.05, ge=0, le=30)
    message: str = Field(default="Injected workflow fault", min_length=3, max_length=500)


class FaultCampaignCase(BaseModel):
    case_id: str
    physical_fault: str
    sensor_fault: str
    predicted_label: str
    confidence: float
    quality_score: float
    warnings: list[str]
    classification_correct: bool
    safety_gate_triggered: bool


class WorkflowFaultCase(BaseModel):
    mode: str
    tool_name: str
    recorded_status: str
    error: str | None = None
    safely_contained: bool


class FaultCampaignReport(BaseModel):
    id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    signal_cases: list[FaultCampaignCase]
    workflow_cases: list[WorkflowFaultCase]
    clean_fault_accuracy: float
    corrupted_signal_safe_response_rate: float
    workflow_containment_rate: float
    artifact_paths: dict[str, str]
    limitations: list[str]
