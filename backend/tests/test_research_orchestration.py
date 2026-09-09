import pytest

from app.research_orchestration.advanced_schemas import (
    CouncilContributionCreate,
    CouncilRole,
    CouncilVerdict,
    EvidenceGraphEdgeCreate,
    GraphEdgeKind,
    KnowledgeChallengeCreate,
    KnowledgeRevalidation,
    KnowledgeTransitionCreate,
    SchedulerTickRequest,
)
from app.research_orchestration.schemas import (
    BranchResultUpdate,
    CounterexampleCreate,
    EvidenceCreate,
    EvidenceKind,
    ExperimentCreate,
    ExperimentStatus,
    ExperimentUpdate,
    ResearchActor,
    ResearchBranchCreate,
    ReviewCreate,
    ReviewVerdict,
)
from app.research_orchestration.service import ResearchOrchestrator


def make_branch(service: ResearchOrchestrator, suffix: str = ""):
    return service.create_branch(
        ResearchBranchCreate(
            title=f"Robust claim{suffix}",
            question="Does the proposed gate reject unsupported scientific claims?",
            hypothesis="A claim with unresolved counterexamples or non-independent review is rejected.",
            owner="researcher-a",
        )
    )


def add_support(service: ResearchOrchestrator, branch_id: str, actor_suffix: str = ""):
    branch = service.add_evidence(
        branch_id,
        EvidenceCreate(
            kind=EvidenceKind.REPLICATION,
            title="Replication record",
            claim="Repeated execution gives the same result.",
            source="pytest://replication",
            reproducible=True,
        ),
    )
    evidence_id = branch.evidence[0].id
    service.set_result(branch.id, BranchResultUpdate(result="The hypothesis survived the recorded test."))
    service.add_critic_review(
        branch.id,
        ReviewCreate(
            reviewer=ResearchActor(id=f"critic-{actor_suffix or '1'}", role="critic", label="Independent critic"),
            verdict=ReviewVerdict.PASS,
            summary="No blocking objection found.",
            checked_evidence_ids=[evidence_id],
        ),
    )
    service.add_verifier_review(
        branch.id,
        ReviewCreate(
            reviewer=ResearchActor(id=f"verifier-{actor_suffix or '1'}", role="verifier", label="Independent verifier"),
            verdict=ReviewVerdict.PASS,
            summary="Evidence replayed successfully.",
            checked_evidence_ids=[evidence_id],
        ),
    )
    return service.get_branch(branch.id)


def pass_council(service: ResearchOrchestrator, branch_id: str, actor_suffix: str = ""):
    session = service.open_council(branch_id)
    roles = [
        CouncilRole.RESEARCHER,
        CouncilRole.DEVILS_ADVOCATE,
        CouncilRole.LITERATURE_CRITIC,
        CouncilRole.EXPERIMENT_CRITIC,
        CouncilRole.FORMAL_VERIFIER,
    ]
    for index, role in enumerate(roles):
        session = service.council_contribute(
            session.id,
            CouncilContributionCreate(
                role=role,
                actor_id=f"actor-{actor_suffix}-{index}",
                actor_label=role.value,
                verdict=CouncilVerdict.PASS,
                summary=f"{role.value} completed independent review.",
                checked_graph_node_ids=session.required_graph_node_ids,
            ),
        )
    assert service.council_evaluate(session.id).accepted is True
    return session


def make_accepted(service: ResearchOrchestrator, suffix: str):
    branch = make_branch(service, suffix=f" {suffix}")
    branch = add_support(service, branch.id, actor_suffix=suffix)
    pass_council(service, branch.id, actor_suffix=suffix)
    assert service.gate_report(branch.id).accepted is True
    return service.accept(branch.id), branch


def test_gate_blocks_unresolved_counterexample(tmp_path):
    service = ResearchOrchestrator(tmp_path / "research.json")
    branch = make_branch(service)
    branch = service.add_evidence(
        branch.id,
        EvidenceCreate(
            kind=EvidenceKind.BENCHMARK,
            title="Reproducible benchmark",
            claim="The gate catches unsupported acceptance attempts.",
            source="pytest://research-gate",
            reproducible=True,
        ),
    )
    branch = service.add_counterexample(
        branch.id,
        CounterexampleCreate(
            title="Unresolved negative case",
            description="A contradictory case remains unexplained.",
            source="pytest://negative-case",
        ),
    )
    service.set_result(branch.id, BranchResultUpdate(result="The current implementation rejects the unsafe path."))
    report = service.gate_report(branch.id)
    assert report.accepted is False
    assert "counterexamples_resolved" in report.blockers


