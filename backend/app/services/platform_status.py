from __future__ import annotations

import os
import platform
from pathlib import Path


def _read_text(path: str) -> str | None:
    try:
        value = Path(path).read_text(encoding="utf-8", errors="ignore").replace("\x00", "").strip()
        return value or None
    except OSError:
        return None


def platform_status() -> dict[str, object]:
    l4t = _read_text("/etc/nv_tegra_release")
    model = _read_text("/proc/device-tree/model")
    profile = os.getenv("FORGEGUARD_DEPLOYMENT_PROFILE", "generic")
    is_jetson = bool(l4t or (model and "jetson" in model.lower()))
    return {
        "profile": profile,
        "platform": os.getenv("FORGEGUARD_PLATFORM_NAME", model or platform.machine()),
        "architecture": platform.machine(),
        "jetson": is_jetson,
        "l4t": l4t,
        "jetpack": os.getenv("FORGEGUARD_JETPACK_VERSION", "unknown"),
        "cuda": os.getenv("FORGEGUARD_CUDA_VERSION", "unknown"),
        "tensorrt": os.getenv("FORGEGUARD_TENSORRT_VERSION", "unknown"),
        "power_mode": os.getenv("FORGEGUARD_POWER_MODE", "operator-managed"),
        "runtime": os.getenv("FORGEGUARD_INFERENCE_RUNTIME", "CPU + optional TensorRT"),
        "mode": os.getenv("FORGEGUARD_OPERATION_MODE", "demo-replay-live"),
        "safety": {
            "human_approval": True,
            "read_only_equipment": True,
            "post_maintenance_verification": True,
        },
    }
