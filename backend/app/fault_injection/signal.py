from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

import numpy as np
from scipy import signal as scipy_signal


class PhysicalFault(str, Enum):
    NORMAL = "normal"
    IMBALANCE = "imbalance"
    MISALIGNMENT = "misalignment"
    OUTER_RACE = "outer_race"
    INNER_RACE = "inner_race"
    BALL = "ball"
    LUBRICATION = "lubrication"
    LOOSENESS = "looseness"


class SensorFault(str, Enum):
    NONE = "none"
    LOW_SNR = "low_snr"
    DROPOUT = "dropout"
    DRIFT = "drift"
    CLIPPING = "clipping"
    QUANTIZATION = "quantization"
    SPEED_SHIFT = "speed_shift"
    IMPULSE_INTERFERENCE = "impulse_interference"


@dataclass(slots=True, frozen=True)
class BearingGeometry:
    rolling_elements: int = 8
    ball_diameter_mm: float = 7.94
    pitch_diameter_mm: float = 39.04
    contact_angle_deg: float = 0.0

    def characteristic_frequencies(self, rpm: float) -> dict[str, float]:
        shaft = rpm / 60.0
        ratio = self.ball_diameter_mm / self.pitch_diameter_mm
        cos_angle = np.cos(np.deg2rad(self.contact_angle_deg))
        bpfo = 0.5 * self.rolling_elements * shaft * (1.0 - ratio * cos_angle)
        bpfi = 0.5 * self.rolling_elements * shaft * (1.0 + ratio * cos_angle)
        bsf = 0.5 * (self.pitch_diameter_mm / self.ball_diameter_mm) * shaft * (
            1.0 - (ratio * cos_angle) ** 2
        )
        ftf = 0.5 * shaft * (1.0 - ratio * cos_angle)
        return {"shaft": shaft, "bpfo": bpfo, "bpfi": bpfi, "bsf": bsf, "ftf": ftf}


def _resonant_impulse_train(
    length: int,
    sample_rate_hz: float,
    impact_frequency_hz: float,
    resonance_hz: float,
    decay_seconds: float,
    amplitude: float,
    rng: np.random.Generator,
) -> np.ndarray:
    signal = np.zeros(length, dtype=np.float64)
    period = max(1, int(round(sample_rate_hz / max(impact_frequency_hz, 1e-6))))
    jitter = max(1, int(period * 0.025))
    kernel_length = max(16, int(sample_rate_hz * decay_seconds * 6.0))
    kt = np.arange(kernel_length, dtype=np.float64) / sample_rate_hz
    kernel = np.exp(-kt / max(decay_seconds, 1e-5)) * np.sin(2 * np.pi * resonance_hz * kt)
    for start in range(0, length, period):
        idx = start + int(rng.integers(-jitter, jitter + 1))
        if idx < 0 or idx >= length:
            continue
        end = min(length, idx + kernel_length)
        local_amp = amplitude * float(rng.uniform(0.78, 1.22))
        signal[idx:end] += local_amp * kernel[: end - idx]
    return signal


