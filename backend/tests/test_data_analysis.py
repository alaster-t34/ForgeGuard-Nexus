import io

import numpy as np
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_live_detection_session_processes_simulated_frames():
    response = client.post(
        "/api/v1/analysis/live/sessions",
        json={
            "asset_id": "FG-BRG-001",
            "source": "simulator",
            "sample_rate_hz": 12000,
            "rpm": 1800,
            "load_percent": 70,
            "open_incident": False,
        },
    )
    assert response.status_code == 201
    session = response.json()

    response = client.post(
        f"/api/v1/analysis/live/sessions/{session['id']}/simulate",
        json={
            "fault_mode": "normal",
            "sensor_fault": "none",
            "severity": 0.1,
            "duration_seconds": 0.5,
        },
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["total_frames"] == 1
    assert updated["last_analysis"] is not None
    assert len(updated["waveform_preview"]) > 20

    response = client.delete(f"/api/v1/analysis/live/sessions/{session['id']}")
    assert response.status_code == 200
    assert response.json()["status"] == "stopped"


def test_csv_upload_analyzes_multicolumn_historical_data():
    t = np.arange(4096, dtype=np.float32) / 12000.0
    signal = 0.08 * np.sin(2 * np.pi * 30 * t) + 0.02 * np.sin(2 * np.pi * 120 * t)
    rows = ["timestamp,acceleration_x"]
    rows.extend(f"{index / 12000.0:.8f},{value:.8f}" for index, value in enumerate(signal))
    payload = "\n".join(rows).encode("utf-8")

    response = client.post(
        "/api/v1/analysis/csv",
        files={"file": ("healthy.csv", io.BytesIO(payload), "text/csv")},
        data={
            "asset_id": "FG-BRG-001",
            "signal_column": "acceleration_x",
            "sample_rate_hz": "12000",
            "rpm": "1800",
            "load_percent": "70",
            "window_size": "2048",
            "hop_size": "1024",
            "create_incident": "false",
        },
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["file_name"] == "healthy.csv"
    assert report["signal_column"] == "acceleration_x"
    assert report["total_samples"] == 4096
    assert report["total_windows"] >= 3
    assert report["accepted_windows"] + report["rejected_windows"] == report["total_windows"]
    assert len(report["waveform_preview"]) > 20

    reports = client.get("/api/v1/analysis/csv/reports").json()
    assert any(item["id"] == report["id"] for item in reports)
