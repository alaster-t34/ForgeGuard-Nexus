import io

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.analysis.service import IndustrialDataAnalysisService
from app.csv_policy import ANALYSIS_CSV_POLICY, MIB, ensure_csv_size
from app.main import app


client = TestClient(app)


def test_csv_auto_selects_acceleration_in_long_table():
    rows = ["sample_id,rpm,load_percent,timestamp,acceleration_x"]
    rows.extend(
        f"sample-{index // 64},1800,70,{index / 12000:.8f},{np.sin(index):.8f}"
        for index in range(128)
    )
    values, selected, warnings = IndustrialDataAnalysisService._parse_csv(
        "\n".join(rows).encode("utf-8"), None
    )
    assert selected == "acceleration_x"
    assert values.shape == (128,)
    assert not np.allclose(values, 1800.0)
    assert any("utf-8" in warning for warning in warnings)


@pytest.mark.parametrize("encoding", ["gb18030", "utf-16"])
def test_csv_supports_chinese_header_and_windows_encodings(encoding: str):
    rows = ["时间,振动值"]
    rows.extend(f"{index},{index / 10:.1f}" for index in range(64))
    values, selected, _ = IndustrialDataAnalysisService._parse_csv(
        "\n".join(rows).encode(encoding), "振动值"
    )
    assert selected == "振动值"
    assert values.size == 64
    assert values[-1] == pytest.approx(6.3)


def test_csv_rejects_column_limit_overflow():
    header = ",".join(f"column_{index}" for index in range(257))
    row = ",".join("1" for _ in range(257))
    with pytest.raises(ValueError, match="256"):
        IndustrialDataAnalysisService._parse_csv(
            f"{header}\n{row}".encode("utf-8"), None
        )


def test_csv_size_policy_is_explicit():
    ensure_csv_size(128 * MIB, ANALYSIS_CSV_POLICY)
    with pytest.raises(ValueError, match="128 MB"):
        ensure_csv_size(128 * MIB + 1, ANALYSIS_CSV_POLICY)


def test_csv_limits_endpoint_matches_backend_policy():
    response = client.get("/api/v1/analysis/csv/limits")
    assert response.status_code == 200
    policy = response.json()["historical-analysis-upload"]
    assert policy["max_size_mb"] == 128
    assert policy["max_rows"] == 1_000_000
    assert policy["max_columns"] == 256


def test_csv_upload_rejects_non_csv_extension():
    payload = ("acceleration_x\n" + "\n".join("0.1" for _ in range(64))).encode()
    response = client.post(
        "/api/v1/analysis/csv",
        files={"file": ("waveform.xlsx", io.BytesIO(payload), "application/octet-stream")},
        data={"create_incident": "false"},
    )
    assert response.status_code == 422
    assert "accepts .csv or .txt" in response.text
