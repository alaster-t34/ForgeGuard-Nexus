from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from app.analysis.schemas import (
    CsvAnalysisReport,
    LiveFrameInput,
    LiveSessionCreate,
    LiveSessionState,
    LiveSimulationInput,
)
from app.bench.schemas import (
    BenchFrameAnalysis,
    BenchNodeRegistration,
    BenchNodeState,
    BenchSignalFrame,
    RigCampaignRegistration,
    RigCampaignState,
)
from app.benchmark.features import extract_vibration_features
from app.benchmark.schemas import (
    BenchmarkReport,
    BenchmarkRunRequest,
    FaultInjectionRequest,
    FaultCampaignReport,
    FaultInjectionResult,
    WorkflowFaultRequest,
)
from app.config import get_settings
from app.csv_policy import ANALYSIS_CSV_POLICY, csv_policy_catalog
from app.domain.schemas import (
    ApprovalRequest,
    AssistantRequest,
    AssistantResponse,
    DashboardSummary,
    SustainabilitySummary,
    DemoScenarioRequest,
    HealthResponse,
    IncidentInput,
    IncidentRecord,
    SearchResult,
    VerificationRequest,
)
from app.fault_injection.campaign import FaultCampaignRunner
from app.fault_injection.signal import (
    PhysicalFault,
    SensorFault,
    fault_catalog,
    generate_rotating_machine_signal,
    inject_sensor_fault,
)
from app.fault_injection.workflow import WorkflowFault, WorkflowFaultMode
from app.runtime import runtime
from app.bootstrap import seed_store
from app.services.platform_status import platform_status

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", app=get_settings().app_name, version=get_settings().app_version)


@router.get("/system/status")
async def get_system_status():
    return platform_status()




@router.get("/analysis/live/sessions", response_model=list[LiveSessionState])
async def list_live_sessions() -> list[LiveSessionState]:
    return runtime.analysis.list_live_sessions()


