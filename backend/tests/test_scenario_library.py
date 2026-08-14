from fastapi.testclient import TestClient

from app.bootstrap import seed_store
from app.main import app
from app.runtime import runtime

client = TestClient(app)


def setup_function():
    runtime.store.reset()
    seed_store(runtime.store)


def test_scenario_catalog_is_large_and_structured():
    response = client.get('/api/v1/demo/scenarios')
    assert response.status_code == 200
    scenarios = response.json()
    assert len(scenarios) >= 20
    ids = {item['id'] for item in scenarios}
    assert {'outer_race_spall', 'pump_cavitation', 'electrical_unbalance', 'sensor_conflict', 'supply_constraint'} <= ids
    assert all(item['name'] and item['category'] and item['description'] for item in scenarios)


def test_representative_scenarios_enter_governed_loop():
    for scenario in ['shaft_misalignment', 'pump_cavitation', 'energy_drift', 'sensor_conflict']:
        response = client.post('/api/v1/demo/run', json={'scenario': scenario, 'asset_id': 'FG-BRG-001'})
        assert response.status_code == 200, response.text
        incident = response.json()
        assert incident['input']['scenario_key'] == scenario
        assert incident['diagnosis']['primary']['fault_mode']
        assert incident['safety']['approval_required'] is True
        assert incident['plan']['options']


def test_unknown_scenario_is_rejected():
    response = client.post('/api/v1/demo/run', json={'scenario': 'not-a-real-scenario', 'asset_id': 'FG-BRG-001'})
    assert response.status_code in {400, 422, 500}