def generate_rotating_machine_signal(
    fault: PhysicalFault | str,
    *,
    sample_rate_hz: float = 12_000.0,
    duration_seconds: float = 0.34,
    rpm: float = 1_800.0,
    load_percent: float = 70.0,
    severity: float = 0.55,
    seed: int = 0,
    geometry: BearingGeometry | None = None,
) -> np.ndarray:
    """Generate a deterministic, physics-informed vibration waveform.

    The generator is intentionally transparent: it is suitable for regression,
    robustness and workflow evaluation, but it is not presented as a substitute
    for experimental measurements from a real test rig.
    """

    fault = PhysicalFault(fault)
    severity = float(np.clip(severity, 0.0, 1.0))
    sample_rate_hz = float(sample_rate_hz)
    length = max(256, int(round(duration_seconds * sample_rate_hz)))
    rng = np.random.default_rng(seed)
    t = np.arange(length, dtype=np.float64) / sample_rate_hz
    geometry = geometry or BearingGeometry()
    frequencies = geometry.characteristic_frequencies(rpm)
    shaft = frequencies["shaft"]

    load_scale = 0.72 + 0.007 * np.clip(load_percent, 0, 120)
    base = 0.055 * np.sin(2 * np.pi * shaft * t + rng.uniform(0, 2 * np.pi))
    base += 0.018 * np.sin(2 * np.pi * 2 * shaft * t + rng.uniform(0, 2 * np.pi))
    base += 0.009 * np.sin(2 * np.pi * 3 * shaft * t + rng.uniform(0, 2 * np.pi))
    base += rng.normal(0.0, 0.018 + 0.008 * severity, size=length)

    if fault == PhysicalFault.NORMAL:
        x = base
    elif fault == PhysicalFault.IMBALANCE:
        x = base + load_scale * (0.14 + 0.42 * severity) * np.sin(
            2 * np.pi * shaft * t + rng.uniform(0, 2 * np.pi)
        )
    elif fault == PhysicalFault.MISALIGNMENT:
        x = base
        x += load_scale * (0.09 + 0.30 * severity) * np.sin(2 * np.pi * 2 * shaft * t)
        x += load_scale * (0.05 + 0.18 * severity) * np.sin(2 * np.pi * 3 * shaft * t + 0.7)
        x += 0.04 * severity * np.sign(np.sin(2 * np.pi * shaft * t))
    elif fault in {PhysicalFault.OUTER_RACE, PhysicalFault.INNER_RACE, PhysicalFault.BALL}:
        characteristic = {
            PhysicalFault.OUTER_RACE: frequencies["bpfo"],
            PhysicalFault.INNER_RACE: frequencies["bpfi"],
            PhysicalFault.BALL: frequencies["bsf"],
        }[fault]
        resonance = float(rng.uniform(1_600.0, 3_200.0))
        impacts = _resonant_impulse_train(
            length,
            sample_rate_hz,
            characteristic,
            resonance,
            decay_seconds=0.0015 + 0.0015 * (1.0 - severity),
            amplitude=0.11 + 0.65 * severity,
            rng=rng,
        )
        if fault == PhysicalFault.INNER_RACE:
            impacts *= 0.65 + 0.35 * (1.0 + np.sin(2 * np.pi * shaft * t))
        elif fault == PhysicalFault.BALL:
            impacts *= 0.62 + 0.38 * (1.0 + np.sin(2 * np.pi * frequencies["ftf"] * t))
        x = base + load_scale * impacts
    elif fault == PhysicalFault.LUBRICATION:
        white = rng.normal(0.0, 1.0, size=length)
        sos = scipy_signal.butter(4, [800, min(4_500, sample_rate_hz * 0.45)], btype="bandpass", fs=sample_rate_hz, output="sos")
        band = scipy_signal.sosfilt(sos, white)
        envelope = 0.55 + 0.45 * np.sin(2 * np.pi * 0.35 * shaft * t + 0.3) ** 2
        x = base + (0.05 + 0.22 * severity) * envelope * band
        x += (0.025 + 0.12 * severity) * rng.standard_t(df=4, size=length)
    elif fault == PhysicalFault.LOOSENESS:
        x = base.copy()
        for harmonic in range(1, 7):
            x += (0.045 + 0.11 * severity) / np.sqrt(harmonic) * np.sin(
                2 * np.pi * harmonic * shaft * t + rng.uniform(0, 2 * np.pi)
            )
        x += _resonant_impulse_train(
            length,
            sample_rate_hz,
            impact_frequency_hz=0.5 * shaft,
            resonance_hz=1_200.0,
            decay_seconds=0.003,
            amplitude=0.07 + 0.3 * severity,
            rng=rng,
        )
    else:  # pragma: no cover - StrEnum guards this branch
        raise ValueError(f"Unsupported fault: {fault}")

    x = x * float(rng.uniform(0.86, 1.16))
    x -= float(np.mean(x))
    return x.astype(np.float32)


