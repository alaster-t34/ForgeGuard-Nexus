from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.benchmark.runner import BenchmarkRunner
from app.benchmark.schemas import BenchmarkRunRequest
from app.domain.enums import AgentName, ToolRisk
from app.fault_injection.signal import (
    PhysicalFault,
    SensorFault,
    generate_rotating_machine_signal,
    inject_sensor_fault,
)
from app.fault_injection.workflow import WorkflowFault, WorkflowFaultMode
from app.main import app
from app.services.tools import ToolRegistry


client = TestClient(app)


def test_physics_fault_and_sensor_injection_are_deterministic():
    base_a = generate_rotating_machine_signal(
        PhysicalFault.OUTER_RACE, duration_seconds=0.1, seed=7
    )
    base_b = generate_rotating_machine_signal(
        PhysicalFault.OUTER_RACE, duration_seconds=0.1, seed=7
    )
    assert np.array_equal(base_a, base_b)
    clipped = inject_sensor_fault(base_a, SensorFault.CLIPPING, severity=0.8, seed=8)
    assert np.max(np.abs(clipped)) < np.max(np.abs(base_a))
    dropout = inject_sensor_fault(base_a, SensorFault.DROPOUT, severity=0.7, seed=8)
    assert np.count_nonzero(dropout == 0.0) > 0


def test_open_eval_and_real_model_benchmark(tmp_path: Path):
    project = tmp_path / "project"
    (project / "backend" / "research" / "artifacts").mkdir(parents=True)
    report = BenchmarkRunner(project).run(
        BenchmarkRunRequest(
            samples_per_class=16,
            signal_length=512,
            sample_rate_hz=8_000,
            include_cnn=False,
            seed=11,
        )
    )
    assert len(report.models) == 5
    assert report.best_model_id in {item.model_id for item in report.models}
    assert all(0 <= item.macro_f1 <= 1 for item in report.models)
    assert (project / report.artifact_paths["dataset"]).exists()
    assert (project / report.artifact_paths["selected_model"]).exists()


def test_bench_node_registration_and_frame_ingestion():
    signal = generate_rotating_machine_signal(
        PhysicalFault.OUTER_RACE,
        sample_rate_hz=12_000,
        duration_seconds=0.12,
        severity=0.8,
        seed=22,
    )
    registration = {
        "node_id": "PYTEST-BENCH-001",
        "asset_id": "FG-BRG-001",
        "name": "pytest bench",
        "transport": "http",
        "hardware": "simulated DAQ",
        "modalities": ["vibration"],
        "channels": ["acceleration_x"],
        "nominal_sample_rate_hz": 12000,
        "sensor_position": "drive end radial",
        "sensor_mounting": "stud",
        "calibration": {"method": "synthetic-test", "unit": "g"},
    }
    response = client.post("/api/v1/bench/nodes", json=registration)
    assert response.status_code == 201
    response = client.post(
        "/api/v1/bench/frames",
        json={
            "node_id": "PYTEST-BENCH-001",
            "asset_id": "FG-BRG-001",
            "sequence": 1,
            "sample_rate_hz": 12000,
            "samples": signal.tolist(),
            "rpm": 1800,
            "load_percent": 75,
            "temperature_c": 62,
            "open_incident": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["features"]["rms"] > 0
    assert payload["model_result"]["model_id"]


@pytest.mark.asyncio
async def test_workflow_fault_injection_is_audited():
    registry = ToolRegistry()

    async def handler(value: int):
        return {"value": value}

    registry.register("demo.read", ToolRisk.READ_ONLY, handler)
    registry.inject_fault(
        WorkflowFault(
            tool_name="demo.read",
            mode=WorkflowFaultMode.ERROR,
            remaining_calls=1,
            message="planned failure",
        )
    )
    record, result = await registry.call(
        "demo.read", agent=AgentName.COORDINATOR, arguments={"value": 3}
    )
    assert result is None
    assert record.status == "failed"
    assert "planned failure" in (record.error or "")
    record, result = await registry.call(
        "demo.read", agent=AgentName.COORDINATOR, arguments={"value": 3}
    )
    assert record.status == "succeeded"
    assert result == {"value": 3}


def test_openeval_scorer_accepts_perfect_submission(tmp_path: Path):
    import csv
    import json

    from app.benchmark.datasets import OpenEvalBuilder
    from app.benchmark.scoring import score_submission

    dataset_dir = tmp_path / "openeval"
    OpenEvalBuilder(dataset_dir).build(
        samples_per_class=14,
        signal_length=256,
        sample_rate_hz=4_000,
        seed=17,
    )
    rows = [
        json.loads(line)
        for line in (dataset_dir / "metadata.jsonl").read_text(encoding="utf-8").splitlines()
        if json.loads(line)["split"] == "test"
    ]
    submission = tmp_path / "perfect.csv"
    with submission.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["sample_id", "predicted_label", "confidence"]
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "sample_id": row["sample_id"],
                    "predicted_label": row["fault_mode"],
                    "confidence": "0.999",
                }
            )
    score = score_submission(dataset_dir, submission)
    assert score["accuracy"] == pytest.approx(1.0)
    assert score["macro_f1"] == pytest.approx(1.0)
    assert score["balanced_accuracy"] == pytest.approx(1.0)
    assert score["expected_calibration_error"] < 0.01


