from fastapi.testclient import TestClient

from app.main import app
from app.runtime import runtime


client = TestClient(app)


def test_health_and_seed_assets():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assets = client.get("/api/v1/assets").json()
    assert any(asset["id"] == "FG-BRG-001" for asset in assets)


def test_full_incident_approval_verification_loop():
    runtime.store.reset()
    from app.bootstrap import seed_store

    seed_store(runtime.store)
    response = client.post(
        "/api/v1/demo/run",
        json={"scenario": "outer_race_spall", "asset_id": "FG-BRG-001"},
    )
    assert response.status_code == 200
    incident = response.json()
    assert incident["status"] == "awaiting_approval"
    assert incident["diagnosis"]["primary"]["fault_mode"] == "outer-race localized spalling"
    assert len(incident["trace"]) >= 4
    assert len(incident["evidence"]) >= 5

    option_id = incident["plan"]["recommended_option_id"]
    response = client.post(
        f"/api/v1/incidents/{incident['id']}/approve",
        json={"option_id": option_id, "approved_by": "Safety Officer"},
    )
    assert response.status_code == 200
    approved = response.json()
    assert approved["work_order"]["status"] == "approved"

    response = client.post(
        f"/api/v1/demo/{incident['id']}/complete",
        params={"scenario": "outer_race_spall"},
    )
    assert response.status_code == 200
    verified = response.json()
    assert verified["status"] == "resolved"
    assert verified["verification"]["passed"] is True
    assert verified["work_order"]["status"] == "completed"
    assert verified["risk"] == "low"
    assert verified["reliability"]["rul_hours_p50"] == 680.0


def test_sensor_conflict_requires_more_evidence():
    response = client.post(
        "/api/v1/demo/run",
        json={"scenario": "sensor_conflict", "asset_id": "FG-BRG-001"},
    )
    assert response.status_code == 200
    incident = response.json()
    assert incident["diagnosis"]["needs_more_evidence"] is True
    assert incident["plan"]["recommended_option_id"] == "acquire-more"
