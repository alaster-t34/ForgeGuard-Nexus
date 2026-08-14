from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

import httpx
import numpy as np

from forgeguard_edge.csv_adapter import CsvReplayAdapter


@dataclass(slots=True, frozen=True)
class BenchNodeConfig:
    node_id: str
    asset_id: str
    name: str
    hardware: str
    nominal_sample_rate_hz: float
    sensor_position: str
    sensor_mounting: str
    transport: str = "http"
    operating_system: str | None = None
    channel: str = "acceleration_x"
    unit: str = "g"
    platform_metadata: dict[str, object] = field(default_factory=dict)

    def registration_payload(self) -> dict[str, object]:
        return {
            "node_id": self.node_id,
            "asset_id": self.asset_id,
            "name": self.name,
            "transport": self.transport,
            "hardware": self.hardware,
            "operating_system": self.operating_system,
            "modalities": ["vibration"],
            "channels": [self.channel],
            "nominal_sample_rate_hz": self.nominal_sample_rate_hz,
            "sensor_position": self.sensor_position,
            "sensor_mounting": self.sensor_mounting,
            "calibration": {
                "performed_at": None,
                "method": "user-declared",
                "reference": None,
                "sensitivity": None,
                "unit": self.unit,
                "certificate_uri": None,
            },
            "metadata": {"client": "ForgeGuard Edge 0.3", **self.platform_metadata},
        }


class ForgeGuardBenchClient:
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 12.0,
        *,
        retries: int = 3,
        retry_base_seconds: float = 0.4,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.retries = max(0, retries)
        self.retry_base_seconds = max(0.0, retry_base_seconds)

    async def _post(self, path: str, payload: dict) -> dict:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(
                        f"{self.base_url}{path}",
                        json=payload,
                        headers={"User-Agent": "ForgeGuard-Edge/0.3"},
                    )
                    # 4xx responses are deterministic contract/permission errors;
                    # retrying them can duplicate traffic without helping.
                    if 400 <= response.status_code < 500:
                        response.raise_for_status()
                    if response.status_code >= 500:
                        response.raise_for_status()
                    return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt >= self.retries:
                    break
                await asyncio.sleep(self.retry_base_seconds * (2**attempt))
        assert last_error is not None
        raise last_error

    async def register(self, config: BenchNodeConfig) -> dict:
        return await self._post("/api/v1/bench/nodes", config.registration_payload())

    async def register_campaign(self, payload: dict) -> dict:
        return await self._post("/api/v1/bench/campaigns", payload)

    @staticmethod
    def frame_payload(
        config: BenchNodeConfig,
        samples: np.ndarray,
        *,
        sequence: int,
        rpm: float,
        load_percent: float,
        campaign_id: str | None = None,
        temperature_c: float | None = None,
        open_incident: bool = False,
        metadata: dict | None = None,
    ) -> dict:
        return {
            "node_id": config.node_id,
            "asset_id": config.asset_id,
            "campaign_id": campaign_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sequence": sequence,
            "channel": config.channel,
            "unit": config.unit,
            "sample_rate_hz": config.nominal_sample_rate_hz,
            "samples": np.asarray(samples, dtype=np.float32).tolist(),
            "rpm": rpm,
            "load_percent": load_percent,
            "temperature_c": temperature_c,
            "metadata": metadata or {},
            "open_incident": open_incident,
        }

    async def publish_payload(self, payload: dict) -> dict:
        return await self._post("/api/v1/bench/frames", payload)

    async def publish_window(
        self,
        config: BenchNodeConfig,
        samples: np.ndarray,
        *,
        sequence: int,
        rpm: float,
        load_percent: float,
        campaign_id: str | None = None,
        temperature_c: float | None = None,
        open_incident: bool = False,
        metadata: dict | None = None,
    ) -> dict:
        payload = self.frame_payload(
            config,
            samples,
            sequence=sequence,
            rpm=rpm,
            campaign_id=campaign_id,
            load_percent=load_percent,
            temperature_c=temperature_c,
            open_incident=open_incident,
            metadata=metadata,
        )
        return await self.publish_payload(payload)


async def csv_windows(
    path: Path,
    *,
    window_size: int,
    hop_size: int,
    signal_column: str | int | None = None,
    sample_rate_hz: float = 25_600.0,
) -> AsyncIterator[np.ndarray]:
    frame = await CsvReplayAdapter(
        path,
        signal_column=signal_column,
        sample_rate_hz=sample_rate_hz,
    ).acquire()
    values = np.asarray(frame.payload, dtype=np.float32)
    if values.size < window_size:
        padded = np.pad(values, (0, window_size - values.size), mode="edge")
        yield padded
        return
    for start in range(0, values.size - window_size + 1, hop_size):
        yield values[start : start + window_size]
        await asyncio.sleep(0)
