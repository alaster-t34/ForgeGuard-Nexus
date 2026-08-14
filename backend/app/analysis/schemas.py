from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LiveSessionCreate(BaseModel):
    asset_id: str
    node_id: str | None = None
    name: str = "实时振动监测"
    source: Literal["external", "simulator"] = "simulator"
    sample_rate_hz: float = Field(default=12000.0, ge=64, le=1_000_000)
    rpm: float = Field(default=1800.0, ge=0, le=100_000)
    load_percent: float = Field(default=70.0, ge=0, le=200)
    open_incident: bool = True


class LiveFrameInput(BaseModel):
    samples: list[float] = Field(min_length=64, max_length=262_144)
    rpm: float | None = Field(default=None, ge=0, le=100_000)
    load_percent: float | None = Field(default=None, ge=0, le=200)
    temperature_c: float | None = Field(default=None, ge=-100, le=500)
    timestamp: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LiveSimulationInput(BaseModel):
    fault_mode: Literal[
        "normal",
        "imbalance",
        "misalignment",
        "outer_race",
        "inner_race",
        "ball",
        "lubrication",
        "looseness",
    ] = "normal"
    sensor_fault: Literal[
        "none",
        "low_snr",
        "dropout",
        "drift",
        "clipping",
        "quantization",
        "speed_shift",
        "impulse_interference",
    ] = "none"
    severity: float = Field(default=0.55, ge=0, le=1)
    duration_seconds: float = Field(default=0.5, ge=0.05, le=10)


class LiveHistoryPoint(BaseModel):
    sequence: int
    timestamp: datetime
    accepted: bool
    quality_score: float
    predicted_class: str
    confidence: float
    anomaly_probability: float
    rms: float
    kurtosis: float
    incident_id: str | None = None


class LiveSessionState(BaseModel):
    id: str
    node_id: str
    asset_id: str
    name: str
    source: Literal["external", "simulator"]
    status: Literal["running", "stopped", "degraded"] = "running"
    sample_rate_hz: float
    rpm: float
    load_percent: float
    open_incident: bool
    started_at: datetime = Field(default_factory=utc_now)
    stopped_at: datetime | None = None
    total_frames: int = 0
    accepted_frames: int = 0
    rejected_frames: int = 0
    incident_id: str | None = None
    last_analysis: dict[str, Any] | None = None
    waveform_preview: list[float] = Field(default_factory=list)
    history: list[LiveHistoryPoint] = Field(default_factory=list)


class CsvWindowResult(BaseModel):
    sequence: int
    start_sample: int
    end_sample: int
    timestamp_seconds: float
    accepted: bool
    quality_score: float
    predicted_class: str
    confidence: float
    anomaly_probability: float
    rms: float
    kurtosis: float
    warnings: list[str] = Field(default_factory=list)


class CsvAnalysisReport(BaseModel):
    id: str
    file_name: str
    asset_id: str
    signal_column: str
    sample_rate_hz: float
    rpm: float
    load_percent: float
    total_samples: int
    duration_seconds: float
    window_size: int
    hop_size: int
    total_windows: int
    accepted_windows: int
    rejected_windows: int
    dominant_class: str
    class_distribution: dict[str, int]
    average_quality: float
    maximum_anomaly_probability: float
    incident_id: str | None = None
    generated_at: datetime = Field(default_factory=utc_now)
    waveform_preview: list[float] = Field(default_factory=list)
    windows: list[CsvWindowResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
