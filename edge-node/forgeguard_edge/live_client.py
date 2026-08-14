from __future__ import annotations

from typing import Any

import httpx
import numpy as np


class ForgeGuardLiveClient:
    """Client for the user-facing real-time detection session API."""

    def __init__(self, server: str, *, timeout_seconds: float = 15.0) -> None:
        self.base_url = server.rstrip("/") + "/api/v1"
        self.timeout_seconds = timeout_seconds

    async def create_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(f"{self.base_url}/analysis/live/sessions", json=payload)
            response.raise_for_status()
            return response.json()

    async def publish_frame(
        self,
        session_id: str,
        samples: np.ndarray,
        *,
        rpm: float,
        load_percent: float,
        temperature_c: float | None,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            "samples": np.asarray(samples, dtype=np.float32).reshape(-1).tolist(),
            "rpm": rpm,
            "load_percent": load_percent,
            "temperature_c": temperature_c,
            "metadata": metadata,
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.base_url}/analysis/live/sessions/{session_id}/frames",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def stop_session(self, session_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.delete(
                f"{self.base_url}/analysis/live/sessions/{session_id}"
            )
            response.raise_for_status()
            return response.json()
