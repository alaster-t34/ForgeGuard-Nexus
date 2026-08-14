from __future__ import annotations

from dataclasses import dataclass
from math import exp

from app.domain.enums import RiskLevel
from app.domain.schemas import SensorSnapshot, VisionObservation


@dataclass(frozen=True, slots=True)
class Thresholds:
    vibration_rms_warning: float = 1.8
    vibration_rms_critical: float = 3.5
    kurtosis_warning: float = 4.5
    kurtosis_critical: float = 7.0
    crest_factor_warning: float = 4.0
    temperature_warning: float = 72.0
    temperature_critical: float = 88.0
    visual_warning: float = 0.55
    visual_critical: float = 0.82


DEFAULT_THRESHOLDS = Thresholds()


def logistic(value: float) -> float:
    return 1.0 / (1.0 + exp(-value))


def compute_anomaly_probability(
    telemetry: SensorSnapshot,
    vision: VisionObservation | None,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> float:
    vibration_term = (telemetry.vibration_rms_g - thresholds.vibration_rms_warning) * 1.2
    kurtosis_term = (telemetry.vibration_kurtosis - thresholds.kurtosis_warning) * 0.45
    temperature_term = (telemetry.temperature_c - thresholds.temperature_warning) * 0.08
    crest_term = (telemetry.crest_factor - thresholds.crest_factor_warning) * 0.35
    visual_term = 0.0 if vision is None else (vision.anomaly_score - thresholds.visual_warning) * 2.2
    quality_penalty = (1.0 - telemetry.quality) * 1.5
    raw = -1.0 + vibration_term + kurtosis_term + temperature_term + crest_term + visual_term
    return max(0.0, min(1.0, logistic(raw) * (1.0 - 0.35 * quality_penalty)))


def infer_risk(probability: float, telemetry: SensorSnapshot) -> RiskLevel:
    if probability >= 0.88 or telemetry.temperature_c >= 88 or telemetry.vibration_rms_g >= 4.0:
        return RiskLevel.CRITICAL
    if probability >= 0.68:
        return RiskLevel.HIGH
    if probability >= 0.42:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def compute_health_score(probability: float, telemetry: SensorSnapshot) -> float:
    load_factor = max(0.0, min(1.0, telemetry.load_percent / 100.0))
    thermal_penalty = max(0.0, telemetry.temperature_c - 55.0) * 0.35
    vibration_penalty = telemetry.vibration_rms_g * 5.2
    score = 100.0 - probability * 52.0 - thermal_penalty - vibration_penalty - load_factor * 3.0
    return round(max(0.0, min(100.0, score)), 1)
