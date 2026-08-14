from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class CalibrationRecord(BaseModel):
    performed_at: datetime | None = None
    method: str = "unknown"
    reference: str | None = None
    sensitivity: float | None = None
    unit: str | None = None
    certificate_uri: str | None = None

class RigSpecimen(BaseModel):
    specimen_id: str
    condition: Literal["healthy", "natural_fault", "seeded_fault", "unknown"]
    declared_fault_label: str | None = None
    provenance: str
    fault_creation_method: str | None = None
    post_test_inspection: str | None = None
    photo_uris: list[str] = Field(default_factory=list)


class RigSensorSpec(BaseModel):
    manufacturer: str
    model: str
    serial_number: str | None = None
    sensitivity: float | None = None
    sensitivity_unit: str | None = None
    measurement_range: str | None = None
    bandwidth_hz: str | None = None
    axis: str = "radial"
    position: str
    mounting: str
    calibration: CalibrationRecord = Field(default_factory=CalibrationRecord)


class RigDAQSpec(BaseModel):
    manufacturer: str
    model: str
    serial_number: str | None = None
    bit_depth: int | None = Field(default=None, ge=8, le=64)
    input_range: str | None = None
    coupling: str | None = None
    anti_alias_filter: str | None = None
    clock_source: str | None = None


class RigSafetyRecord(BaseModel):
    guard_installed: bool
    emergency_stop_verified: bool
    max_rpm: float = Field(gt=0)
    max_load_percent: float = Field(gt=0, le=200)
    approved_by: str
    approved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RigOperatingPoint(BaseModel):
    rpm: float = Field(gt=0)
    load_percent: float = Field(ge=0, le=200)
    duration_seconds: float = Field(gt=0)
    target_temperature_c: float | None = None
    repetitions: int = Field(default=1, ge=1, le=100)


class RigCampaignRegistration(BaseModel):
    campaign_id: str = Field(min_length=3, max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$")
    node_id: str
    asset_id: str
    title: str
    operator_id: str
    specimen: RigSpecimen
    sensor: RigSensorSpec
    daq: RigDAQSpec
    safety: RigSafetyRecord
    operating_points: list[RigOperatingPoint] = Field(min_length=1)
    protocol_version: str = "forgeguard-rig-v0.2"
    notes: str | None = None

    @model_validator(mode="after")
    def validate_campaign_controls(self) -> "RigCampaignRegistration":
        if not self.safety.guard_installed or not self.safety.emergency_stop_verified:
            raise ValueError("Guard and emergency-stop verification are required")
        placeholders = [
            self.operator_id,
            self.safety.approved_by,
            self.sensor.manufacturer,
            self.sensor.model,
            self.sensor.calibration.method,
            self.daq.manufacturer,
            self.daq.model,
            self.specimen.provenance,
        ]
        if any("replace" in value.lower() for value in placeholders if value):
            raise ValueError("Rig campaign contains unresolved template placeholders")
        if any(point.rpm > self.safety.max_rpm for point in self.operating_points):
            raise ValueError("An operating-point RPM exceeds the approved safety limit")
        if any(
            point.load_percent > self.safety.max_load_percent
            for point in self.operating_points
        ):
            raise ValueError("An operating-point load exceeds the approved safety limit")
        if self.specimen.condition == "seeded_fault":
            if not self.specimen.declared_fault_label or not self.specimen.fault_creation_method:
                raise ValueError(
                    "Seeded-fault specimens require a declared fault label and creation method"
                )
        return self


class RigCampaignState(RigCampaignRegistration):
    status: Literal["active", "completed", "aborted"] = "active"
    registered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    received_frames: int = 0
    rejected_frames: int = 0


class BenchNodeRegistration(BaseModel):
    node_id: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_.:-]+$")
    asset_id: str
    name: str
    transport: Literal["http", "mqtt", "opcua", "file", "serial", "custom"] = "http"
    hardware: str
    operating_system: str | None = None
    modalities: list[str] = Field(default_factory=lambda: ["vibration"])
    channels: list[str] = Field(default_factory=lambda: ["acceleration_x"])
    nominal_sample_rate_hz: float = Field(ge=1, le=1_000_000)
    sensor_position: str
    sensor_mounting: str
    calibration: CalibrationRecord = Field(default_factory=CalibrationRecord)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BenchNodeState(BenchNodeRegistration):
    status: Literal["online", "stale", "offline", "degraded"] = "online"
    registered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    received_frames: int = 0
    rejected_frames: int = 0


class BenchSignalFrame(BaseModel):
    node_id: str
    asset_id: str
    campaign_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sequence: int = Field(ge=0)
    channel: str = "acceleration_x"
    unit: str = "g"
    sample_rate_hz: float = Field(ge=1, le=1_000_000)
    samples: list[float] = Field(min_length=64, max_length=262_144)
    rpm: float = Field(default=1800.0, ge=0, le=100_000)
    load_percent: float = Field(default=50.0, ge=0, le=200)
    temperature_c: float | None = Field(default=None, ge=-100, le=500)
    metadata: dict[str, Any] = Field(default_factory=dict)
    open_incident: bool = False

    @field_validator("samples")
    @classmethod
    def finite_samples(cls, values: list[float]) -> list[float]:
        import math

        if not all(math.isfinite(value) for value in values):
            raise ValueError("All samples must be finite")
        return values


class SignalQualityReport(BaseModel):
    score: float = Field(ge=0, le=1)
    clipping_ratio: float = Field(ge=0, le=1)
    dropout_ratio: float = Field(ge=0, le=1)
    dc_offset_ratio: float = Field(ge=0)
    effective_bits_estimate: float | None = None
    warnings: list[str] = Field(default_factory=list)


class BenchFrameAnalysis(BaseModel):
    node_id: str
    asset_id: str
    sequence: int
    accepted: bool
    quality: SignalQualityReport
    features: dict[str, float]
    model_result: dict[str, Any]
    evidence_uri: str | None = None
    incident_id: str | None = None
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
