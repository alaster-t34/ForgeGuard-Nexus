from __future__ import annotations

import json
from pathlib import Path
from threading import RLock

from app.research_orchestration.advanced_schemas import (
    CouncilContributionCreate,
    CouncilEvaluation,
    CouncilSession,
    EvidenceGraphEdge,
    EvidenceGraphEdgeCreate,
    EvidenceGraphSnapshot,
    KnowledgeChallengeCreate,
    KnowledgeEvolutionSnapshot,
    KnowledgeRevalidation,
    KnowledgeTransitionCreate,
    KnowledgeVersion,
    ResearchSystemOverview,
    SchedulerRun,
    SchedulerTickRequest,
)
from app.research_orchestration.council import AdversarialResearchCouncil
from app.research_orchestration.evidence_graph import EvidenceGraphStore
from app.research_orchestration.knowledge_evolution import KnowledgeEvolutionStore
from app.research_orchestration.scheduler import ResearchScheduler
from app.research_orchestration.schemas import (
    AcceptedKnowledge,
    BranchResultUpdate,
    BranchStatus,
    CounterexampleCreate,
    CrossPollinationDigest,
    CrossPollinationRequest,
    EvidenceCreate,
    EvidenceKind,
    EvidenceRecord,
    ExperimentCreate,
    ExperimentRecord,
    ExperimentStatus,
    ExperimentUpdate,
    GateCheck,
    GateStage,
    ResearchBranch,
    ResearchBranchCreate,
    ResearchGateReport,
    ResearchOverview,
    ReviewCreate,
    ReviewRecord,
    ReviewVerdict,
    utc_now,
)


