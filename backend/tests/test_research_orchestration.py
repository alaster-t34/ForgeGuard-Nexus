import pytest

from app.research_orchestration.advanced_schemas import (
    CouncilContributionCreate,
    CouncilRole,
    CouncilVerdict,
    EvidenceGraphEdgeCreate,
    GraphEdgeKind,
    KnowledgeChallengeCreate,
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


def make_branch(service: ResearchOrchestrator):
    return service.create_branch(
        ResearchBranchCreate(
            title="Robust claim",
            question="Does the proposed gate reject unsupported scientific claims?",
            hypothesis="A claim with unresolved counterexamples or non-independent review is rejected.",
            owner="researcher-a",
        )
    )


def add_support(service: ResearchOrchestrator, branch_id: str):
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
            reviewer=ResearchActor(id="critic-1", role="critic", label="Independent critic"),
            verdict=ReviewVerdict.PASS,
            summary="No blocking objection found.",
            checked_evidence_ids=[evidence_id],
        ),
    )
    service.add_verifier_review(
        branch.id,
        ReviewCreate(
            reviewer=ResearchActor(id="verifier-1", role="verifier", label="Independent verifier"),
            verdict=ReviewVerdict.PASS,
            summary="Evidence replayed successfully.",
            checked_evidence_ids=[evidence_id],
        ),
    )
    return service.get_branch(branch.id)


def pass_council(service: ResearchOrchestrator, branch_id: str):
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
                actor_id=f"actor-{index}",
                actor_label=role.value,
                verdict=CouncilVerdict.PASS,
                summary=f"{role.value} completed independent review.",
                checked_graph_node_ids=session.required_graph_node_ids,
            ),
        )
    assert service.council_evaluate(session.id).accepted is True
    return session


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