def inject_sensor_fault(
    samples: Iterable[float] | np.ndarray,
    fault: SensorFault | str,
    *,
    severity: float = 0.5,
    seed: int = 0,
) -> np.ndarray:
    fault = SensorFault(fault)
    x = np.asarray(list(samples) if not isinstance(samples, np.ndarray) else samples, dtype=np.float64).copy()
    if x.ndim != 1 or x.size < 8:
        raise ValueError("samples must be a one-dimensional signal with at least 8 values")
    severity = float(np.clip(severity, 0.0, 1.0))
    rng = np.random.default_rng(seed)

    if fault == SensorFault.NONE:
        return x.astype(np.float32)
    if fault == SensorFault.LOW_SNR:
        rms = float(np.sqrt(np.mean(x**2)) + 1e-12)
        target_snr_db = 22.0 - 20.0 * severity
        noise_rms = rms / (10 ** (target_snr_db / 20.0))
        x += rng.normal(0.0, noise_rms, size=x.size)
    elif fault == SensorFault.DROPOUT:
        count = max(1, int(x.size * (0.02 + 0.28 * severity)))
        start = int(rng.integers(0, max(1, x.size - count)))
        x[start : start + count] = 0.0
    elif fault == SensorFault.DRIFT:
        scale = float(np.std(x) + 1e-12)
        x += np.linspace(0.0, scale * (0.2 + 2.2 * severity), x.size)
    elif fault == SensorFault.CLIPPING:
        quantile = 0.995 - 0.30 * severity
        threshold = max(1e-8, float(np.quantile(np.abs(x), max(0.55, quantile))))
        x = np.clip(x, -threshold, threshold)
    elif fault == SensorFault.QUANTIZATION:
        levels = int(round(2 ** (12 - 8 * severity)))
        levels = max(8, levels)
        min_value, max_value = float(np.min(x)), float(np.max(x))
        if max_value > min_value:
            x = np.round((x - min_value) / (max_value - min_value) * (levels - 1))
            x = x / (levels - 1) * (max_value - min_value) + min_value
    elif fault == SensorFault.SPEED_SHIFT:
        factor = 1.0 + rng.choice([-1.0, 1.0]) * (0.04 + 0.26 * severity)
        source = np.arange(x.size, dtype=np.float64)
        warped = (source * factor) % x.size
        extended_source = np.concatenate([source, source + x.size])
        extended_signal = np.concatenate([x, x])
        x = np.interp(warped, extended_source, extended_signal)
    elif fault == SensorFault.IMPULSE_INTERFERENCE:
        count = max(1, int(1 + 10 * severity))
        scale = float(np.std(x) + 1e-12)
        indices = rng.choice(x.size, size=min(count, x.size), replace=False)
        x[indices] += rng.choice([-1.0, 1.0], size=indices.size) * scale * (4.0 + 12.0 * severity)
    else:  # pragma: no cover
        raise ValueError(f"Unsupported sensor fault: {fault}")

    return x.astype(np.float32)


def fault_catalog() -> list[dict[str, str]]:
    physical_descriptions = {
        PhysicalFault.NORMAL: "Healthy rotating-machine baseline with load and speed variability.",
        PhysicalFault.IMBALANCE: "Dominant 1x shaft component with load-dependent amplitude.",
        PhysicalFault.MISALIGNMENT: "Strong 2x/3x harmonics and mild nonlinear waveform distortion.",
        PhysicalFault.OUTER_RACE: "BPFO-related periodic impacts exciting a structural resonance.",
        PhysicalFault.INNER_RACE: "BPFI impacts modulated by shaft rotation.",
        PhysicalFault.BALL: "Ball-spin impacts modulated by cage frequency.",
        PhysicalFault.LUBRICATION: "Broadband high-frequency energy and heavy-tailed friction impulses.",
        PhysicalFault.LOOSENESS: "Multiple shaft harmonics with intermittent mechanical impacts.",
    }
    sensor_descriptions = {
        SensorFault.NONE: "No sensor degradation.",
        SensorFault.LOW_SNR: "Additive noise with severity-controlled signal-to-noise ratio.",
        SensorFault.DROPOUT: "Contiguous zero-valued acquisition gap.",
        SensorFault.DRIFT: "Slow sensor bias drift across a sample window.",
        SensorFault.CLIPPING: "Analog or ADC saturation.",
        SensorFault.QUANTIZATION: "Reduced effective ADC bit depth.",
        SensorFault.SPEED_SHIFT: "Time-scale shift representing an unseen operating speed.",
        SensorFault.IMPULSE_INTERFERENCE: "Sparse electromagnetic or handling spikes.",
    }
    return [
        *[
            {"domain": "physical", "id": item.value, "description": physical_descriptions[item]}
            for item in PhysicalFault
        ],
        *[
            {"domain": "sensor", "id": item.value, "description": sensor_descriptions[item]}
            for item in SensorFault
        ],
    ]
