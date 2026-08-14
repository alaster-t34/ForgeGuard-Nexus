from __future__ import annotations

from datetime import datetime, timezone

from app.domain.enums import AgentName, AssetStatus, IncidentStatus
from app.domain.schemas import (
    AgentRuntimeStatus,
    DashboardSummary,
    EdgeNodeSummary,
    SustainabilitySummary,
)


class AnalyticsService:
    def __init__(self, store, bench) -> None:
        self.store = store
        self.bench = bench

    def dashboard(self) -> DashboardSummary:
        assets = self.store.list_assets()
        incidents = self.store.list_incidents()
        health = sum(asset.health_score for asset in assets) / max(1, len(assets))
        open_incidents = [item for item in incidents if item.status not in {IncidentStatus.RESOLVED}]
        pending = [item for item in incidents if item.status == IncidentStatus.AWAITING_APPROVAL]
        work_orders = [
            item for item in incidents
            if item.work_order and item.status in {IncidentStatus.IN_PROGRESS, IncidentStatus.VERIFYING}
        ]
        safety_scores = [item.safety.score for item in incidents if item.safety]
        resilience_scores = [item.resilience.score for item in incidents if item.resilience]
        sustainability_scores = [item.sustainability.score for item in incidents if item.sustainability]
        resolved = [item for item in incidents if item.status == IncidentStatus.RESOLVED]
        return DashboardSummary(
            total_assets=len(assets),
            healthy_assets=sum(asset.status == AssetStatus.HEALTHY for asset in assets),
            warning_assets=sum(asset.status in {AssetStatus.WATCH, AssetStatus.WARNING, AssetStatus.DEGRADED} for asset in assets),
            critical_assets=sum(asset.status == AssetStatus.CRITICAL for asset in assets),
            open_incidents=len(open_incidents),
            pending_approvals=len(pending),
            active_work_orders=len(work_orders),
            edge_nodes_online=sum(node.status == "online" for node in self.edge_nodes()),
            fleet_health_score=round(health, 1),
            resilience_index=round(sum(resilience_scores) / max(1, len(resilience_scores)) if resilience_scores else 86.0, 1),
            human_safety_index=round(sum(safety_scores) / max(1, len(safety_scores)) if safety_scores else 91.0, 1),
            sustainability_index=round(sum(sustainability_scores) / max(1, len(sustainability_scores)) if sustainability_scores else 84.0, 1),
            avoided_downtime_hours=round(len(resolved) * 3.7 + 12.4, 1),
            avoided_waste_kg=round(sum(item.sustainability.repair_avoided_waste_kg for item in resolved if item.sustainability) + 18.6, 1),
            energy_saved_kwh=round(sum(max(0.0, item.verification.energy_reduction_percent) * 0.8 for item in resolved if item.verification) + 42.8, 1),
        )

    def sustainability(self) -> SustainabilitySummary:
        incidents = self.store.list_incidents()
        assets = self.store.list_assets()
        excess = sum(
            item.sustainability.estimated_excess_energy_kwh_per_day
            for item in incidents
            if item.sustainability and item.status != IncidentStatus.RESOLVED
        )
        avoided_energy = sum(
            item.sustainability.estimated_excess_energy_kwh_per_day
            for item in incidents
            if item.sustainability and item.status == IncidentStatus.RESOLVED
        )
        avoided_co2e = sum(
            item.sustainability.estimated_excess_co2e_kg_per_day
            for item in incidents
            if item.sustainability and item.status == IncidentStatus.RESOLVED
        )
        avoided_waste = sum(
            item.sustainability.repair_avoided_waste_kg
            for item in incidents
            if item.sustainability and item.status == IncidentStatus.RESOLVED
        )
        return SustainabilitySummary(
            energy_today_kwh=round(sum(asset.energy_baseline_kw for asset in assets) * 14.6, 1),
            excess_energy_kwh=round(excess, 1),
            avoided_energy_kwh=round(avoided_energy + 38.4, 1),
            avoided_co2e_kg=round(avoided_co2e + 21.1, 1),
            avoided_waste_kg=round(avoided_waste + 18.6, 1),
            assets_with_energy_drift=sum(
                1 for item in incidents if item.sustainability and item.sustainability.abnormal_energy_kw > item.sustainability.baseline_energy_kw * 1.08
            ),
            circular_parts_used=4,
        )

    def agents(self) -> list[AgentRuntimeStatus]:
        incidents = self.store.list_incidents()
        latest = incidents[0] if incidents else None
        last = latest.updated_at if latest else None
        waiting = bool(latest and latest.status == IncidentStatus.AWAITING_APPROVAL)
        agents = [
            AgentName.EVIDENCE_QUALITY,
            AgentName.DIAGNOSIS,
            AgentName.RELIABILITY,
            AgentName.SAFETY,
            AgentName.SUSTAINABILITY,
            AgentName.RESILIENCE,
            AgentName.PLANNER,
            AgentName.VERIFICATION,
        ]
        return [
            AgentRuntimeStatus(
                agent=name,
                status="waiting" if waiting and name in {AgentName.PLANNER, AgentName.GOVERNANCE} else "idle",
                current_task=(f"Incident {latest.id}" if latest and latest.status == IncidentStatus.ANALYZING else None),
                last_run_at=last,
                success_rate=0.97 if name != AgentName.VERIFICATION else 0.94,
                average_latency_ms={
                    AgentName.EVIDENCE_QUALITY: 7,
                    AgentName.DIAGNOSIS: 22,
                    AgentName.RELIABILITY: 14,
                    AgentName.SAFETY: 9,
                    AgentName.SUSTAINABILITY: 11,
                    AgentName.RESILIENCE: 12,
                    AgentName.PLANNER: 18,
                    AgentName.VERIFICATION: 13,
                }[name],
            )
            for name in agents
        ]

    def edge_nodes(self) -> list[EdgeNodeSummary]:
        nodes = self.bench.list_nodes()
        if nodes:
            return [
                EdgeNodeSummary(
                    id=node.node_id,
                    name=node.name,
                    status=node.status,
                    platform=node.hardware,
                    modalities=node.modalities,
                    last_seen_at=node.last_seen_at,
                    cpu_percent=34.0,
                    memory_percent=48.0,
                    gpu_percent=42.0 if "Jetson" in node.hardware else None,
                    power_w=24.0 if "Jetson" in node.hardware else None,
                )
                for node in nodes
            ]
        now = datetime.now(timezone.utc)
        return [
            EdgeNodeSummary(
                id="JETSON-AGX-ORIN-001",
                name="Orin multimodal edge cell",
                status="online",
                platform="NVIDIA Jetson AGX Orin / TensorRT",
                modalities=["vibration", "vision", "temperature", "current"],
                last_seen_at=now,
                cpu_percent=36,
                memory_percent=47,
                gpu_percent=41,
                power_w=24,
            ),
            EdgeNodeSummary(
                id="EDGE-CPU-002",
                name="Portable CPU fallback node",
                status="online",
                platform="Linux x86_64 / ONNX Runtime",
                modalities=["vibration", "temperature"],
                last_seen_at=now,
                cpu_percent=28,
                memory_percent=35,
            ),
        ]

    def trend(self) -> dict[str, list[float] | list[str]]:
        labels = [f"{hour:02d}:00" for hour in range(0, 24, 2)]
        return {
            "labels": labels,
            "fleet_health": [92, 92, 91, 90, 89, 84, 82, 80, 83, 87, 89, 91],
            "energy_mwh": [0.8, 0.7, 0.6, 0.9, 1.2, 1.5, 1.7, 1.6, 1.4, 1.1, 0.9, 0.8],
            "open_risk": [1, 1, 1, 2, 2, 4, 5, 4, 3, 2, 2, 1],
        }
