from __future__ import annotations

from pathlib import Path
from typing import Any

from app.models.contracts import ModelAdapter, ModelMetadata


class LegacyBearingModelAdapter(ModelAdapter[dict[str, Any], dict[str, Any]]):
    """Boundary around prior WDCNN/FP-FLNet/RKNN assets.

    The new application never imports the legacy monolithic GUI. Instead, legacy
    inference is exposed behind a narrow JSON contract and can be replaced by a
    newer model without changing the agent workflow.
    """

    metadata = ModelMetadata(
        id="legacy-bearing-stack",
        role="bearing-diagnosis-and-rul",
        version="compat-v1",
        license="user-owned-or-third-party-disclosed",
        runtime=("pytorch", "onnxruntime", "rknn"),
        calibrated=False,
        source="bearing_main_code_compliant_v2_20260722.zip",
    )

    def __init__(self, legacy_root: Path) -> None:
        self.legacy_root = legacy_root

    async def infer(self, payload: dict[str, Any]) -> dict[str, Any]:
        required = {"signal", "sample_rate"}
        missing = required - payload.keys()
        if missing:
            raise ValueError(f"Missing legacy adapter fields: {sorted(missing)}")
        return {
            "status": "adapter_contract_ready",
            "message": "Mount validated legacy weights and select an explicit runtime before inference.",
            "legacy_root": str(self.legacy_root),
        }