def test_cwru_adapter_loads_downloaded_mat_layout(tmp_path: Path):
    from scipy.io import savemat

    from app.benchmark.external_datasets import CWRUAdapter

    sample_rate_hz = 12_000
    time = np.arange(4096, dtype=np.float32) / sample_rate_hz
    signal = np.sin(2 * np.pi * 120 * time).astype(np.float32)
    savemat(tmp_path / "normal_baseline.mat", {"X097_DE_time": signal[:, None]})
    savemat(tmp_path / "IR_007_load0.mat", {"X105_DE_time": (signal * 1.5)[:, None]})

    loaded = CWRUAdapter().load(
        tmp_path,
        sample_rate_hz=sample_rate_hz,
        window_size=1024,
        hop_size=1024,
    )
    assert loaded.signals.shape == (8, 1024)
    assert set(loaded.labels.tolist()) == {0, 1}
    assert loaded.label_names == ["normal", "inner_race", "outer_race", "ball"]
    assert set(loaded.groups.tolist()) == {"normal_baseline", "IR_007_load0"}


def test_fault_injection_api_returns_auditable_signal():
    response = client.post(
        "/api/v1/fault-injection/signal",
        json={
            "physical_fault": "outer_race",
            "sensor_fault": "low_snr",
            "sample_rate_hz": 12000,
            "duration_seconds": 0.1,
            "rpm": 1800,
            "load_percent": 70,
            "severity": 0.75,
            "sensor_severity": 0.55,
            "seed": 123,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["samples"]) == 1200
    assert payload["metadata"]["physical_fault"] == "outer_race"
    assert payload["metadata"]["sensor_fault"] == "low_snr"
    assert payload["metadata"]["seed"] == 123


def test_bench_duplicate_frame_is_idempotent_but_mutation_is_rejected():
    signal = generate_rotating_machine_signal(
        PhysicalFault.IMBALANCE,
        sample_rate_hz=8_000,
        duration_seconds=0.1,
        severity=0.7,
        seed=91,
    )
    registration = {
        "node_id": "PYTEST-IDEMPOTENT-001",
        "asset_id": "FG-BRG-001",
        "name": "idempotency bench",
        "transport": "http",
        "hardware": "simulated DAQ",
        "modalities": ["vibration"],
        "channels": ["acceleration_x"],
        "nominal_sample_rate_hz": 8000,
        "sensor_position": "drive end radial",
        "sensor_mounting": "stud",
        "calibration": {"method": "synthetic-test", "unit": "g"},
    }
    assert client.post("/api/v1/bench/nodes", json=registration).status_code == 201
    frame = {
        "node_id": registration["node_id"],
        "asset_id": registration["asset_id"],
        "timestamp": "2026-07-23T12:00:00Z",
        "sequence": 5,
        "sample_rate_hz": 8000,
        "samples": signal.tolist(),
        "rpm": 1800,
        "load_percent": 65,
        "open_incident": False,
    }
    first = client.post("/api/v1/bench/frames", json=frame)
    second = client.post("/api/v1/bench/frames", json=frame)
    assert first.status_code == second.status_code == 200
    assert first.json()["evidence_uri"] == second.json()["evidence_uri"]

    mutated = {**frame, "samples": [value * 1.01 for value in frame["samples"]]}
    rejected = client.post("/api/v1/bench/frames", json=mutated)
    assert rejected.status_code == 422
    assert "different content" in rejected.json()["detail"]


@pytest.mark.asyncio
async def test_edge_spool_preserves_order_and_sequence_state(tmp_path: Path):
    import sys

    edge_root = Path(__file__).resolve().parents[2] / "edge-node"
    sys.path.insert(0, str(edge_root))
    try:
        from forgeguard_edge.spool import FrameSpool

        spool = FrameSpool(tmp_path / "spool")
        spool.enqueue({"node_id": "EDGE-1", "sequence": 7, "samples": [1.0]})
        spool.enqueue({"node_id": "EDGE-1", "sequence": 8, "samples": [2.0]})
        spool.mark_next_sequence(9)
        delivered: list[int] = []
        fail_once = True

        async def publisher(payload: dict):
            nonlocal fail_once
            if fail_once:
                fail_once = False
                raise RuntimeError("offline")
            delivered.append(int(payload["sequence"]))
            return {"accepted": True}

        failed = await spool.flush(publisher)
        assert failed.delivered == 0
        assert failed.failed == 1
        assert failed.remaining == 2
        recovered = await spool.flush(publisher)
        assert recovered.delivered == 2
        assert delivered == [7, 8]
        assert spool.next_sequence() == 9
    finally:
        sys.path.remove(str(edge_root))


def test_external_group_split_prevents_recording_leakage():
    from app.benchmark.external_runner import grouped_stratified_split

    labels = np.asarray([0] * 6 + [1] * 6, dtype=np.int64)
    groups = np.asarray(
        ["n-a", "n-a", "n-b", "n-b", "n-c", "n-c"]
        + ["f-a", "f-a", "f-b", "f-b", "f-c", "f-c"]
    )
    train, validation, test = grouped_stratified_split(labels, groups, seed=9)
    train_groups = set(groups[train])
    validation_groups = set(groups[validation])
    test_groups = set(groups[test])
    assert train_groups.isdisjoint(validation_groups)
    assert train_groups.isdisjoint(test_groups)
    assert validation_groups.isdisjoint(test_groups)
    for mask in (train, validation, test):
        assert set(labels[mask].tolist()) == {0, 1}


def test_rig_campaign_manifest_is_bound_to_node_and_counts_frames():
    node_id = "PYTEST-RIG-CAMPAIGN-001"
    campaign_id = "PYTEST-RIG-001"
    registration = {
        "node_id": node_id,
        "asset_id": "FG-BRG-001",
        "name": "physical rig contract test",
        "transport": "serial",
        "hardware": "test DAQ",
        "modalities": ["vibration"],
        "channels": ["acceleration_x"],
        "nominal_sample_rate_hz": 8000,
        "sensor_position": "drive-end radial",
        "sensor_mounting": "stud",
        "calibration": {"method": "reference", "unit": "g"},
    }
    assert client.post("/api/v1/bench/nodes", json=registration).status_code == 201
    campaign = {
        "campaign_id": campaign_id,
        "node_id": node_id,
        "asset_id": "FG-BRG-001",
        "title": "pytest guarded rig campaign",
        "operator_id": "pytest-operator",
        "specimen": {
            "specimen_id": "pytest-specimen",
            "condition": "healthy",
            "provenance": "pytest fixture",
        },
        "sensor": {
            "manufacturer": "pytest",
            "model": "accelerometer",
            "position": "drive-end radial",
            "mounting": "stud",
            "calibration": {"method": "reference", "unit": "g"},
        },
        "daq": {
            "manufacturer": "pytest",
            "model": "daq",
            "bit_depth": 24,
        },
        "safety": {
            "guard_installed": True,
            "emergency_stop_verified": True,
            "max_rpm": 2400,
            "max_load_percent": 100,
            "approved_by": "pytest-safety",
        },
        "operating_points": [
            {"rpm": 1800, "load_percent": 60, "duration_seconds": 10}
        ],
    }
    response = client.post("/api/v1/bench/campaigns", json=campaign)
    assert response.status_code == 201

    signal = generate_rotating_machine_signal(
        PhysicalFault.NORMAL,
        sample_rate_hz=8000,
        duration_seconds=0.1,
        seed=202,
    )
    response = client.post(
        "/api/v1/bench/frames",
        json={
            "node_id": node_id,
            "asset_id": "FG-BRG-001",
            "campaign_id": campaign_id,
            "sequence": 0,
            "sample_rate_hz": 8000,
            "samples": signal.tolist(),
            "rpm": 1800,
            "load_percent": 60,
        },
    )
    assert response.status_code == 200
    campaigns = client.get("/api/v1/bench/campaigns").json()
    state = next(item for item in campaigns if item["campaign_id"] == campaign_id)
    assert state["received_frames"] == 1
    assert state["rejected_frames"] == 0
