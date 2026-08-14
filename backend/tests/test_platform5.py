from pathlib import Path

from fastapi.testclient import TestClient

from app.bootstrap import seed_store
from app.main import app
from app.runtime import runtime
from app.services.store import PersistentStore


client = TestClient(app)


def test_industry5_agents_and_decision_contract():
    runtime.store.reset()
    seed_store(runtime.store)
    response = client.post(
        "/api/v1/demo/run",
        json={"scenario": "outer_race_spall", "asset_id": "FG-BRG-001"},
    )
    assert response.status_code == 200
    incident = response.json()
    assert incident["safety"]["approval_required"] is True
    assert incident["sustainability"]["estimated_excess_energy_kwh_per_day"] > 0
    assert incident["resilience"]["offline_capable"] is True
    assert incident["plan"]["recommended_option_id"] == "replace-now"
    recommended = next(
        item for item in incident["plan"]["options"] if item["id"] == "replace-now"
    )
    assert recommended["score"] >= max(
        item["score"] for item in incident["plan"]["options"] if item["id"] != "replace-now"
    )


def test_dashboard_and_cross_domain_endpoints():
    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 200
    summary = response.json()
    assert summary["total_assets"] >= 5
    assert 0 <= summary["human_safety_index"] <= 100
    assert client.get("/api/v1/inventory").status_code == 200
    assert client.get("/api/v1/production/orders").status_code == 200
    assert client.get("/api/v1/people/technicians").status_code == 200
    assert client.get("/api/v1/agents/status").status_code == 200
    assert client.get("/api/v1/edge/nodes").status_code == 200


def test_assistant_uses_governed_deterministic_mode():
    incident = client.get("/api/v1/incidents").json()[0]
    response = client.post(
        "/api/v1/assistant/query",
        json={
            "query": "为什么推荐这个方案？",
            "asset_id": incident["asset_id"],
            "incident_id": incident["id"],
            "language": "zh-CN",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["reasoning_mode"] == "deterministic-domain-reasoning"
    assert "授权" in payload["safety_notice"]


def test_sqlite_store_persists_records(tmp_path: Path):
    database_url = f"sqlite:///{(tmp_path / 'forgeguard.db').as_posix()}"
    first = PersistentStore(database_url, tmp_path)
    seed_store(first)
    assert len(first.list_assets()) >= 5
    second = PersistentStore(database_url, tmp_path)
    assert second.get_asset("FG-BRG-001") is not None
    assert second.list_inventory()
