from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

import numpy as np

from app.benchmark.features import extract_vibration_features
from app.bench.schemas import (
    BenchFrameAnalysis,
    BenchNodeRegistration,
    BenchNodeState,
    BenchSignalFrame,
    RigCampaignRegistration,
    RigCampaignState,
    SignalQualityReport,
)
from app.domain.schemas import IncidentInput, SensorSnapshot
from app.models.registry import ModelRegistry


class BenchGateway:
    def __init__(self, models: ModelRegistry, evidence_dir: Path) -> None:
        self.models = models
        self.evidence_dir = evidence_dir
        self._nodes: dict[str, BenchNodeState] = {}
        self._campaigns: dict[str, RigCampaignState] = {}
        self._last_sequence: dict[str, int] = {}
        self._frame_hashes: dict[tuple[str, int], str] = {}
        self._analysis_cache: dict[tuple[str, int], BenchFrameAnalysis] = {}
        self._lock = RLock()

    def register(self, registration: BenchNodeRegistration) -> BenchNodeState:
        with self._lock:
            existing = self._nodes.get(registration.node_id)
            state = BenchNodeState(
                **registration.model_dump(),
                registered_at=existing.registered_at if existing else datetime.now(timezone.utc),
                last_seen_at=datetime.now(timezone.utc),
                received_frames=existing.received_frames if existing else 0,
                rejected_frames=existing.rejected_frames if existing else 0,
            )
            self._nodes[registration.node_id] = state
            return deepcopy(state)

    def register_campaign(self, registration: RigCampaignRegistration) -> RigCampaignState:
        with self._lock:
            node = self._nodes.get(registration.node_id)
            if node is None:
                raise KeyError(f"Unknown bench node: {registration.node_id}")
            if node.asset_id != registration.asset_id:
                raise ValueError("Campaign asset_id does not match the registered node")
            existing = self._campaigns.get(registration.campaign_id)
            if existing is not None and existing.status == "active":
                raise ValueError(f"Campaign is already active: {registration.campaign_id}")
            state = RigCampaignState(**registration.model_dump())
            self._campaigns[registration.campaign_id] = state
            return deepcopy(state)

    def list_campaigns(self) -> list[RigCampaignState]:
        with self._lock:
            return sorted(
                (deepcopy(item) for item in self._campaigns.values()),
                key=lambda item: item.registered_at,
                reverse=True,
            )

    def list_nodes(self) -> list[BenchNodeState]:
        with self._lock:
            now = datetime.now(timezone.utc)
            items: list[BenchNodeState] = []
            for node in self._nodes.values():
                age = (now - node.last_seen_at).total_seconds()
                copy = deepcopy(node)
                if age > 120:
                    copy.status = "offline"
                elif age > 30:
                    copy.status = "stale"
                items.append(copy)
            return sorted(items, key=lambda item: item.node_id)

    async def ingest(self, frame: BenchSignalFrame) -> BenchFrameAnalysis:
        frame_hash = self._frame_hash(frame)
        cache_key = (frame.node_id, frame.sequence)
        previous: int | None = None
        with self._lock:
            node = self._nodes.get(frame.node_id)
            if node is None:
                raise KeyError(f"Unknown bench node: {frame.node_id}")
            if node.asset_id != frame.asset_id:
                node.rejected_frames += 1
                raise ValueError("Frame asset_id does not match registered node")
            campaign = None
            if frame.campaign_id is not None:
                campaign = self._campaigns.get(frame.campaign_id)
                if campaign is None:
                    node.rejected_frames += 1
                    raise ValueError(f"Unknown rig campaign: {frame.campaign_id}")
                if campaign.status != "active":
                    node.rejected_frames += 1
                    campaign.rejected_frames += 1
                    raise ValueError(f"Rig campaign is not active: {frame.campaign_id}")
                if campaign.node_id != frame.node_id or campaign.asset_id != frame.asset_id:
                    node.rejected_frames += 1
                    campaign.rejected_frames += 1
                    raise ValueError("Frame node/asset does not match the rig campaign")
            previous = self._last_sequence.get(frame.node_id)
            if previous is not None and frame.sequence <= previous:
                cached_hash = self._frame_hashes.get(cache_key)
                cached_analysis = self._analysis_cache.get(cache_key)
                if (
                    frame.sequence == previous
                    and cached_hash == frame_hash
                    and cached_analysis is not None
                ):
                    return deepcopy(cached_analysis)
                node.rejected_frames += 1
                if frame.sequence == previous and cached_hash is None:
                    raise ValueError("Frame sequence is already being processed; retry later")
                if frame.sequence == previous:
                    raise ValueError("Duplicate frame sequence has different content")
                raise ValueError("Frame sequence is stale; sequence must increase monotonically")
            relative_rate_error = abs(frame.sample_rate_hz - node.nominal_sample_rate_hz) / max(
                node.nominal_sample_rate_hz, 1e-9
            )
            if relative_rate_error > 0.05:
                node.status = "degraded"
            node.last_seen_at = datetime.now(timezone.utc)
            node.received_frames += 1
            if campaign is not None:
                campaign.received_frames += 1
            self._last_sequence[frame.node_id] = frame.sequence

        try:
            samples = np.asarray(frame.samples, dtype=np.float32)
            features = extract_vibration_features(samples, frame.sample_rate_hz)
            quality = self._quality(samples, features, frame)
            model_result = await self._infer(samples, frame.sample_rate_hz, features)
            evidence_uri = self._persist(frame, features, quality, model_result)
            analysis = BenchFrameAnalysis(
                node_id=frame.node_id,
                asset_id=frame.asset_id,
                sequence=frame.sequence,
                accepted=quality.score >= 0.45,
                quality=quality,
                features=dict(features),
                model_result=model_result,
                evidence_uri=evidence_uri,
            )
        except Exception:
            with self._lock:
                node = self._nodes.get(frame.node_id)
                if node is not None:
                    node.received_frames = max(0, node.received_frames - 1)
                if frame.campaign_id is not None:
                    campaign = self._campaigns.get(frame.campaign_id)
                    if campaign is not None:
                        campaign.received_frames = max(0, campaign.received_frames - 1)
                if self._last_sequence.get(frame.node_id) == frame.sequence:
                    if previous is None:
                        self._last_sequence.pop(frame.node_id, None)
                    else:
                        self._last_sequence[frame.node_id] = previous
            raise

        with self._lock:
            self._frame_hashes[cache_key] = frame_hash
            self._analysis_cache[cache_key] = deepcopy(analysis)
        return analysis

    @staticmethod
    def _frame_hash(frame: BenchSignalFrame) -> str:
        metadata = frame.model_dump(mode="json", exclude={"samples"})
        canonical = json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode("utf-8")
        samples = np.asarray(frame.samples, dtype=np.float32)
        digest = hashlib.sha256(canonical)
        digest.update(samples.tobytes(order="C"))
        return digest.hexdigest()

    def to_incident_input(self, frame: BenchSignalFrame, analysis: BenchFrameAnalysis) -> IncidentInput:
        features = analysis.features
        predicted_class = str(analysis.model_result.get("class_name", "unknown anomaly"))
        confidence = float(analysis.model_result.get("confidence", 0.0))
        return IncidentInput(
            asset_id=frame.asset_id,
            summary=(
                f"Bench node {frame.node_id} detected {predicted_class} "
                f"with confidence {confidence:.2f}."
            ),
            telemetry=SensorSnapshot(
                timestamp=frame.timestamp,
                vibration_rms_g=max(0.0, float(features["rms"])),
                vibration_kurtosis=max(0.0, float(features["kurtosis"])),
                crest_factor=max(0.0, float(features["crest_factor"])),
                temperature_c=frame.temperature_c if frame.temperature_c is not None else 25.0,
                rotational_speed_rpm=frame.rpm,
                load_percent=min(150.0, frame.load_percent),
                quality=analysis.quality.score,
            ),
            operator_note=(
                f"Evidence: {analysis.evidence_uri}. Model={analysis.model_result.get('model_id', 'fallback')}."
            ),
        )

    async def _infer(
        self, samples: np.ndarray, sample_rate_hz: float, features: dict[str, float]
    ) -> dict[str, Any]:
        try:
            adapter = self.models.get("selected-vibration-model")
        except KeyError:
            anomaly_score = float(
                np.clip(
                    0.14 * features["rms"]
                    + 0.07 * max(0.0, features["kurtosis"] - 3.0)
                    + 0.06 * max(0.0, features["crest_factor"] - 3.0)
                    + 0.8 * features["band_energy_1500_3000"],
                    0.0,
                    1.0,
                )
            )
            return {
                "model_id": "transparent-signal-quality-fallback",
                "class_name": "normal" if anomaly_score < 0.42 else "unclassified_anomaly",
                "confidence": abs(anomaly_score - 0.5) * 2.0,
                "anomaly_probability": anomaly_score,
                "probabilities": {},
            }
        return await adapter.infer(
            {"samples": samples.tolist(), "sample_rate_hz": sample_rate_hz}
        )

    @staticmethod
    def _quality(
        samples: np.ndarray, features: dict[str, float], frame: BenchSignalFrame
    ) -> SignalQualityReport:
        rms = max(float(features["rms"]), 1e-12)
        dc_ratio = abs(float(np.mean(samples))) / rms
        clipping_ratio = float(features["clipping_ratio"])
        dropout_ratio = float(features["dropout_ratio"])
        unique = np.unique(np.round(samples, decimals=7)).size
        effective_bits = float(np.log2(max(unique, 1)))
        spectral_entropy = float(features["spectral_entropy"])
        high_band_energy = float(features["band_energy_3000_nyquist"])
        kurtosis = float(features["kurtosis"])
        crest_factor = float(features["crest_factor"])
        shaft_frequency = frame.rpm / 60.0 if frame.rpm > 0 else 0.0
        low_dominant = float(features.get("low_band_dominant_frequency_hz", 0.0))
        order_mismatch = False
        if shaft_frequency > 1.0 and low_dominant > 1.0:
            nearest_order = min(range(1, 7), key=lambda order: abs(low_dominant - order * shaft_frequency))
            relative_error = abs(low_dominant - nearest_order * shaft_frequency) / max(shaft_frequency, 1e-9)
            order_mismatch = relative_error > 0.14

        penalty = min(0.45, clipping_ratio * 4.0)
        penalty += min(0.45, dropout_ratio * 2.2)
        penalty += min(0.25, dc_ratio * 0.3)
        if effective_bits < 8:
            penalty += min(0.30, (8.0 - effective_bits) * 0.10)
        noisy = spectral_entropy > 0.44 and high_band_energy > 0.11
        if noisy:
            penalty += min(0.25, (spectral_entropy - 0.40) * 1.2 + high_band_energy * 0.25)
        impulsive_interference = kurtosis > 18.0 or crest_factor > 8.0
        if impulsive_interference:
            penalty += 0.22
        if order_mismatch:
            penalty += 0.12

        warnings: list[str] = []
        if clipping_ratio > 0.01:
            warnings.append("Possible analog or ADC clipping")
        if dropout_ratio > 0.08:
            warnings.append("Possible acquisition dropout or disconnected sensor")
        if dc_ratio > 0.4:
            warnings.append("Large DC offset relative to signal RMS")
        if effective_bits < 8:
            warnings.append("Low effective amplitude resolution or quantization")
        if noisy:
            warnings.append("Broadband noise floor is inconsistent with the clean reference envelope")
        if impulsive_interference:
            warnings.append("Sparse impulse interference exceeds the sensor-integrity threshold")
        if order_mismatch:
            warnings.append("Reported RPM and low-frequency order content are inconsistent")
        return SignalQualityReport(
            score=float(np.clip(1.0 - penalty, 0.0, 1.0)),
            clipping_ratio=clipping_ratio,
            dropout_ratio=dropout_ratio,
            dc_offset_ratio=dc_ratio,
            effective_bits_estimate=effective_bits,
            warnings=warnings,
        )

    def _persist(
        self,
        frame: BenchSignalFrame,
        features: dict[str, float],
        quality: SignalQualityReport,
        model_result: dict[str, Any],
    ) -> str:
        node_dir = self.evidence_dir / frame.node_id
        node_dir.mkdir(parents=True, exist_ok=True)
        stem = f"{frame.timestamp.strftime('%Y%m%dT%H%M%S')}-{frame.sequence:08d}"
        npz_path = node_dir / f"{stem}.npz"
        np.savez_compressed(
            npz_path,
            samples=np.asarray(frame.samples, dtype=np.float32),
            sample_rate_hz=np.asarray([frame.sample_rate_hz]),
        )
        metadata_path = node_dir / f"{stem}.json"
        metadata_path.write_text(
            json.dumps(
                {
                    "frame": frame.model_dump(mode="json", exclude={"samples"}),
                    "features": features,
                    "quality": quality.model_dump(mode="json"),
                    "model_result": model_result,
                    "waveform_file": npz_path.name,
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        return str(metadata_path)