class ResearchOrchestrator:
    """Persistent, auditable research state machine with adversarial evolution.

    Acceptance is deliberately deterministic: recorded support, resolved negative
    evidence, independent review, evidence coverage and a five-role adversarial
    council must all pass. Accepted knowledge remains challengeable and versioned.
    """

    def __init__(self, state_path: Path):
        self.state_path = state_path
        self._lock = RLock()
        self._branches: dict[str, ResearchBranch] = {}
        self._accepted: dict[str, AcceptedKnowledge] = {}
        self._cross_pollination: list[CrossPollinationDigest] = []
        self.autonomy = None
        base = state_path.parent
        self.graph = EvidenceGraphStore(base / "evidence-graph.json")
        self.council = AdversarialResearchCouncil(base / "research-council.json", self.graph)
        self.evolution = KnowledgeEvolutionStore(base / "knowledge-evolution.json", self.graph)
        self.scheduler = ResearchScheduler(base / "research-scheduler.json")
        self._load()
        self._reconcile_graph()

    def attach_autonomy(self, controller) -> None:
        self.autonomy = controller

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            self._branches = {
                item["id"]: ResearchBranch.model_validate(item)
                for item in raw.get("branches", [])
            }
            self._accepted = {
                item["id"]: AcceptedKnowledge.model_validate(item)
                for item in raw.get("accepted_knowledge", [])
            }
            self._cross_pollination = [
                CrossPollinationDigest.model_validate(item)
                for item in raw.get("cross_pollination", [])
            ]
        except (OSError, ValueError, TypeError, KeyError):
            self._branches = {}
            self._accepted = {}
            self._cross_pollination = []

    def _persist(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 3,
            "branches": [item.model_dump(mode="json") for item in self._branches.values()],
            "accepted_knowledge": [item.model_dump(mode="json") for item in self._accepted.values()],
            "cross_pollination": [item.model_dump(mode="json") for item in self._cross_pollination],
        }
        temp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        temp.replace(self.state_path)

    def _reconcile_graph(self) -> None:
        for branch in self._branches.values():
            self.graph.ensure_branch(branch)
            for evidence in branch.evidence:
                self.graph.add_evidence(branch, evidence)
            for counterexample in branch.counterexamples:
                self.graph.add_counterexample(branch, counterexample)
            for experiment in branch.experiments:
                self.graph.add_experiment(branch, experiment)
            if branch.result:
                self.graph.set_result(branch)
            for review in branch.critic_reviews:
                self.graph.add_review(branch, review, verifier=False)
            for review in branch.verifier_reviews:
                self.graph.add_review(branch, review, verifier=True)
        for accepted in self._accepted.values():
            self.graph.add_knowledge(accepted)
            self.evolution.bootstrap(accepted)

    def _branch(self, branch_id: str) -> ResearchBranch:
        branch = self._branches.get(branch_id)
        if branch is None:
            raise KeyError(f"Unknown research branch: {branch_id}")
        return branch

    def _touch(self, branch: ResearchBranch) -> ResearchBranch:
        branch.updated_at = utc_now()
        if branch.status not in {BranchStatus.VERIFIED, BranchStatus.REJECTED, BranchStatus.ARCHIVED}:
            if any(not item.resolved for item in branch.counterexamples):
                branch.status = BranchStatus.BLOCKED
            elif branch.critic_reviews or branch.verifier_reviews:
                branch.status = BranchStatus.UNDER_REVIEW
            else:
                branch.status = BranchStatus.ACTIVE
        self._branches[branch.id] = branch
        self._persist()
        return branch

    def seed_demo(self) -> None:
        with self._lock:
            if self._branches:
                return
            examples = [
                ResearchBranchCreate(
                    title="Bearing evidence robustness under sensor corruption",
                    question="Can the current evidence gate reject corrupted vibration inputs without hiding valid faults?",
                    hypothesis="Quality gating can preserve safe-response behavior while retaining useful diagnostic evidence.",
                    owner="reliability-researcher",
                    tags=["industrial-ai", "robustness", "first-domain"],
                ),
                ResearchBranchCreate(
                    title="Cross-domain abstention calibration",
                    question="Does evidence-aware abstention remain calibrated when data moves beyond the synthetic OpenEval-RM distribution?",
                    hypothesis="Domain-shift indicators plus abstention will reduce unsupported high-confidence decisions.",
                    owner="verification-researcher",
                    tags=["calibration", "domain-shift"],
                ),
                ResearchBranchCreate(
                    title="Verifier independence protocol",
                    question="What minimum separation prevents a research agent from grading its own hypothesis?",
                    hypothesis="Distinct critic and verifier identities plus evidence coverage checks are a useful minimum invariant.",
                    owner="governance-researcher",
                    tags=["scientific-agents", "governance"],
                ),
            ]
            for payload in examples:
                self.create_branch(payload)

    def overview(self) -> ResearchOverview:
        branches = list(self._branches.values())
        return ResearchOverview(
            branches_total=len(branches),
            active=sum(item.status == BranchStatus.ACTIVE for item in branches),
            blocked=sum(item.status == BranchStatus.BLOCKED for item in branches),
            under_review=sum(item.status == BranchStatus.UNDER_REVIEW for item in branches),
            verified=sum(item.status == BranchStatus.VERIFIED for item in branches),
            rejected=sum(item.status == BranchStatus.REJECTED for item in branches),
            accepted_knowledge=len(self._accepted),
            cross_pollination_events=len(self._cross_pollination),
        )

    def system_overview(self) -> ResearchSystemOverview:
        graph = self.graph.snapshot()
        sessions = self.council.list_sessions()
        evolution = self.evolution.snapshot()
        runs = self.scheduler.list_runs()
        return ResearchSystemOverview(
            graph_nodes=len(graph.nodes),
            graph_edges=len(graph.edges),
            council_sessions=len(sessions),
            council_passed=sum(item.status.value == "passed" for item in sessions),
            knowledge_challenged=sum(item.state.value == "challenged" for item in evolution.versions),
            knowledge_revised=sum(item.state.value == "revised" for item in evolution.versions),
            knowledge_revoked=sum(item.state.value == "revoked" for item in evolution.versions),
            scheduler_runs=len(runs),
            scheduler_actions=sum(len(item.decisions) for item in runs),
        )

    def list_branches(self) -> list[ResearchBranch]:
        return sorted(self._branches.values(), key=lambda item: item.updated_at, reverse=True)

    def get_branch(self, branch_id: str) -> ResearchBranch:
        return self._branch(branch_id)

    def create_branch(self, payload: ResearchBranchCreate) -> ResearchBranch:
        with self._lock:
            if payload.parent_branch_id is not None:
                self._branch(payload.parent_branch_id)
            branch = ResearchBranch(**payload.model_dump())
            branch.status = BranchStatus.ACTIVE
            self._branches[branch.id] = branch
            self.graph.ensure_branch(branch)
            self._persist()
            if self.autonomy is not None:
                self.autonomy.ensure_budget(branch.id)
            return branch

    def archive_branch(self, branch_id: str, reason: str) -> ResearchBranch:
        with self._lock:
            branch = self._branch(branch_id)
            branch.status = BranchStatus.ARCHIVED
            branch.tags = sorted(set(branch.tags + ["killed-by-scheduler"]))
            branch.updated_at = utc_now()
            self._branches[branch.id] = branch
            self._persist()
            return branch

    def add_evidence(self, branch_id: str, payload: EvidenceCreate) -> ResearchBranch:
        with self._lock:
            branch = self._branch(branch_id)
            record = EvidenceRecord(**payload.model_dump())
            branch.evidence.append(record)
            self.graph.add_evidence(branch, record)
            return self._touch(branch)

    def add_counterexample(self, branch_id: str, payload: CounterexampleCreate) -> ResearchBranch:
        from app.research_orchestration.schemas import CounterexampleRecord

        with self._lock:
            branch = self._branch(branch_id)
            record = CounterexampleRecord(**payload.model_dump())
            branch.counterexamples.append(record)
            self.graph.add_counterexample(branch, record)
            touched = self._touch(branch)
            if self.autonomy is not None and not payload.source.startswith("propagated:"):
                self.autonomy.propagate_counterexample(branch.id, record.id)
            return touched

    def resolve_counterexample(self, branch_id: str, counterexample_id: str, resolution: str) -> ResearchBranch:
        with self._lock:
            branch = self._branch(branch_id)
            item = next((value for value in branch.counterexamples if value.id == counterexample_id), None)
            if item is None:
                raise KeyError(f"Unknown counterexample: {counterexample_id}")
            item.resolved = True
            item.resolution = resolution
            self.graph.update_counterexample(item)
            return self._touch(branch)

    def add_experiment(self, branch_id: str, payload: ExperimentCreate) -> ResearchBranch:
        with self._lock:
            branch = self._branch(branch_id)
            record = ExperimentRecord(**payload.model_dump())
            branch.experiments.append(record)
            self.graph.add_experiment(branch, record)
            return self._touch(branch)

    def update_experiment(self, branch_id: str, experiment_id: str, payload: ExperimentUpdate) -> ResearchBranch:
        with self._lock:
            branch = self._branch(branch_id)
            experiment = next((value for value in branch.experiments if value.id == experiment_id), None)
            if experiment is None:
                raise KeyError(f"Unknown experiment: {experiment_id}")
            experiment.actual_result = payload.actual_result
            experiment.status = payload.status
            experiment.artifacts = payload.artifacts
            experiment.reproducible = payload.reproducible
            experiment.updated_at = utc_now()
            self.graph.update_experiment(experiment)
            return self._touch(branch)

    def set_result(self, branch_id: str, payload: BranchResultUpdate) -> ResearchBranch:
        with self._lock:
            branch = self._branch(branch_id)
            branch.result = payload.result.strip()
            self.graph.set_result(branch)
            return self._touch(branch)

    def add_critic_review(self, branch_id: str, payload: ReviewCreate) -> ResearchBranch:
        if payload.reviewer.role not in {"critic", "human"}:
            raise ValueError("Independent critic review requires a critic or human reviewer")
        return self._add_review(branch_id, payload, verifier=False)

    def add_verifier_review(self, branch_id: str, payload: ReviewCreate) -> ResearchBranch:
        if payload.reviewer.role not in {"verifier", "human"}:
            raise ValueError("Verifier review requires a verifier or human reviewer")
        return self._add_review(branch_id, payload, verifier=True)

    def _add_review(self, branch_id: str, payload: ReviewCreate, *, verifier: bool) -> ResearchBranch:
        with self._lock:
            branch = self._branch(branch_id)
            known = {item.id for item in branch.evidence}
            unknown = set(payload.checked_evidence_ids) - known
            if unknown:
                raise ValueError(f"Review references unknown evidence IDs: {sorted(unknown)}")
            review = ReviewRecord(**payload.model_dump())
            if verifier:
                branch.verifier_reviews.append(review)
            else:
                branch.critic_reviews.append(review)
            self.graph.add_review(branch, review, verifier=verifier)
            return self._touch(branch)

    def cross_pollinate(self, branch_id: str, payload: CrossPollinationRequest) -> CrossPollinationDigest:
        with self._lock:
            self._branch(branch_id)
            targets = payload.target_branch_ids or [item.id for item in self._branches.values() if item.id != branch_id]
            for target in targets:
                if target == branch_id:
                    raise ValueError("A branch cannot cross-pollinate into itself")
                self._branch(target)
            digest = CrossPollinationDigest(
                source_branch_id=branch_id,
                target_branch_ids=targets,
                best_lemma=payload.best_lemma,
                best_negative_result=payload.best_negative_result,
                unresolved_obstacle=payload.unresolved_obstacle,
                useful_tool=payload.useful_tool,
            )
            if not any([digest.best_lemma, digest.best_negative_result, digest.unresolved_obstacle, digest.useful_tool]):
                raise ValueError("Cross-pollination requires at least one research payload")
            self._cross_pollination.append(digest)
            self._persist()
            return digest

    def list_cross_pollination(self) -> list[CrossPollinationDigest]:
        return list(reversed(self._cross_pollination))

    def list_accepted_knowledge(self) -> list[AcceptedKnowledge]:
        return sorted(self._accepted.values(), key=lambda item: item.accepted_at, reverse=True)

    def graph_snapshot(self, branch_id: str | None = None) -> EvidenceGraphSnapshot:
        return self.graph.snapshot(branch_id)

    def add_graph_edge(self, payload: EvidenceGraphEdgeCreate) -> EvidenceGraphEdge:
        return self.graph.add_edge(payload)

    def open_council(self, branch_id: str) -> CouncilSession:
        branch = self._branch(branch_id)
        return self.council.open_session(branch)

    def council_contribute(self, session_id: str, payload: CouncilContributionCreate) -> CouncilSession:
        return self.council.contribute(session_id, payload)

    def council_evaluate(self, session_id: str) -> CouncilEvaluation:
        return self.council.evaluate(session_id)

    def list_council_sessions(self, branch_id: str | None = None) -> list[CouncilSession]:
        return self.council.list_sessions(branch_id)

    def scheduler_tick(self, payload: SchedulerTickRequest) -> SchedulerRun:
        return self.scheduler.tick(self, policy=payload.policy, dry_run=payload.dry_run)

    def list_scheduler_runs(self) -> list[SchedulerRun]:
        return self.scheduler.list_runs()

    def evolution_snapshot(self) -> KnowledgeEvolutionSnapshot:
        return self.evolution.snapshot()

    def challenge_knowledge(self, knowledge_id: str, payload: KnowledgeChallengeCreate) -> KnowledgeVersion:
        if knowledge_id not in self._accepted:
            raise KeyError(f"Unknown accepted knowledge: {knowledge_id}")
        self.evolution.bootstrap(self._accepted[knowledge_id])
        version = self.evolution.challenge(knowledge_id, payload)
        if self.autonomy is not None and version.challenge_ids:
            self.autonomy.propagate_knowledge_challenge(knowledge_id, version.challenge_ids[-1])
        return version

    def revoke_knowledge(self, knowledge_id: str, payload: KnowledgeTransitionCreate) -> KnowledgeVersion:
        return self.evolution.revoke(knowledge_id, payload)

    def gate_report(self, branch_id: str) -> ResearchGateReport:
        branch = self._branch(branch_id)
        checks: list[GateCheck] = []

        def add(name: str, passed: bool, detail: str) -> None:
            checks.append(GateCheck(name=name, passed=passed, detail=detail))

        add("hypothesis_present", bool(branch.hypothesis.strip()), "A falsifiable hypothesis must be recorded.")
        add("evidence_present", bool(branch.evidence), "At least one evidence record is required.")
        unresolved = [item.id for item in branch.counterexamples if not item.resolved]
        add(
            "counterexamples_resolved",
            not unresolved,
            "Unresolved counterexamples block acceptance." if unresolved else "No unresolved counterexample remains.",
        )
        add("result_recorded", bool((branch.result or "").strip()), "A branch result must be recorded before review.")
        reproducible_evidence = any(item.reproducible for item in branch.evidence)
        reproducible_experiment = any(
            item.status == ExperimentStatus.PASSED and item.reproducible for item in branch.experiments
        )
        proof_evidence = any(item.kind in {EvidenceKind.PROOF, EvidenceKind.DERIVATION} for item in branch.evidence)
        add(
            "reproducibility_or_formal_support",
            reproducible_evidence or reproducible_experiment or proof_evidence,
            "Require reproducible evidence/experiment or formal proof/derivation evidence.",
        )
        graph = self.graph.snapshot(branch_id)
        graph_ok = len(graph.topological_order) == len(graph.nodes)
        add("evidence_graph_acyclic", graph_ok, "Evidence Graph must remain a DAG without circular support.")
        critic = branch.critic_reviews[-1] if branch.critic_reviews else None
        verifier = branch.verifier_reviews[-1] if branch.verifier_reviews else None
        critic_pass = bool(
            critic and critic.verdict == ReviewVerdict.PASS and not critic.blocking_objections and critic.checked_evidence_ids
        )
        verifier_pass = bool(
            verifier and verifier.verdict == ReviewVerdict.PASS and not verifier.blocking_objections and verifier.checked_evidence_ids
        )
        add("independent_critic_pass", critic_pass, "Latest critic must pass and inspect recorded evidence.")
        add("verifier_pass", verifier_pass, "Latest verifier must pass and inspect recorded evidence.")
        independent = bool(critic and verifier and critic.reviewer.id != verifier.reviewer.id)
        add("critic_verifier_independent", independent, "Critic and verifier must have distinct actor IDs.")
        evidence_ids = {item.id for item in branch.evidence}
        verifier_coverage = bool(verifier and evidence_ids.issubset(set(verifier.checked_evidence_ids)))
        add("verifier_evidence_coverage", verifier_coverage, "Verifier must explicitly cover every current evidence record.")
        sessions = self.council.list_sessions(branch_id)
        latest_council = sessions[0] if sessions else None
        council_pass = bool(latest_council and self.council.evaluate(latest_council.id).accepted)
        add(
            "adversarial_research_council",
            council_pass,
            "Latest five-role Adversarial Research Council must pass with independent actors and graph coverage.",
        )
        blockers = [item.name for item in checks if not item.passed]
        if not branch.hypothesis.strip():
            stage = GateStage.HYPOTHESIS
        elif not branch.evidence or unresolved or not (branch.result or "").strip() or not graph_ok:
            stage = GateStage.EVIDENCE
        elif not critic_pass:
            stage = GateStage.CRITIC
        elif not verifier_pass or not independent or not verifier_coverage or not council_pass:
            stage = GateStage.VERIFIER
        else:
            stage = GateStage.ACCEPTED
        return ResearchGateReport(branch_id=branch.id, stage=stage, accepted=not blockers, checks=checks, blockers=blockers)

    def accept(self, branch_id: str) -> AcceptedKnowledge:
        with self._lock:
            branch = self._branch(branch_id)
            report = self.gate_report(branch_id)
            if not report.accepted:
                raise ValueError(f"Research gate rejected branch; blockers: {', '.join(report.blockers)}")
            existing = next((item for item in self._accepted.values() if item.branch_id == branch_id), None)
            if existing:
                return existing
            critic = branch.critic_reviews[-1]
            verifier = branch.verifier_reviews[-1]
            council = self.council.list_sessions(branch_id)[0]
            knowledge = AcceptedKnowledge(
                branch_id=branch.id,
                title=branch.title,
                statement=branch.result or branch.hypothesis,
                evidence_ids=[item.id for item in branch.evidence],
                critic_review_id=critic.id,
                verifier_review_id=verifier.id,
                provenance={
                    "question": branch.question,
                    "hypothesis": branch.hypothesis,
                    "counterexample_ids": [item.id for item in branch.counterexamples],
                    "experiment_ids": [item.id for item in branch.experiments],
                    "council_session_id": council.id,
                    "gate_checks": [item.model_dump(mode="json") for item in report.checks],
                },
            )
            self._accepted[knowledge.id] = knowledge
            self.graph.add_knowledge(knowledge)
            self.evolution.bootstrap(knowledge)
            branch.status = BranchStatus.VERIFIED
            branch.updated_at = utc_now()
            self._branches[branch.id] = branch
            self._persist()
            return knowledge
