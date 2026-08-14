from __future__ import annotations

from collections import OrderedDict

import numpy as np
from scipy import signal as scipy_signal
from scipy import stats


def _safe_div(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if abs(denominator) > 1e-12 else 0.0


def spectral_entropy(power: np.ndarray) -> float:
    normalized = power / max(float(np.sum(power)), 1e-12)
    normalized = normalized[normalized > 1e-15]
    if normalized.size == 0:
        return 0.0
    entropy = -float(np.sum(normalized * np.log(normalized)))
    return _safe_div(entropy, np.log(len(power)))


def extract_vibration_features(samples: np.ndarray, sample_rate_hz: float) -> OrderedDict[str, float]:
    x = np.asarray(samples, dtype=np.float64).reshape(-1)
    if x.size < 64:
        raise ValueError("At least 64 samples are required")
    x = np.nan_to_num(x, copy=False)
    x_centered = x - np.mean(x)
    absolute = np.abs(x_centered)
    rms = float(np.sqrt(np.mean(x_centered**2)) + 1e-12)
    peak = float(np.max(absolute))
    mean_abs = float(np.mean(absolute) + 1e-12)
    root_amp = float(np.mean(np.sqrt(absolute + 1e-12)) ** 2 + 1e-12)

    window = scipy_signal.windows.hann(x_centered.size, sym=False)
    spectrum = np.fft.rfft(x_centered * window)
    power = np.abs(spectrum) ** 2
    freqs = np.fft.rfftfreq(x_centered.size, d=1.0 / sample_rate_hz)
    power_sum = float(np.sum(power) + 1e-12)
    centroid = float(np.sum(freqs * power) / power_sum)
    spread = float(np.sqrt(np.sum(((freqs - centroid) ** 2) * power) / power_sum))
    dominant_index = int(np.argmax(power[1:]) + 1) if power.size > 1 else 0
    dominant_frequency = float(freqs[dominant_index])
    low_band_mask = (freqs > 1.0) & (freqs <= min(180.0, sample_rate_hz / 2.0))
    if np.any(low_band_mask):
        low_indices = np.flatnonzero(low_band_mask)
        low_dominant_index = int(low_indices[int(np.argmax(power[low_band_mask]))])
        low_dominant_frequency = float(freqs[low_dominant_index])
    else:
        low_dominant_frequency = dominant_frequency

    nyquist = sample_rate_hz / 2.0
    bands = [
        (0.0, min(120.0, nyquist)),
        (120.0, min(500.0, nyquist)),
        (500.0, min(1_500.0, nyquist)),
        (1_500.0, min(3_000.0, nyquist)),
        (3_000.0, nyquist),
    ]
    band_energies: list[float] = []
    for lower, upper in bands:
        if upper <= lower:
            band_energies.append(0.0)
            continue
        mask = (freqs >= lower) & (freqs < upper)
        band_energies.append(float(np.sum(power[mask]) / power_sum))

    analytic = scipy_signal.hilbert(x_centered)
    envelope = np.abs(analytic)
    envelope_centered = envelope - np.mean(envelope)
    envelope_spectrum = np.abs(np.fft.rfft(envelope_centered * window)) ** 2
    envelope_power_sum = float(np.sum(envelope_spectrum) + 1e-12)
    envelope_centroid = float(np.sum(freqs * envelope_spectrum) / envelope_power_sum)

    diff = np.diff(x_centered)
    zero_crossings = np.mean(np.signbit(x_centered[:-1]) != np.signbit(x_centered[1:]))
    clipping_threshold = max(1e-8, float(np.max(absolute)) * 0.999)
    clipping_ratio = float(np.mean(absolute >= clipping_threshold))
    dropout_ratio = float(np.mean(np.isclose(x, 0.0, atol=max(1e-8, np.std(x) * 1e-4))))

    values = OrderedDict(
        mean=float(np.mean(x)),
        std=float(np.std(x_centered)),
        rms=rms,
        peak=peak,
        peak_to_peak=float(np.ptp(x)),
        skewness=float(np.nan_to_num(stats.skew(x_centered, bias=False))),
        kurtosis=float(np.nan_to_num(stats.kurtosis(x_centered, fisher=False, bias=False))),
        crest_factor=_safe_div(peak, rms),
        shape_factor=_safe_div(rms, mean_abs),
        impulse_factor=_safe_div(peak, mean_abs),
        clearance_factor=_safe_div(peak, root_amp),
        zero_crossing_rate=float(zero_crossings),
        derivative_rms=float(np.sqrt(np.mean(diff**2)) if diff.size else 0.0),
        spectral_centroid_hz=centroid,
        spectral_spread_hz=spread,
        spectral_entropy=spectral_entropy(power),
        dominant_frequency_hz=dominant_frequency,
        low_band_dominant_frequency_hz=low_dominant_frequency,
        envelope_kurtosis=float(np.nan_to_num(stats.kurtosis(envelope_centered, fisher=False, bias=False))),
        envelope_spectral_centroid_hz=envelope_centroid,
        band_energy_0_120=band_energies[0],
        band_energy_120_500=band_energies[1],
        band_energy_500_1500=band_energies[2],
        band_energy_1500_3000=band_energies[3],
        band_energy_3000_nyquist=band_energies[4],
        clipping_ratio=clipping_ratio,
        dropout_ratio=dropout_ratio,
    )
    return values


def feature_matrix(signals: np.ndarray, sample_rate_hz: float) -> tuple[np.ndarray, list[str]]:
    rows = [extract_vibration_features(signal, sample_rate_hz) for signal in signals]
    names = list(rows[0].keys())
    matrix = np.asarray([[row[name] for name in names] for row in rows], dtype=np.float64)
    return matrix, names
