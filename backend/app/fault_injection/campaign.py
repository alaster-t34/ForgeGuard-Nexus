from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from app.bench.gateway import BenchGateway
from app.bench.schemas import BenchNodeRegistration, BenchSignalFrame, CalibrationRecord
from app.benchmark.schemas import FaultCampaignCase, FaultCampaignReport, WorkflowFaultCase
from app.domain.enums import AgentName
from app.fault_injection.signal import (
    PhysicalFault,
    SensorFault,
    generate_rotating_machine_signal,
    inject_sensor_fault,
)
from app.fault_injection.workflow import WorkflowFault, WorkflowFaultMode
from app.services.tools import ToolRegistry


class FaultCampaignRunner:
    def __init__(
        self,
        project_root: Path,
        bench: BenchGateway,
        tools: ToolRegistry,
    ) -> None:
        self.project_root = project_root
        self.bench = bench
        self.tools = tools
        self.output_dir = project_root / "artifacts" / "fault-campaigns"

    async def run(self, *, seed: int = 43) -> FaultCampaignReport:
        node_id = f"FAULT-CAMPAIGN-{seed}"
        self.bench.register(
            BenchNodeRegistration(
                node_id=node_id,
                asset_id="FG-BRG-001",
                name="Automated fault-injection campaign",
                transport="file",
                hardware="ForgeGuard deterministic signal harness",
                operating_system="portable Python",
                modalities=["vibration"],
                channels=["acceleration_x"],
                nominal_sample_rate_hz=12_000,
                sensor_position="simulated radial bearing-housing channel",
                sensor_mounting="physics-informed signal generator",
                calibration=CalibrationRecord(method="deterministic-generator", unit="g"),
            )
        )
        signal_cases: list[FaultCampaignCase] = []
        sequence = 0
        clean_faults = list(PhysicalFault)
        sensor_slices = [
            SensorFault.LOW_SNR,
            SensorFault.DROPOUT,
            SensorFault.DRIFT,
            SensorFault.CLIPPING,
            SensorFault.QUANTIZATION,
            SensorFault.SPEED_SHIFT,
            SensorFault.IMPULSE_INTERFERENCE,
        ]

        for physical_index, physical in enumerate(clean_faults):
            base = generate_rotating_machine_signal(
                physical,
                sample_rate_hz=12_000,
                duration_seconds=2048 / 12_000,
                rpm=1_650 + physical_index * 55,
                load_percent=62 + physical_index * 3,
                severity=0.0 if physical == PhysicalFault.NORMAL else 0.72,
                seed=seed * 1_000 + physical_index,
            )
            frame = BenchSignalFrame(
                node_id=node_id,
                asset_id="FG-BRG-001",
                sequence=sequence,
                sample_rate_hz=12_000,
                samples=base.tolist(),
                rpm=1_650 + physical_index * 55,
                load_percent=62 + physical_index * 3,
                open_incident=False,
                metadata={"campaign": "clean-physical-fault"},
            )
            analysis = await self.bench.ingest(frame)
            predicted = str(analysis.model_result.get("class_name", "unknown"))
            confidence = float(analysis.model_result.get("confidence", 0.0))
            signal_cases.append(
                FaultCampaignCase(
                    case_id=f"clean-{physical.value}",
                    physical_fault=physical.value,
                    sensor_fault=SensorFault.NONE.value,
                    predicted_label=predicted,
                    confidence=confidence,
                    quality_score=analysis.quality.score,
                    warnings=analysis.quality.warnings,
                    classification_correct=predicted == physical.value,
                    safety_gate_triggered=(
                        analysis.quality.score < 0.65 or confidence < 0.62
                    ),
                )
            )
            sequence += 1

        for sensor_index, sensor_fault in enumerate(sensor_slices):
            base = generate_rotating_machine_signal(
                PhysicalFault.NORMAL,
                sample_rate_hz=12_000,
                duration_seconds=2048 / 12_000,
                rpm=1_800,
                load_percent=70,
                severity=0.0,
                seed=seed * 2_000 + sensor_index,
            )
            corrupted = inject_sensor_fault(
                base,
                sensor_fault,
                severity=0.72,
                seed=seed * 3_000 + sensor_index,
            )
            frame = BenchSignalFrame(
                node_id=node_id,
                asset_id="FG-BRG-001",
                sequence=sequence,
                sample_rate_hz=12_000,
                samples=corrupted.tolist(),
                rpm=1_800,
                load_percent=70,
                open_incident=False,
                metadata={"campaign": "sensor-fault", "sensor_fault": sensor_fault.value},
            )
            analysis = await self.bench.ingest(frame)
            predicted = str(analysis.model_result.get("class_name", "unknown"))
            confidence = float(analysis.model_result.get("confidence", 0.0))
            safety_gate = (
                analysis.quality.score < 0.80
                or bool(analysis.quality.warnings)
                or confidence < 0.62
                or predicted != PhysicalFault.NORMAL.value
            )
            signal_cases.append(
                FaultCampaignCase(
                    case_id=f"sensor-{sensor_fault.value}",
                    physical_fault=PhysicalFault.NORMAL.value,
                    sensor_fault=sensor_fault.value,
                    predicted_label=predicted,
                    confidence=confidence,
                    quality_score=analysis.quality.score,
                    warnings=analysis.quality.warnings,
                    classification_correct=predicted == PhysicalFault.NORMAL.value,
                    safety_gate_triggered=safety_gate,
                )
            )
            sequence += 1

        workflow_cases: list[WorkflowFaultCase] = []
        for mode in WorkflowFaultMode:
            self.tools.inject_fault(
                WorkflowFault(
                    tool_name="inventory.query",
                    mode=mode,
                    remaining_calls=1,
                    delay_seconds=0.001,
                    message=f"fault-campaign-{mode.value}",
                )
            )
            record, result = await self.tools.call(
                "inventory.query",
                agent=AgentName.PLANNER,
                arguments={"part_numbers": ["6205-2RS-C3 bearing"]},
            )
            safely_contained = (
                record.status in {"failed", "succeeded"}
                and record.finished_at is not None
                and (mode == WorkflowFaultMode.EMPTY_RESULT or result is None)
            )
            workflow_cases.append(
                WorkflowFaultCase(
                    mode=mode.value,
                    tool_name="inventory.query",
                    recorded_status=record.status,
                    error=record.error,
                    safely_contained=safely_contained,
                )
            )
        self.tools.clear_fault()

        clean = [case for case in signal_cases if case.sensor_fault == SensorFault.NONE.value]
        corrupted = [case for case in signal_cases if case.sensor_fault != SensorFault.NONE.value]
        report = FaultCampaignReport(
            id=f"FCR-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
            signal_cases=signal_cases,
            workflow_cases=workflow_cases,
            clean_fault_accuracy=float(np.mean([case.classification_correct for case in clean])),
            corrupted_signal_safe_response_rate=float(
                np.mean([case.safety_gate_triggered for case in corrupted])
            ),
            workflow_containment_rate=float(
                np.mean([case.safely_contained for case in workflow_cases])
            ),
            artifact_paths={},
            limitations=[
                "Signal cases are deterministic fault injections, not destructive physical-rig faults.",
                "Physical injection and seeded-damage specimens must be reported separately.",
                "The campaign evaluates detection and containment, not permission to control equipment.",
            ],
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.output_dir / "latest.json"
        markdown_path = self.output_dir / "latest.md"
        report.artifact_paths = {
            "json": str(json_path.relative_to(self.project_root)),
            "markdown": str(markdown_path.relative_to(self.project_root)),
        }
        json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        markdown_path.write_text(self._markdown(report), encoding="utf-8")
        return report

    @staticmethod
    def _markdown(report: FaultCampaignReport) -> str:
        signal_rows = [
            "| Case | Physical | Sensor fault | Predicted | Confidence | Quality | Safe gate |",
            "|---|---|---|---|---:|---:|---:|",
        ]
        for case in report.signal_cases:
            signal_rows.append(
                f"| `{case.case_id}` | {case.physical_fault} | {case.sensor_fault} | "
                f"{case.predicted_label} | {case.confidence:.3f} | {case.quality_score:.3f} | "
                f"{'yes' if case.safety_gate_triggered else 'no'} |"
            )
        workflow_rows = [
            "| Tool fault | Status | Contained | Error |",
            "|---|---|---:|---|",
        ]
        for case in report.workflow_cases:
            workflow_rows.append(
                f"| {case.mode} | {case.recorded_status} | "
                f"{'yes' if case.safely_contained else 'no'} | {case.error or '-'} |"
            )
        return f"""# ForgeGuard fault-injection campaign

Run: `{report.id}`

- Clean physical-fault accuracy: **{report.clean_fault_accuracy:.3f}**
- Corrupted-signal safe-response rate: **{report.corrupted_signal_safe_response_rate:.3f}**
- Workflow-fault containment rate: **{report.workflow_containment_rate:.3f}**

## Signal campaign

{chr(10).join(signal_rows)}

## Workflow campaign

{chr(10).join(workflow_rows)}

## Boundary

This campaign uses reproducible signal and software fault injection. It is evidence for
regression and safety behavior, not a substitute for a physical test rig or a plant safety case.
"""
