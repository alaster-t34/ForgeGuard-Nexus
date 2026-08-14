from __future__ import annotations

import numpy as np

from forgeguard_edge.contracts import RawFrame


class StatisticalVibrationFeatures:
    async def infer(self, frame: RawFrame) -> dict[str, float]:
        if frame.modality != "vibration" or not isinstance(frame.payload, list):
            raise ValueError("A numeric vibration frame is required")
        signal = np.asarray(frame.payload, dtype=np.float64)
        signal = signal - np.mean(signal)
        rms = float(np.sqrt(np.mean(signal**2)))
        std = float(np.std(signal))
        peak = float(np.max(np.abs(signal)))
        kurtosis = float(np.mean((signal / max(std, 1e-12)) ** 4))
        crest = peak / max(rms, 1e-12)
        return {
            "rms": rms,
            "peak": peak,
            "kurtosis": kurtosis,
            "crest_factor": crest,
        }
