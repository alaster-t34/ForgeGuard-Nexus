from __future__ import annotations

import json
from pathlib import Path
from threading import RLock

from app.research_orchestration.autonomy_schemas import (
    AutoExperimentKind,
    AutoExperimentRequest,
    AutoExperimentRun,
    BranchBudgetAllocation,
    BranchResourceBudget,
    BudgetStatus,
    ContradictionPropagationEvent,
    ContradictionTrigger,
    LineageScore,
    LiteratureIngestionResult,
    LiteratureRelation,
    LiteratureSearchRequest,
    ResearchAutonomyOverview,
)
from app.research_orchestration.schemas import (
    CounterexampleCreate,
    EvidenceCreate,
    EvidenceKind,
    ExperimentCreate,
    ExperimentStatus,
    ExperimentUpdate,
    utc_now,
)


class ResearchAutonomyController:
    """Controlled autonomy for experiments, literature evidence, budgets and propagation.

    Automatic experiments are limited to pre-registered deterministic executors. No
    arbitrary command or code execution is accepted from API payloads.
    """

    def __init__(self, state_path: Path, research, search_broker=None):
        self.state_path = state_path
        self.research = research
        self.search_broker = search_broker
        self._lock = RLock()
        self._budgets: dict[str, BranchResourceBudget] = {}
        self._experiment_runs: list[AutoExperimentRun] = []
        self._literature_runs: list[LiteratureIngestionResult] = []
        self._contradictions: list[ContradictionPropagationEvent] = []
        self._load()

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            self._budgets = {
                item["branch_id"]: BranchResourceBudget.model_validate(item)
                for item in raw.get("budgets", [])
            }
            self._experiment_runs = [
                AutoExperimentRun.model_validate(item) for item in raw.get("experiment_runs", [])
            ]
            self._literature_runs = [
                LiteratureIngestionResult.model_validate(item) for item in raw.get("literature_runs", [])
            ]
            self._contradictions = [
                ContradictionPropagationEvent.model_validate(item)
                for item in raw.get("contradictions", [])
            ]
        except (OSError, ValueError, TypeError, KeyError):
            self._budgets, self._experiment_runs, self._literature_runs, self._contradictions = {}, [], [], []

    def _persist(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "budgets": [item.model_dump(mode="json") for item in self._budgets.values()],
            "experiment_runs": [item.model_dump(mode="json") for item in self._experiment_runs],
            "literature_runs": [item.model_dump(mode="json") for item in self._literature_runs],
            "contradictions": [item.model_dump(mode="json") for item in self._contradictions],
        }
        temp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        temp.replace(self.state_path)

    def ensure_budget(self, branch_id: str) -> BranchResourceBudget:
        self.research.get_branch(branch_id)
        budget = self._budgets.get(branch_id)
        if budget is None:
            budget = BranchResourceBudget(branch_id=branch_id)
            self._budgets[branch_id] = budget
            self._persist()
        return budget

    def allocate_budget(self, branch_id: str, payload: BranchBudgetAllocation) -> BranchResourceBudget:
        with self._lock:
            self.research.get_branch(branch_id)
            budget = self._budgets.get(branch_id) or BranchResourceBudget(branch_id=branch_id)
            budget.limits = payload.limits
            budget.updated_at = utc_now()
            self._refresh_budget_status(budget)
            self._budgets[branch_id] = budget
            self._persist()
            return budget

    def budget(self, branch_id: str) -> BranchResourceBudget:
        return self.ensure_budget(branch_id)

    def list_budgets(self) -> list[BranchResourceBudget]:
        for branch in self.research.list_branches():
            self.ensure_budget(branch.id)
        return sorted(self._budgets.values(), key=lambda item: item.updated_at, reverse=True)

    def _refresh_budget_status(self, budget: BranchResourceBudget) -> None:
        limits = budget.limits
        exhausted = (
            budget.spent_experiment_runs >= limits.max_experiment_runs
            or budget.spent_literature_queries >= limits.max_literature_queries
            or budget.spent_citations_ingested >= limits.max_citations_ingested
            or budget.spent_compute_units >= limits.max_compute_units
        )
        budget.status = BudgetStatus.EXHAUSTED if exhausted else BudgetStatus.ACTIVE

    def _charge(self, branch_id: str, *, experiments=0, literature=0, citations=0, compute=0) -> BranchResourceBudget:
        budget = self.ensure_budget(branch_id)
        limits = budget.limits
        checks = [
            (budget.spent_experiment_runs + experiments, limits.max_experiment_runs, "experiment runs"),
            (budget.spent_literature_queries + literature, limits.max_literature_queries, "literature queries"),
            (budget.spent_citations_ingested + citations, limits.max_citations_ingested, "citation ingestion"),
            (budget.spent_compute_units + compute, limits.max_compute_units, "compute units"),
        ]
        exceeded = [name for value, limit, name in checks if value > limit]
        if exceeded:
            budget.status = BudgetStatus.EXHAUSTED
            budget.updated_at = utc_now()
            self._persist()
            raise ValueError(f"Branch resource budget exceeded: {', '.join(exceeded)}")
        budget.spent_experiment_runs += experiments
        budget.spent_literature_queries += literature
        budget.spent_citations_ingested += citations
        budget.spent_compute_units += compute
        budget.updated_at = utc_now()
        self._refresh_budget_status(budget)
        self._budgets[branch_id] = budget
        self._persist()
        return budget

    def run_experiment(self, branch_id: str, payload: AutoExperimentRequest) -> AutoExperimentRun:
        with self._lock:
            branch = self.research.get_branch(branch_id)
            self._charge(branch_id, experiments=1, compute=payload.compute_units)
            protocol = f"auto:{payload.kind.value}; parameters={json.dumps(payload.parameters, sort_keys=True)}"
            branch = self.research.add_experiment(
                branch_id,
                ExperimentCreate(title=payload.title, protocol=protocol, expected_result=payload.expected_result),
            )
            experiment = branch.experiments[-1]
            status, actual, metrics = self._execute(branch_id, payload)
            artifact_uri = f"forgeguard://autonomy/experiments/{experiment.id}"
            self.research.update_experiment(
                branch_id,
                experiment.id,
                ExperimentUpdate(
                    actual_result=actual,
                    status=status,
                    artifacts=[artifact_uri],
                    reproducible=True,
                ),
            )
            run = AutoExperimentRun(
                branch_id=branch_id,
                experiment_id=experiment.id,
                kind=payload.kind,
                status=status,
                actual_result=actual,
                metrics=metrics,
                artifact_uri=artifact_uri,
                compute_units=payload.compute_units,
            )
            self._experiment_runs.append(run)
            self._persist()
            return run

    def _execute(self, branch_id: str, payload: AutoExperimentRequest):
        branch = self.research.get_branch(branch_id)
        params = payload.parameters
        if payload.kind == AutoExperimentKind.NUMERIC_THRESHOLD:
            value = float(params.get("value", 0.0))
            threshold = float(params.get("threshold", 0.0))
            operator = str(params.get("operator", ">="))
            result = {
                ">=": value >= threshold,
                ">": value > threshold,
                "<=": value <= threshold,
                "<": value < threshold,
                "==": value == threshold,
            }.get(operator)
            if result is None:
                raise ValueError(f"Unsupported numeric operator: {operator}")
            return (
                ExperimentStatus.PASSED if result else ExperimentStatus.FAILED,
                f"{value} {operator} {threshold} evaluated to {result}.",
                {"value": value, "threshold": threshold, "operator": operator, "condition": result},
            )
        if payload.kind == AutoExperimentKind.GRAPH_INTEGRITY:
            graph = self.research.graph_snapshot(branch_id)
            acyclic = len(graph.topological_order) == len(graph.nodes)
            return (
                ExperimentStatus.PASSED if acyclic else ExperimentStatus.FAILED,
                f"Evidence graph acyclic={acyclic}; nodes={len(graph.nodes)}; edges={len(graph.edges)}.",
                {"acyclic": acyclic, "nodes": len(graph.nodes), "edges": len(graph.edges)},
            )
        if payload.kind == AutoExperimentKind.EVIDENCE_REPLAY:
            reproducible = [item.id for item in branch.evidence if item.reproducible]
            success = bool(reproducible)
            return (
                ExperimentStatus.PASSED if success else ExperimentStatus.INCONCLUSIVE,
                f"Reproducible evidence records available: {len(reproducible)}.",
                {"reproducible_evidence_ids": reproducible},
            )
        if payload.kind == AutoExperimentKind.BRANCH_CONSISTENCY:
            unresolved = [item.id for item in branch.counterexamples if not item.resolved]
            success = not unresolved and bool(branch.hypothesis.strip())
            return (
                ExperimentStatus.PASSED if success else ExperimentStatus.FAILED,
                f"Branch consistency check: unresolved_counterexamples={len(unresolved)}.",
                {"unresolved_counterexample_ids": unresolved, "hypothesis_present": bool(branch.hypothesis.strip())},
            )
        raise ValueError(f"Unknown auto experiment kind: {payload.kind}")

    def list_experiment_runs(self, branch_id: str | None = None) -> list[AutoExperimentRun]:
        items = self._experiment_runs
        if branch_id is not None:
            items = [item for item in items if item.branch_id == branch_id]
        return list(reversed(items))

    async def ingest_literature(self, branch_id: str, payload: LiteratureSearchRequest) -> LiteratureIngestionResult:
        if self.search_broker is None:
            raise ValueError("Literature search broker is not configured")
        self.research.get_branch(branch_id)
        self._charge(branch_id, literature=1)
        result = await self.search_broker.search(
            payload.query,
            purpose=payload.purpose,
            max_results=payload.max_results,
            scope=payload.scope,
        )
        remaining = self.ensure_budget(branch_id).limits.max_citations_ingested - self.ensure_budget(branch_id).spent_citations_ingested
        citations = result.citations[: max(0, remaining)]
        evidence_ids: list[str] = []
        counterexample_ids: list[str] = []
        for citation in citations:
            if payload.relation == LiteratureRelation.CHALLENGE:
                branch = self.research.add_counterexample(
                    branch_id,
                    CounterexampleCreate(
                        title=f"Literature challenge: {citation.title}",
                        description=citation.snippet or f"Retrieved literature may challenge the current hypothesis: {citation.title}",
                        source=citation.url,
                    ),
                )
                counterexample_ids.append(branch.counterexamples[-1].id)
            else:
                claim = citation.snippet or f"Retrieved literature context for branch hypothesis: {citation.title}"
                branch = self.research.add_evidence(
                    branch_id,
                    EvidenceCreate(
                        kind=EvidenceKind.LITERATURE,
                        title=citation.title,
                        claim=claim,
                        source=citation.url,
                        reproducible=False,
                        metadata={
                            "provider": citation.source,
                            "published_at": citation.published_at,
                            "relation": payload.relation.value,
                            "query": payload.query,
                        },
                    ),
                )
                evidence_ids.append(branch.evidence[-1].id)
        if citations:
            self._charge(branch_id, citations=len(citations))
        ingestion = LiteratureIngestionResult(
            branch_id=branch_id,
            query=payload.query,
            provider=result.provider,
            evidence_ids=evidence_ids,
            counterexample_ids=counterexample_ids,
            citations_ingested=len(citations),
            policy_notes=result.policy_notes,
        )
        self._literature_runs.append(ingestion)
        self._persist()
        return ingestion

    def list_literature_runs(self, branch_id: str | None = None) -> list[LiteratureIngestionResult]:
        items = self._literature_runs
        if branch_id is not None:
            items = [item for item in items if item.branch_id == branch_id]
        return list(reversed(items))

    def lineage_scores(self) -> list[LineageScore]:
        branches = {item.id: item for item in self.research.list_branches()}
        children: dict[str, list[str]] = {branch_id: [] for branch_id in branches}
        for branch in branches.values():
            if branch.parent_branch_id in children:
                children[branch.parent_branch_id].append(branch.id)

        def depth(branch_id: str) -> int:
            seen: set[str] = set()
            current = branches[branch_id]
            value = 0
            while current.parent_branch_id and current.parent_branch_id in branches and current.parent_branch_id not in seen:
                seen.add(current.id)
                value += 1
                current = branches[current.parent_branch_id]
            return value

        def descendants(branch_id: str) -> set[str]:
            found: set[str] = set()
            stack = list(children.get(branch_id, []))
            while stack:
                current = stack.pop()
                if current in found:
                    continue
                found.add(current)
                stack.extend(children.get(current, []))
            return found

        scores: list[LineageScore] = []
        for branch in branches.values():
            evidence = min(1.0, len(branch.evidence) / 4)
            experiments = min(1.0, len(branch.experiments) / 3)
            resolved = 1.0 if all(item.resolved for item in branch.counterexamples) else 0.0
            verified = 1.0 if branch.status.value == "verified" else 0.0
            descendants_count = len(descendants(branch.id))
            fertility = min(1.0, descendants_count / 4)
            budget = self.ensure_budget(branch.id)
            efficiency = 1.0 - min(1.0, max(budget.utilization().values(), default=0.0))
            penalties: list[str] = []
            if branch.status.value in {"rejected", "archived"}:
                penalties.append(branch.status.value)
            if any(not item.resolved for item in branch.counterexamples):
                penalties.append("unresolved_counterexample")
            score = 100 * (
                0.24 * evidence
                + 0.22 * experiments
                + 0.18 * resolved
                + 0.18 * verified
                + 0.10 * fertility
                + 0.08 * efficiency
            )
            if penalties:
                score *= 0.72
            scores.append(LineageScore(
                branch_id=branch.id,
                parent_branch_id=branch.parent_branch_id,
                depth=depth(branch.id),
                descendant_count=descendants_count,
                score=round(score, 2),
                factors={
                    "evidence": evidence,
                    "experiments": experiments,
                    "negative_result_resolution": resolved,
                    "verified": verified,
                    "lineage_fertility": fertility,
                    "budget_efficiency": efficiency,
                },
                penalties=penalties,
            ))
        return sorted(scores, key=lambda item: item.score, reverse=True)

    def propagate_counterexample(self, origin_branch_id: str, counterexample_id: str) -> ContradictionPropagationEvent:
        origin = self.research.get_branch(origin_branch_id)
        source = next((item for item in origin.counterexamples if item.id == counterexample_id), None)
        if source is None:
            raise KeyError(f"Unknown counterexample: {counterexample_id}")
        branches = self.research.list_branches()
        children: dict[str, list[str]] = {}
        for branch in branches:
            if branch.parent_branch_id:
                children.setdefault(branch.parent_branch_id, []).append(branch.id)
        descendants: list[str] = []
        stack = list(children.get(origin_branch_id, []))
        while stack:
            current = stack.pop()
            if current in descendants:
                continue
            descendants.append(current)
            stack.extend(children.get(current, []))

        inherited: list[str] = []
        for branch_id in descendants:
            branch = self.research.get_branch(branch_id)
            already = any(item.source == f"propagated:{counterexample_id}" for item in branch.counterexamples)
            if already:
                continue
            updated = self.research.add_counterexample(
                branch_id,
                CounterexampleCreate(
                    title=f"Inherited contradiction: {source.title}",
                    description=f"Inherited from ancestor {origin_branch_id}: {source.description}",
                    source=f"propagated:{counterexample_id}",
                ),
            )
            inherited.append(updated.counterexamples[-1].id)

        affected_knowledge = [
            item.id for item in self.research.list_accepted_knowledge()
            if item.branch_id == origin_branch_id or item.branch_id in descendants
        ]
        event = ContradictionPropagationEvent(
            trigger=ContradictionTrigger.COUNTEREXAMPLE,
            source_id=counterexample_id,
            origin_branch_id=origin_branch_id,
            affected_branch_ids=descendants,
            affected_knowledge_ids=affected_knowledge,
            inherited_counterexample_ids=inherited,
        )
        self._contradictions.append(event)
        self._persist()
        return event

    def propagate_knowledge_challenge(self, knowledge_id: str, challenge_id: str) -> ContradictionPropagationEvent:
        accepted = next((item for item in self.research.list_accepted_knowledge() if item.id == knowledge_id), None)
        if accepted is None:
            raise KeyError(f"Unknown accepted knowledge: {knowledge_id}")
        branch_id = accepted.branch_id
        event = self.propagate_counterexample_from_text(
            branch_id,
            trigger=ContradictionTrigger.KNOWLEDGE_CHALLENGE,
            source_id=challenge_id,
            title=f"Accepted knowledge challenged: {accepted.title}",
            description=f"Knowledge item {knowledge_id} is challenged and descendants must revalidate inherited assumptions.",
        )
        event.affected_knowledge_ids = sorted(set(event.affected_knowledge_ids + [knowledge_id]))
        self._contradictions[-1] = event
        self._persist()
        return event

    def propagate_counterexample_from_text(
        self,
        origin_branch_id: str,
        *,
        trigger: ContradictionTrigger,
        source_id: str,
        title: str,
        description: str,
    ) -> ContradictionPropagationEvent:
        branches = self.research.list_branches()
        children: dict[str, list[str]] = {}
        for branch in branches:
            if branch.parent_branch_id:
                children.setdefault(branch.parent_branch_id, []).append(branch.id)
        descendants: list[str] = []
        stack = list(children.get(origin_branch_id, []))
        while stack:
            current = stack.pop()
            if current in descendants:
                continue
            descendants.append(current)
            stack.extend(children.get(current, []))
        inherited: list[str] = []
        for branch_id in descendants:
            branch = self.research.get_branch(branch_id)
            source = f"propagated:{source_id}"
            if any(item.source == source for item in branch.counterexamples):
                continue
            updated = self.research.add_counterexample(
                branch_id,
                CounterexampleCreate(
                    title=title,
                    description=description,
                    source=source,
                ),
            )
            inherited.append(updated.counterexamples[-1].id)
        affected_knowledge = [
            item.id for item in self.research.list_accepted_knowledge()
            if item.branch_id == origin_branch_id or item.branch_id in descendants
        ]
        event = ContradictionPropagationEvent(
            trigger=trigger,
            source_id=source_id,
            origin_branch_id=origin_branch_id,
            affected_branch_ids=descendants,
            affected_knowledge_ids=affected_knowledge,
            inherited_counterexample_ids=inherited,
        )
        self._contradictions.append(event)
        self._persist()
        return event

    def list_contradictions(self) -> list[ContradictionPropagationEvent]:
        return list(reversed(self._contradictions))

    def overview(self) -> ResearchAutonomyOverview:
        return ResearchAutonomyOverview(
            branches_total=len(self.research.list_branches()),
            experiment_runs=len(self._experiment_runs),
            literature_searches=len(self._literature_runs),
            citations_ingested=sum(item.citations_ingested for item in self._literature_runs),
            budgets_exhausted=sum(item.status == BudgetStatus.EXHAUSTED for item in self._budgets.values()),
            contradiction_events=len(self._contradictions),
        )