@router.post("/analysis/live/sessions", response_model=LiveSessionState, status_code=status.HTTP_201_CREATED)
async def start_live_session(payload: LiveSessionCreate) -> LiveSessionState:
    try:
        if runtime.store.get_asset(payload.asset_id) is None:
            raise KeyError(f"Unknown asset: {payload.asset_id}")
        return runtime.analysis.start_live_session(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/analysis/live/sessions/{session_id}", response_model=LiveSessionState)
async def get_live_session(session_id: str) -> LiveSessionState:
    try:
        return runtime.analysis.get_live_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/analysis/live/sessions/{session_id}", response_model=LiveSessionState)
async def stop_live_session(session_id: str) -> LiveSessionState:
    try:
        return runtime.analysis.stop_live_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/analysis/live/sessions/{session_id}/frames", response_model=LiveSessionState)
async def ingest_live_frame(session_id: str, payload: LiveFrameInput) -> LiveSessionState:
    try:
        return await runtime.analysis.ingest_live_frame(session_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/analysis/live/sessions/{session_id}/simulate", response_model=LiveSessionState)
async def simulate_live_frame(session_id: str, payload: LiveSimulationInput) -> LiveSessionState:
    try:
        return await runtime.analysis.simulate_live_frame(session_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/analysis/csv/reports", response_model=list[CsvAnalysisReport])
async def list_csv_analysis_reports(limit: int = Query(default=20, ge=1, le=100)) -> list[CsvAnalysisReport]:
    return runtime.analysis.list_csv_reports(limit=limit)


@router.get("/analysis/csv/limits")
async def csv_limits():
    return csv_policy_catalog()


@router.post("/analysis/csv", response_model=CsvAnalysisReport)
async def analyze_csv_file(
    file: UploadFile = File(...),
    asset_id: str = Form(default="FG-BRG-001"),
    signal_column: str = Form(default=""),
    sample_rate_hz: float = Form(default=12000.0),
    rpm: float = Form(default=1800.0),
    load_percent: float = Form(default=70.0),
    window_size: int = Form(default=2048),
    hop_size: int = Form(default=1024),
    create_incident: bool = Form(default=True),
) -> CsvAnalysisReport:
    try:
        if runtime.store.get_asset(asset_id) is None:
            raise KeyError(f"Unknown asset: {asset_id}")
        file_name = file.filename or "uploaded.csv"
        suffix = Path(file_name).suffix.casefold()
        if suffix not in {"", ".csv", ".txt"}:
            raise ValueError("Historical analysis accepts .csv or .txt files")
        content = await file.read(ANALYSIS_CSV_POLICY.max_bytes + 1)
        if len(content) > ANALYSIS_CSV_POLICY.max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    f"CSV file exceeds the "
                    f"{ANALYSIS_CSV_POLICY.max_bytes // (1024 * 1024)} MB analysis limit"
                ),
            )
        return await runtime.analysis.analyze_csv(
            file_name=file_name,
            content=content,
            asset_id=asset_id,
            sample_rate_hz=sample_rate_hz,
            rpm=rpm,
            load_percent=load_percent,
            signal_column=signal_column or None,
            window_size=window_size,
            hop_size=hop_size,
            create_incident=create_incident,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/assets")
async def list_assets():
    return runtime.store.list_assets()


@router.get("/incidents", response_model=list[IncidentRecord])
async def list_incidents() -> list[IncidentRecord]:
    return runtime.store.list_incidents()


@router.get("/incidents/{incident_id}", response_model=IncidentRecord)
async def get_incident(incident_id: str) -> IncidentRecord:
    incident = runtime.store.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.post("/incidents", response_model=IncidentRecord, status_code=status.HTTP_201_CREATED)
async def create_incident(payload: IncidentInput) -> IncidentRecord:
    try:
        return await runtime.orchestrator.create_and_analyze(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/incidents/{incident_id}/approve", response_model=IncidentRecord)
async def approve_incident(incident_id: str, payload: ApprovalRequest) -> IncidentRecord:
    try:
        return await runtime.orchestrator.approve(incident_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/incidents/{incident_id}/verify", response_model=IncidentRecord)
async def verify_incident(incident_id: str, payload: VerificationRequest) -> IncidentRecord:
    try:
        return await runtime.orchestrator.verify(incident_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/demo/scenarios")
async def list_demo_scenarios():
    """Return the governed scenario library used by the competition demo UI."""
    return runtime.simulator.catalog()


@router.post("/demo/reset")
async def reset_demo():
    runtime.store.reset()
    seed_store(runtime.store)
    return {"status": "reset", "assets": len(runtime.store.list_assets()), "incidents": 0}


@router.post("/demo/run", response_model=IncidentRecord)
async def run_demo(payload: DemoScenarioRequest) -> IncidentRecord:
    try:
        incident_input = runtime.simulator.incident_input(payload)
        return await runtime.orchestrator.create_and_analyze(incident_input)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/demo/{incident_id}/complete", response_model=IncidentRecord)
async def complete_demo(incident_id: str, scenario: str = Query(default="outer_race_spall")) -> IncidentRecord:
    incident = runtime.store.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if incident.status.value == "awaiting_approval":
        incident = await runtime.orchestrator.approve(
            incident_id,
            ApprovalRequest(
                option_id=incident.plan.recommended_option_id if incident.plan else "replace-now",
                approved_by="Demo Safety Officer",
                comment="Approved for controlled competition demonstration.",
            ),
        )
    telemetry, vision = runtime.simulator.post_maintenance_snapshot(scenario)
    return await runtime.orchestrator.verify(
        incident.id,
        VerificationRequest(
            telemetry=telemetry,
            vision=vision,
            technician_note="Bearing replaced and torque verified.",
        ),
    )


@router.get("/research/search", response_model=SearchResult)
async def research_search(
    q: str = Query(min_length=3, max_length=500),
    purpose: str = Query(default="industrial maintenance evidence"),
    scope: str = Query(default="all", pattern="^(internal|academic|web|all)$"),
) -> SearchResult:
    try:
        return await runtime.search.search(q, purpose=purpose, scope=scope)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/tools")
async def list_tools():
    return runtime.tools.catalog()


@router.get("/models")
async def list_models():
    return runtime.models.catalog()


@router.post("/bench/nodes", response_model=BenchNodeState, status_code=status.HTTP_201_CREATED)
async def register_bench_node(payload: BenchNodeRegistration) -> BenchNodeState:
    try:
        return runtime.bench.register(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/bench/nodes", response_model=list[BenchNodeState])
async def list_bench_nodes() -> list[BenchNodeState]:
    return runtime.bench.list_nodes()


@router.post(
    "/bench/campaigns",
    response_model=RigCampaignState,
    status_code=status.HTTP_201_CREATED,
)
async def register_rig_campaign(payload: RigCampaignRegistration) -> RigCampaignState:
    try:
        return runtime.bench.register_campaign(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/bench/campaigns", response_model=list[RigCampaignState])
async def list_rig_campaigns() -> list[RigCampaignState]:
    return runtime.bench.list_campaigns()


@router.post("/bench/frames", response_model=BenchFrameAnalysis)
async def ingest_bench_frame(payload: BenchSignalFrame) -> BenchFrameAnalysis:
    try:
        analysis = await runtime.bench.ingest(payload)
        predicted = str(analysis.model_result.get("class_name", ""))
        anomaly_probability = float(analysis.model_result.get("anomaly_probability", 0.0))
        should_open = payload.open_incident and (predicted not in {"", "normal"} or anomaly_probability >= 0.45)
        if should_open and analysis.accepted:
            incident_input = runtime.bench.to_incident_input(payload, analysis)
            incident = await runtime.orchestrator.create_and_analyze(incident_input)
            analysis.incident_id = incident.id
        return analysis
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/benchmarks/run", response_model=BenchmarkReport)
async def run_model_benchmark(payload: BenchmarkRunRequest) -> BenchmarkReport:
    return await run_in_threadpool(runtime.benchmark.run, payload)


@router.get("/benchmarks/latest", response_model=BenchmarkReport | None)
async def latest_model_benchmark() -> BenchmarkReport | None:
    return runtime.benchmark.load_latest()


@router.get("/benchmarks/datasets")
async def benchmark_dataset_manifest():
    manifest = runtime.benchmark.manifest()
    if manifest is None:
        raise HTTPException(status_code=404, detail="OpenEval manifest has not been built")
    return manifest


@router.get("/fault-injection/catalog")
async def get_fault_catalog():
    return {"signal_faults": fault_catalog(), "workflow_faults": runtime.tools.active_faults()}


@router.post("/fault-injection/signal", response_model=FaultInjectionResult)
async def inject_signal_fault(payload: FaultInjectionRequest) -> FaultInjectionResult:
    try:
        base = generate_rotating_machine_signal(
            PhysicalFault(payload.physical_fault),
            sample_rate_hz=payload.sample_rate_hz,
            duration_seconds=payload.duration_seconds,
            rpm=payload.rpm,
            load_percent=payload.load_percent,
            severity=payload.physical_severity,
            seed=payload.seed,
        )
        injected = inject_sensor_fault(
            base,
            SensorFault(payload.sensor_fault),
            severity=payload.sensor_severity,
            seed=payload.seed + 1,
        )
        features = extract_vibration_features(injected, payload.sample_rate_hz)
        return FaultInjectionResult(
            samples=injected.tolist(),
            features=dict(features),
            metadata={
                "physical_fault": payload.physical_fault,
                "sensor_fault": payload.sensor_fault,
                "sample_rate_hz": payload.sample_rate_hz,
                "rpm": payload.rpm,
                "load_percent": payload.load_percent,
                "seed": payload.seed,
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/fault-injection/workflow")
async def inject_workflow_fault(payload: WorkflowFaultRequest):
    try:
        runtime.tools.inject_fault(
            WorkflowFault(
                tool_name=payload.tool_name,
                mode=WorkflowFaultMode(payload.mode),
                remaining_calls=payload.remaining_calls,
                delay_seconds=payload.delay_seconds,
                message=payload.message,
            )
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"active_faults": runtime.tools.active_faults()}


@router.delete("/fault-injection/workflow")
async def clear_workflow_fault(tool_name: str | None = None):
    runtime.tools.clear_fault(tool_name)
    return {"active_faults": runtime.tools.active_faults()}


@router.post("/fault-injection/campaign", response_model=FaultCampaignReport)
async def run_fault_campaign(seed: int = 43) -> FaultCampaignReport:
    runner = FaultCampaignRunner(runtime.benchmark.project_root, runtime.bench, runtime.tools)
    return await runner.run(seed=seed)


@router.get("/dashboard/summary", response_model=DashboardSummary)
async def dashboard_summary() -> DashboardSummary:
    return runtime.analytics.dashboard()


@router.get("/dashboard/trend")
async def dashboard_trend():
    return runtime.analytics.trend()


@router.get("/sustainability/summary", response_model=SustainabilitySummary)
async def sustainability_summary() -> SustainabilitySummary:
    return runtime.analytics.sustainability()


@router.get("/agents/status")
async def agent_status():
    return runtime.analytics.agents()


@router.get("/edge/nodes")
async def edge_nodes():
    return runtime.analytics.edge_nodes()


@router.get("/inventory")
async def inventory_items():
    return runtime.store.list_inventory()


@router.get("/production/orders")
async def production_orders():
    return runtime.store.list_production()


@router.get("/people/technicians")
async def technicians():
    return runtime.store.list_technicians()


@router.get("/work-orders")
async def work_orders():
    return [incident.work_order for incident in runtime.store.list_incidents() if incident.work_order]


@router.get("/audit/events")
async def audit_events(limit: int = Query(default=100, ge=1, le=500)):
    return runtime.store.list_audit(limit=limit)


@router.get("/decisions/{incident_id}")
async def decision_context(incident_id: str):
    incident = runtime.store.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {
        "incident_id": incident.id,
        "status": incident.status,
        "risk": incident.risk,
        "diagnosis": incident.diagnosis,
        "reliability": incident.reliability,
        "safety": incident.safety,
        "sustainability": incident.sustainability,
        "resilience": incident.resilience,
        "plan": incident.plan,
        "approval": incident.approval,
        "work_order": incident.work_order,
        "verification": incident.verification,
    }


@router.post("/assistant/query", response_model=AssistantResponse)
async def assistant_query(payload: AssistantRequest) -> AssistantResponse:
    return await runtime.reasoning.answer(payload)
