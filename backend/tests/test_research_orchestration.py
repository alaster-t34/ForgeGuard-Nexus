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

    same_actor_critic = ResearchActor(id="agent-review-1", role="critic", label="Critic")
    same_actor_verifier = ResearchActor(id="agent-review-1", role="verifier", label="Verifier alias")
    service.add_critic_review(
        branch.id,
        ReviewCreate(
            reviewer=same_actor_critic,
            verdict=ReviewVerdict.PASS,
            summary="No blocking objection found.",
            checked_evidence_ids=[evidence_id],
        ),
    )
    service.add_verifier_review(
        branch.id,
        ReviewCreate(
            reviewer=same_actor_verifier,
            verdict=ReviewVerdict.PASS,
            summary="Evidence replayed successfully.",
            checked_evidence_ids=[evidence_id],
        ),
    )

    report = service.gate_report(branch.id)
    assert report.accepted is False
    assert "critic_verifier_independent" in report.blockers


def test_verified_branch_enters_accepted_knowledge(tmp_path):
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
    service.resolve_counterexample(
        branch.id,
        branch.counterexamples[0].id,
        "Require distinct critic and verifier actor IDs.",
    )
    service.set_result(
        branch.id,
        BranchResultUpdate(result="The research gate enforces recorded evidence and independent verification."),
    )
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

    report = service.gate_report(branch.id)
    assert report.accepted is True
    knowledge = service.accept(branch.id)
    assert knowledge.statement.startswith("The research gate")
    assert service.get_branch(branch.id).status.value == "verified"
    assert len(service.list_accepted_knowledge()) == 1
