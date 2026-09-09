from dataclasses import dataclass
from pathlib import Path

from app.agents.orchestrator import IncidentOrchestrator
from app.analysis.service import IndustrialDataAnalysisService
from app.bench.gateway import BenchGateway
from app.benchmark.runner import BenchmarkRunner
from app.bootstrap import seed_store
from app.config import get_settings
from app.domain.enums import ToolRisk
from app.models.deterministic import DeterministicFusionAdapter
from app.models.registry import ModelRegistry
from app.models.vibration_selected import SelectedVibrationAdapter
from app.research_orchestration import ResearchOrchestrator
from app.research_orchestration.autonomy import ResearchAutonomyController
from app.services.analytics import AnalyticsService
from app.services.knowledge import LocalKnowledgeBase
from app.services.reasoning import ReasoningGateway
from app.services.search import SearchBroker
from app.services.simulator import ScenarioSimulator
from app.services.store import InMemoryStore, PersistentStore
from app.services.tools import ToolRegistry


@dataclass(slots=True)
class Runtime:
    store: object
    orchestrator: IncidentOrchestrator
    simulator: ScenarioSimulator
    knowledge: LocalKnowledgeBase
    search: SearchBroker
    reasoning: ReasoningGateway
    analytics: AnalyticsService
    tools: ToolRegistry
    models: ModelRegistry
    benchmark: BenchmarkRunner
    bench: BenchGateway
    analysis: IndustrialDataAnalysisService
    research: ResearchOrchestrator
    research_autonomy: ResearchAutonomyController


settings = get_settings()
project_root = Path(__file__).resolve().parents[2]
if settings.database_url == "memory://":
    store = InMemoryStore()
else:
    store = PersistentStore(settings.database_url, project_root)
seed_store(store)
knowledge = LocalKnowledgeBase(settings.knowledge_path)
search = SearchBroker(settings, knowledge)
tools = ToolRegistry()
models = ModelRegistry([DeterministicFusionAdapter()])
selected_model_card = project_root / "backend" / "research" / "artifacts" / "selected_vibration_model.json"
if selected_model_card.exists():
    try:
        models.register(SelectedVibrationAdapter(selected_model_card))
    except Exception:
        pass
benchmark = BenchmarkRunner(project_root)
bench = BenchGateway(models, project_root / "artifacts" / "bench-evidence")
analytics = AnalyticsService(store, bench)
reasoning = ReasoningGateway(settings, store)
research = ResearchOrchestrator(project_root / "runtime-data" / "research-state.json")
research_autonomy = ResearchAutonomyController(
    project_root / "runtime-data" / "research-autonomy.json",
    research,
    search,
)
research.attach_autonomy(research_autonomy)
research.seed_demo()


async def query_asset(asset_id: str):
    asset = store.get_asset(asset_id)
    if not asset:
        raise KeyError(f"Unknown asset: {asset_id}")
    return asset.model_dump(mode="json")


async def retrieve_failure_modes(query: str, limit: int = 4):
    return [item.model_dump(mode="json") for item in knowledge.search(query, limit=limit)]


async def query_inventory(part_numbers: list[str]):
    by_id = {item.id: item for item in store.list_inventory()}
    items = []
    for part in part_numbers:
        item = by_id.get(part)
        if item:
            items.append(
                {
                    "part_number": item.id,
                    "name": item.name,
                    "available": item.available,
                    "reserved": item.quantity_reserved,
                    "lead_time_days": item.lead_time_days,
                    "circularity": item.circularity,
                }
            )
        else:
            items.append({"part_number": part, "available": 0, "reserved": 0, "lead_time_days": None})
    return {"items": items, "source": "ForgeGuard inventory service"}


async def query_production_context(asset_id: str):
    asset = store.get_asset(asset_id)
    if not asset:
        raise KeyError(f"Unknown asset: {asset_id}")
    orders = [order for order in store.list_production() if order.line == asset.line and order.status == "running"]
    order = orders[0] if orders else None
    return {
        "asset_id": asset_id,
        "active_order": order.id if order else None,
        "product": order.product if order else None,
        "minutes_to_safe_transition": order.safe_transition_minutes if order else 30,
        "downstream_buffer_minutes": order.downstream_buffer_minutes if order else 20,
        "shift": "A",
        "source": "ForgeGuard production context service",
    }


async def query_workforce(skills: list[str]):
    technicians = store.list_technicians()
    available = [item for item in technicians if item.available]
    qualified = [
        item for item in available
        if all(skill in item.skills or skill in item.certifications for skill in skills)
    ]
    return {
        "available": len(available),
        "qualified": len(qualified),
        "people": [
            {
                "id": item.id,
                "name": item.name,
                "team": item.team,
                "fatigue_risk": item.fatigue_risk.value,
            }
            for item in qualified
        ],
        "source": "ForgeGuard workforce context service",
    }


async def research_search(query: str, purpose: str, scope: str = "all"):
    return (await search.search(query, purpose=purpose, scope=scope)).model_dump(mode="json")


async def issue_work_order(incident_id: str, selected_option_id: str):
    return {
        "accepted": True,
        "incident_id": incident_id,
        "selected_option_id": selected_option_id,
        "system": "ForgeGuard governed work-order service",
    }


tools.register("asset.query", ToolRisk.READ_ONLY, query_asset)
tools.register("knowledge.failure_modes", ToolRisk.READ_ONLY, retrieve_failure_modes)
tools.register("inventory.query", ToolRisk.READ_ONLY, query_inventory)
tools.register("production.context", ToolRisk.READ_ONLY, query_production_context)
tools.register("workforce.query", ToolRisk.READ_ONLY, query_workforce)
tools.register("research.search", ToolRisk.READ_ONLY, research_search)
tools.register("work_order.issue", ToolRisk.HIGH, issue_work_order)

orchestrator = IncidentOrchestrator(store, tools)
analysis = IndustrialDataAnalysisService(bench, orchestrator, project_root)

runtime = Runtime(
    store=store,
    orchestrator=orchestrator,
    simulator=ScenarioSimulator(),
    knowledge=knowledge,
    search=search,
    reasoning=reasoning,
    analytics=analytics,
    tools=tools,
    models=models,
    benchmark=benchmark,
    bench=bench,
    analysis=analysis,
    research=research,
    research_autonomy=research_autonomy,
)
