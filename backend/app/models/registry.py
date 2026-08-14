from __future__ import annotations

from collections.abc import Iterable

from app.models.contracts import ModelAdapter


class ModelRegistry:
    def __init__(self, adapters: Iterable[ModelAdapter] = ()) -> None:
        self._adapters: dict[str, ModelAdapter] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: ModelAdapter) -> None:
        if adapter.metadata.id in self._adapters:
            raise ValueError(f"Duplicate model adapter: {adapter.metadata.id}")
        self._adapters[adapter.metadata.id] = adapter

    def get(self, model_id: str) -> ModelAdapter:
        try:
            return self._adapters[model_id]
        except KeyError as exc:
            raise KeyError(f"Unknown model adapter: {model_id}") from exc

    def catalog(self) -> list[dict[str, object]]:
        return [
            {
                "id": adapter.metadata.id,
                "role": adapter.metadata.role,
                "version": adapter.metadata.version,
                "license": adapter.metadata.license,
                "runtime": adapter.metadata.runtime,
                "calibrated": adapter.metadata.calibrated,
                "source": adapter.metadata.source,
            }
            for adapter in self._adapters.values()
        ]
