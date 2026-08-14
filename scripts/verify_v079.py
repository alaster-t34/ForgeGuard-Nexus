from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "edge-node"))

from app.analysis.service import IndustrialDataAnalysisService  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.csv_policy import ANALYSIS_CSV_POLICY, csv_policy_catalog  # noqa: E402
from forgeguard_edge.csv_adapter import CsvReplayAdapter  # noqa: E402


def verify_small_csv() -> dict[str, object]:
    rows = ["sample_id,rpm,timestamp,acceleration_x"]
    rows.extend(
        f"sample-{index // 64},1800,{index / 12000:.8f},{np.sin(index):.8f}"
        for index in range(128)
    )
    values, selected, warnings = IndustrialDataAnalysisService._parse_csv(
        "\n".join(rows).encode("utf-8"), None
    )
    assert selected == "acceleration_x"
    assert values.size == 128

    chinese_rows = ["时间,振动值", *(f"{index},{index / 10:.1f}" for index in range(64))]
    for encoding in ("gb18030", "utf-16"):
        decoded, column, _ = IndustrialDataAnalysisService._parse_csv(
            "\n".join(chinese_rows).encode(encoding), "振动值"
        )
        assert column == "振动值"
        assert decoded.size == 64

    too_wide = ",".join(f"c{index}" for index in range(257)) + "\n" + ",".join(
        "1" for _ in range(257)
    )
    try:
        IndustrialDataAnalysisService._parse_csv(too_wide.encode(), None)
    except ValueError as exc:
        assert "256" in str(exc)
    else:
        raise AssertionError("257-column CSV was not rejected")

    return {
        "selected_column": selected,
        "samples": int(values.size),
        "warnings": warnings,
        "encoding_checks": ["gb18030", "utf-16"],
        "column_limit_check": "passed",
    }


def verify_edge_csv() -> dict[str, object]:
    runtime_dir = ROOT / "runtime-data"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="v079-中文-", dir=runtime_dir) as directory:
        path = Path(directory) / "中文波形.csv"
        path.write_bytes("时间,振动值\n0,1.25\n1,2.5\n2,3.75\n".encode("gb18030"))
        frame = asyncio.run(CsvReplayAdapter(path, signal_column="振动值").acquire())
        assert frame.payload == [1.25, 2.5, 3.75]
        assert frame.metadata["signal_column"] == "振动值"
        return dict(frame.metadata)


def verify_merged_train() -> dict[str, object]:
    path = (
        ROOT
        / "data"
        / "openeval"
        / "ForgeGuard-OpenEval-RM-v0.1.0-waveform-csv"
        / "train_merged.csv"
    )
    if not path.is_file():
        return {"status": "skipped", "reason": f"not found: {path}"}
    started = time.perf_counter()
    content = path.read_bytes()
    assert len(content) <= ANALYSIS_CSV_POLICY.max_bytes
    values, selected, warnings = IndustrialDataAnalysisService._parse_csv(content, None)
    elapsed = time.perf_counter() - started
    assert selected == "acceleration_x"
    assert values.size == 589_824
    assert np.all(np.isfinite(values))
    return {
        "status": "passed",
        "file_mb": round(len(content) / 1024 / 1024, 2),
        "samples": int(values.size),
        "selected_column": selected,
        "elapsed_seconds": round(elapsed, 2),
        "warnings": warnings,
    }


def main() -> int:
    settings = get_settings()
    assert settings.app_version == "0.7.9"
    report = {
        "version": settings.app_version,
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "csv_policies": csv_policy_catalog(),
        "small_csv": verify_small_csv(),
        "edge_csv": verify_edge_csv(),
        "merged_train": verify_merged_train(),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
