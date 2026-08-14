from __future__ import annotations

from datetime import datetime, timezone

from app.domain.schemas import DemoScenarioRequest, IncidentInput, SensorSnapshot, VisionObservation
from app.services.scenario_catalog import get_scenario, list_scenarios


class ScenarioSimulator:
    def catalog(self) -> list[dict]:
        return list_scenarios()

    def incident_input(self, request: DemoScenarioRequest) -> IncidentInput:
        now = datetime.now(timezone.utc)
        scenario = get_scenario(request.scenario)
        telemetry = SensorSnapshot(timestamp=now, **scenario["telemetry"])
        vision_payload = scenario.get("vision")
        vision = None
        if vision_payload:
            vision = VisionObservation(
                image_id=f"demo_{scenario['id']}_{int(now.timestamp())}",
                source="scenario-library",
                region=(0.28, 0.2, 0.72, 0.76) if vision_payload.get("anomaly_score", 0) >= 0.55 else None,
                heatmap_uri=f"/demo/heatmaps/{scenario['id']}.svg" if vision_payload.get("anomaly_score", 0) >= 0.55 else None,
                **vision_payload,
            )
        return IncidentInput(
            asset_id=request.asset_id,
            summary=scenario["summary"],
            telemetry=telemetry,
            vision=vision,
            operator_note=scenario.get("operator_note"),
            scenario_key=scenario["id"],
            scenario_category=scenario["category"],
            simulation_only=True,
        )

    def post_maintenance_snapshot(self, scenario: str) -> tuple[SensorSnapshot, VisionObservation | None]:
        now = datetime.now(timezone.utc)
        definition = get_scenario(scenario)
        baseline = definition["telemetry"]
        telemetry = SensorSnapshot(
            timestamp=now,
            vibration_rms_g=max(0.45, min(0.92, baseline["vibration_rms_g"] * 0.28)),
            vibration_kurtosis=3.08,
            crest_factor=2.65,
            temperature_c=min(56.0, max(48.0, baseline["temperature_c"] - 22.0)),
            rotational_speed_rpm=baseline["rotational_speed_rpm"],
            load_percent=min(82.0, baseline["load_percent"]),
            acoustic_rms_db=max(52.0, baseline["acoustic_rms_db"] - 15.0),
            current_rms_a=max(2.5, baseline["current_rms_a"] * 0.86),
            energy_kw=max(4.0, baseline["energy_kw"] * 0.82),
            quality=0.99,
        )
        vision = VisionObservation(
            image_id=f"post_{scenario}_{int(now.timestamp())}",
            anomaly_score=0.1,
            class_name=None,
            confidence=0.96,
            region=None,
            source="post-maintenance-verification",
        )
        return telemetry, vision