def test_gate_requires_independent_critic_and_verifier(tmp_path):
    service = ResearchOrchestrator(tmp_path / "research.json")
    branch = make_branch(service)
    branch = service.add_evidence(
        branch.id,
        EvidenceCreate(
            kind=EvidenceKind.REPLICATION,
            title="Replication record",
            claim="Repeated execution gives the same result.",
            source="pytest://replication",
            reproducible=True,
        ),
    )
    evidence_id = branch.evidence[0].id
    service.set_result(branch.id, BranchResultUpdate(result="The hypothesis survived the recorded test."))
    service.add_critic_review(
        branch.id,
        ReviewCreate(
            reviewer=ResearchActor(id="agent-review-1", role="critic", label="Critic"),
            verdict=ReviewVerdict.PASS,
            summary="No blocking objection found.",
            checked_evidence_ids=[evidence_id],
        ),
    )
    service.add_verifier_review(
        branch.id,
        ReviewCreate(
            reviewer=ResearchActor(id="agent-review-1", role="verifier", label="Verifier alias"),
            verdict=ReviewVerdict.PASS,
            summary="Evidence replayed successfully.",
            checked_evidence_ids=[evidence_id],
        ),
    )
    report = service.gate_report(branch.id)
    assert report.accepted is False
    assert "critic_verifier_independent" in report.blockers


def test_evidence_graph_rejects_cycles(tmp_path):
    service = ResearchOrchestrator(tmp_path / "research.json")
    branch = make_branch(service)
    branch = service.add_evidence(
        branch.id,
        EvidenceCreate(
            kind=EvidenceKind.DATASET,
            title="Controlled evidence",
            claim="Evidence supports hypothesis.",
            source="pytest://dataset",
            reproducible=True,
        ),
    )
    claim_id = service.graph.claim_node_id(branch.id)
    evidence_id = branch.evidence[0].id
    with pytest.raises(ValueError, match="cycle"):
        service.add_graph_edge(EvidenceGraphEdgeCreate(
            source_id=claim_id,
            target_id=evidence_id,
            kind=GraphEdgeKind.DERIVED_FROM,
            rationale="Illegal circular support",
        ))


def test_council_requires_five_distinct_actors(tmp_path):
    service = ResearchOrchestrator(tmp_path / "research.json")
    branch = add_support(service, make_branch(service).id)
    session = service.open_council(branch.id)
    for role in CouncilRole:
        service.council_contribute(
            session.id,
            CouncilContributionCreate(
                role=role,
                actor_id="same-agent",
                actor_label="One agent wearing another hat",
                verdict=CouncilVerdict.PASS,
                summary="Claims independence despite identical identity.",
                checked_graph_node_ids=session.required_graph_node_ids,
            ),
        )
    evaluation = service.council_evaluate(session.id)
    assert evaluation.accepted is False
    assert "council_actor_identity_collision" in evaluation.blockers


def test_verified_branch_enters_versioned_accepted_knowledge(tmp_path):
    service = ResearchOrchestrator(tmp_path / "research.json")
    branch = make_branch(service)
    branch = service.add_evidence(
        branch.id,
        EvidenceCreate(
            kind=EvidenceKind.DATASET,
            title="Controlled evidence",
            claim="Observed behavior matches the hypothesis under the recorded protocol.",
            source="pytest://dataset",
            reproducible=True,
        ),
    )
    evidence_id = branch.evidence[0].id
    branch = service.add_experiment(
        branch.id,
        ExperimentCreate(
            title="Independent replay",
            protocol="Run the same gate sequence from clean state.",
            expected_result="Unsafe acceptance is rejected and safe acceptance succeeds.",
        ),
    )
    experiment_id = branch.experiments[0].id
    service.update_experiment(
        branch.id,
        experiment_id,
        ExperimentUpdate(
            actual_result="Observed expected behavior.",
            status=ExperimentStatus.PASSED,
            artifacts=["pytest://artifact/replay"],
            reproducible=True,
        ),
    )
    branch = service.add_counterexample(
        branch.id,
        CounterexampleCreate(
            title="Same reviewer identity",
            description="Critic and verifier could otherwise be aliases of one actor.",
            source="pytest://identity-negative",
        ),
    )
    service.resolve_counterexample(branch.id, branch.counterexamples[0].id, "Require distinct actor IDs.")
    service.set_result(branch.id, BranchResultUpdate(result="The research gate enforces recorded evidence and independent verification."))
    service.add_critic_review(
        branch.id,
        ReviewCreate(
            reviewer=ResearchActor(id="critic-1", role="critic", label="Independent critic"),
            verdict=ReviewVerdict.PASS,
            summary="Counterexample resolved; evidence supports the scoped result.",
            checked_evidence_ids=[evidence_id],
        ),
    )
    service.add_verifier_review(
        branch.id,
        ReviewCreate(
            reviewer=ResearchActor(id="verifier-1", role="verifier", label="Independent verifier"),
            verdict=ReviewVerdict.PASS,
            summary="Replayed evidence and confirmed the gate outcome.",
            checked_evidence_ids=[evidence_id],
        ),
    )
    pass_council(service, branch.id)
    assert service.gate_report(branch.id).accepted is True
    knowledge = service.accept(branch.id)
    evolution = service.evolution_snapshot()
    assert service.get_branch(branch.id).status.value == "verified"
    assert evolution.versions[0].id == knowledge.id
    assert evolution.versions[0].version == 1
    assert evolution.versions[0].state.value == "accepted"

    challenged = service.challenge_knowledge(
        knowledge.id,
        KnowledgeChallengeCreate(
            title="New negative result",
            description="A newly observed case contradicts the accepted statement.",
            source="pytest://new-counterexample",
            evidence_node_ids=[evidence_id],
            raised_by="devils-advocate",
        ),
    )
    assert challenged.state.value == "challenged"
    revoked = service.revoke_knowledge(
        knowledge.id,
        KnowledgeTransitionCreate(actor="formal-verifier", reason="Challenge invalidates the scoped statement."),
    )
    assert revoked.state.value == "revoked"


