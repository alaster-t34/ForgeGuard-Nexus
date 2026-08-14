from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput")


@dataclass(slots=True, frozen=True)
class ModelMetadata:
    id: str
    role: str
    version: str
    license: str
    runtime: tuple[str, ...]
    calibrated: bool
    source: str


class ModelAdapter(ABC, Generic[TInput, TOutput]):
    metadata: ModelMetadata

    @abstractmethod
    async def infer(self, payload: TInput) -> TOutput:
        """Run inference without mutating external systems."""

    async def healthcheck(self) -> dict[str, Any]:
        return {
            "id": self.metadata.id,
            "version": self.metadata.version,
            "status": "ready",
            "runtime": self.metadata.runtime,
        }
