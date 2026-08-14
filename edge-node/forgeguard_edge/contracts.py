from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol

from pydantic import BaseModel, Field


class RawFrame(BaseModel):
    source_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    modality: str
    sampling_rate_hz: float | None = None
    payload: list[float] | str | dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


class SensorAdapter(Protocol):
    async def acquire(self) -> RawFrame: ...


class InferenceAdapter(Protocol):
    async def infer(self, frame: RawFrame) -> dict[str, Any]: ...


class TransportAdapter(Protocol):
    async def publish(self, topic: str, payload: dict[str, Any]) -> None: ...