def test_challenged_knowledge_can_be_revised_only_by_verified_successor(tmp_path):
    service = ResearchOrchestrator(tmp_path / "research.json")
    original, original_branch = make_accepted(service, "original")
    replacement, _ = make_accepted(service, "replacement")
    evidence_id = original_branch.evidence[0].id
    service.challenge_knowledge(
        original.id,
        KnowledgeChallengeCreate(
            title="Scope failure",
            description="The original statement is too broad and needs a verified narrower successor.",
            source="pytest://scope-failure",
            evidence_node_ids=[evidence_id],
            raised_by="devils-advocate",
        ),
    )
    challenge = next(item for item in service.evolution_snapshot().challenges if item.knowledge_id == original.id)
    successor = service.evolution.revise(
        original.id,
        replacement,
        KnowledgeRevalidation(
            challenge_id=challenge.id,
            actor="formal-verifier-revision",
            rationale="Replacement passed the complete independent gate with narrower scope.",
        ),
    )
    snapshot = service.evolution_snapshot()
    old = next(item for item in snapshot.versions if item.id == original.id)
    assert old.state.value == "revised"
    assert old.successor_id == successor.id
    assert successor.state.value == "accepted"
    assert successor.version == 2
    assert successor.parent_version_id == original.id
    edge = next(
        item for item in service.graph_snapshot().edges
        if item.source_id == successor.id and item.target_id == original.id
    )
    assert edge.kind.value == "revises"


def test_challenged_knowledge_can_be_superseded_by_verified_replacement(tmp_path):
    service = ResearchOrchestrator(tmp_path / "research.json")
    original, original_branch = make_accepted(service, "legacy")
    replacement, _ = make_accepted(service, "successor")
    service.challenge_knowledge(
        original.id,
        KnowledgeChallengeCreate(
            title="Competing verified explanation",
            description="A stronger independently verified explanation replaces the old claim.",
            source="pytest://supersession",
            evidence_node_ids=[original_branch.evidence[0].id],
            raised_by="literature-critic",
        ),
    )
    challenge = next(item for item in service.evolution_snapshot().challenges if item.knowledge_id == original.id)
    successor = service.evolution.supersede(
        original.id,
        replacement,
        KnowledgeRevalidation(
            challenge_id=challenge.id,
            actor="formal-verifier-supersession",
            rationale="Replacement dominates the old scoped claim after independent verification.",
        ),
    )
    snapshot = service.evolution_snapshot()
    old = next(item for item in snapshot.versions if item.id == original.id)
    assert old.state.value == "superseded"
    assert old.successor_id == successor.id
    assert successor.state.value == "accepted"
    edge = next(
        item for item in service.graph_snapshot().edges
        if item.source_id == successor.id and item.target_id == original.id
    )
    assert edge.kind.value == "supersedes"


def test_scheduler_forks_unresolved_counterexample(tmp_path):
    service = ResearchOrchestrator(tmp_path / "research.json")
    branch = make_branch(service)
    service.add_counterexample(
        branch.id,
        CounterexampleCreate(
            title="Boundary failure",
            description="The hypothesis fails on a boundary condition.",
            source="pytest://boundary",
        ),
    )
    run = service.scheduler_tick(SchedulerTickRequest())
    fork = next(item for item in run.decisions if item.action.value == "fork")
    assert fork.source_branch_id == branch.id
    assert fork.target_branch_id is not None
    child = service.get_branch(fork.target_branch_id)
    assert child.parent_branch_id == branch.id
