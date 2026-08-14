from __future__ import annotations

import csv
import io
import json
import math
from collections import Counter
from datetime import datetime, timezone
from itertools import chain
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

import numpy as np

from app.csv_policy import ANALYSIS_CSV_POLICY, decode_csv_bytes, ensure_csv_size, sniff_csv_dialect
from app.analysis.schemas import (
    CsvAnalysisReport,
    CsvWindowResult,
    LiveFrameInput,
    LiveHistoryPoint,
    LiveSessionCreate,
    LiveSessionState,
    LiveSimulationInput,
)
from app.bench.schemas import BenchNodeRegistration, BenchSignalFrame, CalibrationRecord
from app.fault_injection.signal import (
    PhysicalFault,
    SensorFault,
    generate_rotating_machine_signal,
    inject_sensor_fault,
)


class IndustrialDataAnalysisService:
    """Shared service for real-time frame processing and historical CSV analysis.

    Both paths use the same BenchGateway quality gate, feature extraction and model
    registry. This prevents the UI from showing two unrelated analysis systems.
    """

    def __init__(self, bench, orchestrator, project_root: Path) -> None:
        self.bench = bench
        self.orchestrator = orchestrator
        self.project_root = Path(project_root)
        self.report_dir = self.project_root / "runtime-data" / "analysis-reports"
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, LiveSessionState] = {}
        self._lock = RLock()

    def list_live_sessions(self) -> list[LiveSessionState]:
        with self._lock:
            return sorted(
                (item.model_copy(deep=True) for item in self._sessions.values()),
                key=lambda item: item.started_at,
                reverse=True,
            )

    def get_live_session(self, session_id: str) -> LiveSessionState:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(f"Unknown live session: {session_id}")
            return session.model_copy(deep=True)

    def start_live_session(self, payload: LiveSessionCreate) -> LiveSessionState:
        session_id = f"live_{uuid4().hex[:12]}"
        node_id = payload.node_id or f"LIVE-{uuid4().hex[:10].upper()}"
        registration = BenchNodeRegistration(
            node_id=node_id,
            asset_id=payload.asset_id,
            name=payload.name,
            transport="http" if payload.source == "external" else "custom",
            hardware="External sensor/gateway" if payload.source == "external" else "ForgeGuard live signal simulator",
            operating_system="user supplied" if payload.source == "external" else "ForgeGuard runtime",
            modalities=["vibration"],
            channels=["acceleration_x"],
            nominal_sample_rate_hz=payload.sample_rate_hz,
            sensor_position="drive-end bearing radial position",
            sensor_mounting="configured by operator",
            calibration=CalibrationRecord(method="operator supplied or replay metadata"),
            metadata={"live_session_id": session_id, "source": payload.source},
        )
        self.bench.register(registration)
        session = LiveSessionState(
            id=session_id,
            node_id=node_id,
            asset_id=payload.asset_id,
            name=payload.name,
            source=payload.source,
            sample_rate_hz=payload.sample_rate_hz,
            rpm=payload.rpm,
            load_percent=payload.load_percent,
            open_incident=payload.open_incident,
        )
        with self._lock:
            self._sessions[session_id] = session
        return session.model_copy(deep=True)

    def stop_live_session(self, session_id: str) -> LiveSessionState:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(f"Unknown live session: {session_id}")
            session.status = "stopped"
            session.stopped_at = datetime.now(timezone.utc)
            return session.model_copy(deep=True)

    async def ingest_live_frame(self, session_id: str, payload: LiveFrameInput) -> LiveSessionState:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(f"Unknown live session: {session_id}")
            if session.status == "stopped":
                raise ValueError("The live session has been stopped")
            sequence = session.total_frames
            rpm = payload.rpm if payload.rpm is not None else session.rpm
            load = payload.load_percent if payload.load_percent is not None else session.load_percent
            node_id = session.node_id
            asset_id = session.asset_id
            sample_rate = session.sample_rate_hz

        frame = BenchSignalFrame(
            node_id=node_id,
            asset_id=asset_id,
            timestamp=payload.timestamp,
            sequence=sequence,
            sample_rate_hz=sample_rate,
            samples=payload.samples,
            rpm=rpm,
            load_percent=load,
            temperature_c=payload.temperature_c,
            metadata={**payload.metadata, "live_session_id": session_id},
            open_incident=False,
        )
        analysis = await self.bench.ingest(frame)
        predicted = str(analysis.model_result.get("class_name", "unknown"))
        confidence = float(analysis.model_result.get("confidence", 0.0))
        anomaly = float(analysis.model_result.get("anomaly_probability", 0.0))
        incident_id: str | None = None

        with self._lock:
            current = self._sessions[session_id]
            should_open = (
                current.open_incident
                and current.incident_id is None
                and analysis.accepted
                and (predicted not in {"", "normal"} or anomaly >= 0.45)
            )

        if should_open:
            incident_input = self.bench.to_incident_input(frame, analysis)
            incident = await self.orchestrator.create_and_analyze(incident_input)
            incident_id = incident.id

        history_point = LiveHistoryPoint(
            sequence=sequence,
            timestamp=analysis.processed_at,
            accepted=analysis.accepted,
            quality_score=analysis.quality.score,
            predicted_class=predicted,
            confidence=confidence,
            anomaly_probability=anomaly,
            rms=float(analysis.features.get("rms", 0.0)),
            kurtosis=float(analysis.features.get("kurtosis", 0.0)),
            incident_id=incident_id,
        )
        preview = self._preview(np.asarray(payload.samples, dtype=np.float32), 180)
        with self._lock:
            current = self._sessions[session_id]
            current.total_frames += 1
            if analysis.accepted:
                current.accepted_frames += 1
            else:
                current.rejected_frames += 1
                current.status = "degraded"
            if incident_id:
                current.incident_id = incident_id
            current.last_analysis = analysis.model_dump(mode="json")
            current.waveform_preview = preview
            current.history = (current.history + [history_point])[-120:]
            return current.model_copy(deep=True)

    async def simulate_live_frame(self, session_id: str, payload: LiveSimulationInput) -> LiveSessionState:
        session = self.get_live_session(session_id)
        physical = PhysicalFault(payload.fault_mode)
        sensor_fault = SensorFault(payload.sensor_fault)
        seed = session.total_frames + 41
        samples = generate_rotating_machine_signal(
            physical,
            sample_rate_hz=session.sample_rate_hz,
            duration_seconds=payload.duration_seconds,
            rpm=session.rpm,
            load_percent=session.load_percent,
            severity=payload.severity,
            seed=seed,
        )
        samples = inject_sensor_fault(
            samples,
            sensor_fault,
            severity=payload.severity,
            seed=seed + 1000,
        )
        return await self.ingest_live_frame(
            session_id,
            LiveFrameInput(
                samples=np.asarray(samples, dtype=np.float32).tolist(),
                rpm=session.rpm,
                load_percent=session.load_percent,
                temperature_c=35.0 + payload.severity * 22.0,
                metadata={
                    "source": "forgeguard-live-simulator",
                    "fault_mode": payload.fault_mode,
                    "sensor_fault": payload.sensor_fault,
                    "synthetic": True,
                },
            ),
        )

    async def analyze_csv(
        self,
        *,
        file_name: str,
        content: bytes,
        asset_id: str,
        sample_rate_hz: float,
        rpm: float,
        load_percent: float,
        signal_column: str | None,
        window_size: int,
        hop_size: int,
        create_incident: bool,
    ) -> CsvAnalysisReport:
        ensure_csv_size(len(content), ANALYSIS_CSV_POLICY)
        if window_size < 64 or window_size > 262_144:
            raise ValueError("window_size must be between 64 and 262144")
        if hop_size < 1 or hop_size > window_size:
            raise ValueError("hop_size must be between 1 and window_size")

        samples, selected_column, parse_warnings = self._parse_csv(content, signal_column)
        if samples.size < 64:
            raise ValueError("CSV does not contain at least 64 finite numeric samples")

        report_id = f"csv_{uuid4().hex[:12]}"
        node_id = f"CSV-{uuid4().hex[:10].upper()}"
        self.bench.register(
            BenchNodeRegistration(
                node_id=node_id,
                asset_id=asset_id,
                name=f"CSV analysis: {file_name}",
                transport="file",
                hardware="Historical CSV file",
                operating_system="ForgeGuard analysis runtime",
                modalities=["vibration"],
                channels=[selected_column],
                nominal_sample_rate_hz=sample_rate_hz,
                sensor_position="declared in CSV analysis form",
                sensor_mounting="historical data; verify source metadata",
                calibration=CalibrationRecord(method="historical data metadata not independently verified"),
                metadata={"analysis_report_id": report_id, "file_name": file_name},
            )
        )

        windows: list[CsvWindowResult] = []
        raw_analyses: list[tuple[BenchSignalFrame, Any]] = []
        starts = list(range(0, max(samples.size - window_size + 1, 1), hop_size))
        if not starts or starts[-1] + window_size < samples.size:
            starts.append(max(0, samples.size - window_size))
        starts = sorted(set(starts))

        for sequence, start in enumerate(starts):
            chunk = samples[start : start + window_size]
            if chunk.size < 64:
                continue
            frame = BenchSignalFrame(
                node_id=node_id,
                asset_id=asset_id,
                sequence=sequence,
                sample_rate_hz=sample_rate_hz,
                samples=chunk.astype(np.float32).tolist(),
                rpm=rpm,
                load_percent=load_percent,
                metadata={
                    "source": "csv-upload",
                    "file_name": file_name,
                    "signal_column": selected_column,
                    "start_sample": start,
                    "analysis_report_id": report_id,
                },
                open_incident=False,
            )
            analysis = await self.bench.ingest(frame)
            predicted = str(analysis.model_result.get("class_name", "unknown"))
            confidence = float(analysis.model_result.get("confidence", 0.0))
            anomaly = float(analysis.model_result.get("anomaly_probability", 0.0))
            windows.append(
                CsvWindowResult(
                    sequence=sequence,
                    start_sample=start,
                    end_sample=start + int(chunk.size),
                    timestamp_seconds=start / sample_rate_hz,
                    accepted=analysis.accepted,
                    quality_score=analysis.quality.score,
                    predicted_class=predicted,
                    confidence=confidence,
                    anomaly_probability=anomaly,
                    rms=float(analysis.features.get("rms", 0.0)),
                    kurtosis=float(analysis.features.get("kurtosis", 0.0)),
                    warnings=list(analysis.quality.warnings),
                )
            )
            raw_analyses.append((frame, analysis))

        if not windows:
            raise ValueError("No valid analysis window could be generated from the CSV")

        accepted = [item for item in windows if item.accepted]
        distribution = Counter(item.predicted_class for item in accepted)
        if distribution:
            dominant = distribution.most_common(1)[0][0]
        else:
            dominant = "rejected_by_quality_gate"

        incident_id: str | None = None
        if create_incident:
            candidates = [
                (frame, analysis)
                for frame, analysis in raw_analyses
                if analysis.accepted
                and (
                    str(analysis.model_result.get("class_name", "normal")) != "normal"
                    or float(analysis.model_result.get("anomaly_probability", 0.0)) >= 0.45
                )
            ]
            if candidates:
                frame, analysis = max(
                    candidates,
                    key=lambda pair: float(pair[1].model_result.get("anomaly_probability", 0.0)),
                )
                incident = await self.orchestrator.create_and_analyze(
                    self.bench.to_incident_input(frame, analysis)
                )
                incident_id = incident.id

        report = CsvAnalysisReport(
            id=report_id,
            file_name=file_name,
            asset_id=asset_id,
            signal_column=selected_column,
            sample_rate_hz=sample_rate_hz,
            rpm=rpm,
            load_percent=load_percent,
            total_samples=int(samples.size),
            duration_seconds=float(samples.size / sample_rate_hz),
            window_size=window_size,
            hop_size=hop_size,
            total_windows=len(windows),
            accepted_windows=len(accepted),
            rejected_windows=len(windows) - len(accepted),
            dominant_class=dominant,
            class_distribution=dict(distribution),
            average_quality=float(np.mean([item.quality_score for item in windows])),
            maximum_anomaly_probability=float(max(item.anomaly_probability for item in windows)),
            incident_id=incident_id,
            waveform_preview=self._preview(samples, 300),
            windows=windows,
            warnings=parse_warnings,
        )
        (self.report_dir / f"{report.id}.json").write_text(
            report.model_dump_json(indent=2),
            encoding="utf-8",
        )
        return report

    def list_csv_reports(self, limit: int = 20) -> list[CsvAnalysisReport]:
        reports: list[CsvAnalysisReport] = []
        for path in sorted(self.report_dir.glob("csv_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
            try:
                reports.append(CsvAnalysisReport.model_validate_json(path.read_text(encoding="utf-8")))
            except (ValueError, OSError):
                continue
        return reports

    @staticmethod
    def _preview(samples: np.ndarray, points: int) -> list[float]:
        values = np.asarray(samples, dtype=np.float32).reshape(-1)
        if values.size <= points:
            return values.tolist()
        indices = np.linspace(0, values.size - 1, points).astype(np.int64)
        return values[indices].tolist()

    @classmethod
    def _parse_csv(cls, content: bytes, requested_column: str | None) -> tuple[np.ndarray, str, list[str]]:
        policy = ANALYSIS_CSV_POLICY
        text, detected_encoding = decode_csv_bytes(content, policy)
        dialect = sniff_csv_dialect(text, policy)
        csv.field_size_limit(policy.max_cell_characters)

        def numeric(value: str) -> bool:
            try:
                return math.isfinite(float(value.strip()))
            except (TypeError, ValueError):
                return False

        def normalized(value: str) -> str:
            return "".join(character for character in value.casefold() if character.isalnum())

        def iter_rows():
            try:
                for row in csv.reader(io.StringIO(text), dialect):
                    if not any(cell.strip() for cell in row):
                        continue
                    if len(row) > policy.max_columns:
                        raise ValueError(
                            f"CSV has {len(row)} columns; the limit is {policy.max_columns}"
                        )
                    if any(len(cell) > policy.max_cell_characters for cell in row):
                        raise ValueError(
                            f"CSV cell exceeds the {policy.max_cell_characters}-character limit"
                        )
                    yield row
            except csv.Error as exc:
                raise ValueError(f"CSV format error: {exc}") from exc

        first_pass = iter_rows()
        first = next(first_pass, None)
        if first is None:
            raise ValueError("CSV file is empty")
        has_header = not all(numeric(cell) for cell in first)
        headers = (
            [cell.strip() or f"column_{index}" for index, cell in enumerate(first)]
            if has_header
            else [f"column_{index}" for index in range(len(first))]
        )
        if not headers:
            raise ValueError("CSV does not contain any columns")

        numeric_counts = [0] * len(headers)
        data_row_count = 0
        ragged_rows = 0

        def inspect_row(row: list[str]) -> None:
            nonlocal data_row_count, ragged_rows
            data_row_count += 1
            if data_row_count > policy.max_rows:
                raise ValueError(f"CSV exceeds the {policy.max_rows:,}-row analysis limit")
            if len(row) != len(headers):
                ragged_rows += 1
            for index in range(len(headers)):
                if index < len(row) and numeric(row[index]):
                    numeric_counts[index] += 1

        if not has_header:
            inspect_row(first)
        for row in first_pass:
            inspect_row(row)
        if data_row_count == 0:
            raise ValueError("CSV contains a header but no data rows")

        column_index: int | None = None
        selected = requested_column.strip() if requested_column else ""
        if selected:
            if selected in headers:
                column_index = headers.index(selected)
            else:
                folded = normalized(selected)
                folded_headers = [normalized(header) for header in headers]
                if folded in folded_headers:
                    column_index = folded_headers.index(folded)
                try:
                    candidate = int(selected)
                    if 0 <= candidate < len(headers):
                        column_index = candidate
                except ValueError:
                    pass
            if column_index is None:
                raise ValueError(f"Signal column '{selected}' was not found. Available columns: {', '.join(headers)}")
        else:
            preferred_names = (
                "acceleration_x",
                "acceleration",
                "vibration",
                "signal",
                "amplitude",
                "sensor_value",
                "value",
                "ch1",
            )
            normalized_headers = [normalized(header) for header in headers]
            for preferred in preferred_names:
                candidate = normalized(preferred)
                if candidate in normalized_headers:
                    possible = normalized_headers.index(candidate)
                    if numeric_counts[possible] > 0:
                        column_index = possible
                        break
            if column_index is None:
                if max(numeric_counts, default=0) == 0:
                    raise ValueError("CSV does not contain a finite numeric column")
                column_index = max(
                    range(len(headers)),
                    key=lambda index: (numeric_counts[index], index),
                )
            selected = headers[column_index]

        values: list[float] = []
        skipped = 0
        second_pass = iter_rows()
        next(second_pass, None)
        if not has_header:
            second_pass = chain((first,), second_pass)
        for row in second_pass:
            if column_index >= len(row) or not numeric(row[column_index]):
                skipped += 1
                continue
            values.append(float(row[column_index].strip()))
        warnings = [
            f"Detected {detected_encoding} encoding and {repr(dialect.delimiter)} delimiter"
        ]
        if skipped:
            warnings.append(f"Skipped {skipped} rows with empty or non-numeric signal values")
        if ragged_rows:
            warnings.append(f"Detected {ragged_rows} rows with a different column count")
        if has_header and "sampleid" in {normalized(header) for header in headers}:
            warnings.append(
                "A sample_id column was detected. Rows are analyzed as one continuous signal; "
                "filter one sample_id at a time to prevent windows crossing waveform boundaries"
            )
        if not has_header:
            warnings.append("No header row detected; the signal column was selected by numeric coverage")
        return np.asarray(values, dtype=np.float32), selected, warnings
