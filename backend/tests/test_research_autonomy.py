from types import SimpleNamespace

import pytest

from app.research_orchestration.autonomy import ResearchAutonomyController
from app.research_orchestration.autonomy_schemas import (
    AutoExperimentKind,
    AutoExperimentRequest,
    BranchBudgetAllocation,
    BranchBudgetLimits,
    LiteratureRelation,
    LiteratureSearchRequest,
)
from app.research_orchestration.schemas import (
    AcceptedKnowledge,
    CounterexampleCreate,
    ResearchBranchCreate,
)
from app.research_orchestration.service import ResearchOrchestrator


class FakeSearchBroker:
    async def search(self, query, *, purpose, max_results=None, scope="all"):
        citations = [
            SimpleNamespace(
                title="Auditable scientific agent evidence",
                url="https://doi.org/10.0000/forgeguard-test",
                snippet="Independent evidence supports explicit provenance and verification gates.",
                source="FakeCrossref",
                published_at="2026-09-09",
            ),
            SimpleNamespace(
                title="Negative evidence under distribution shift",
                url="https://example.org/negative-evidence",
                snippet="A boundary condition may contradict an over-broad hypothesis.",
                source="FakeOpenAlex",
                published_at="2026",
            ),
        ]
        return SimpleNamespace(
            query=query,
            citations=citations[: max_results or len(citations)],
            provider="fake-academic",
            policy_notes=[f"scope={scope}", f"purpose={purpose}"],
        )


def make_system(tmp_path):
    research = ResearchOrchestrator(tmp_path / "research.json")
    autonomy = ResearchAutonomyController(
        tmp_path / "autonomy.json",
        research,
        FakeSearchBroker(),
    )
    research.attach_autonomy(autonomy)
    return research, autonomy


def make_branch(research, *, parent=None, title="Autonomy branch"):
    return research.create_branch(
        ResearchBranchCreate(
            title=title,
            question="Can controlled scientific autonomy remain auditable?",
            hypothesis="Budgeted, provenance-preserving automation is safer than unconstrained execution.",
            owner="autonomy-researcher",
            parent_branch_id=parent,
        )
    )


def test_branch_budget_blocks_excess_auto_experiment(tmp_path):
    research, autonomy = make_system(tmp_path)
    branch = make_branch(research)
    autonomy.allocate_budget(
        branch.id,
        BranchBudgetAllocation(
            limits=BranchBudgetLimits(
                max_experiment_runs=1,
                max_literature_queries=3,
                max_citations_ingested=10,
                max_compute_units=2,
            )
        ),
    )
    run = autonomy.run_experiment(
        branch.id,
        AutoExperimentRequest(
            title="Evidence DAG integrity",
            kind=AutoExperimentKind.GRAPH_INTEGRITY,
            expected_result="Graph remains acyclic.",
            compute_units=1,
        ),
    )
    assert run.status.value == "passed"
    assert research.get_branch(branch.id).experiments[-1].id == run.experiment_id
    assert autonomy.budget(branch.id).spent_experiment_runs == 1
    assert any(node.id == run.experiment_id for node in research.graph_snapshot(branch.id).nodes)

    with pytest.raises(ValueError, match="budget exceeded"):
        autonomy.run_experiment(
            branch.id,
            AutoExperimentRequest(
                title="Second experiment",
                kind=AutoExperimentKind.BRANCH_CONSISTENCY,
                expected_result="Should be rejected by budget before execution.",
            ),
        )


@pytest.mark.asyncio
async def test_literature_search_ingests_citations_into_evidence_graph(tmp_path):
    research, autonomy = make_system(tmp_path)
    branch = make_branch(research)
    result = await autonomy.ingest_literature(
        branch.id,
        LiteratureSearchRequest(
            query="scientific agent provenance",
            scope="academic",
            max_results=2,
            relation=LiteratureRelation.SUPPORT,
        ),
    )
    updated = research.get_branch(branch.id)
    assert result.provider == "fake-academic"
    assert result.citations_ingested == 2
    assert len(result.evidence_ids) == 2
    assert all(item.kind.value == "literature" for item in updated.evidence)
    graph_ids = {node.id for node in research.graph_snapshot(branch.id).nodes}
    assert set(result.evidence_ids).issubset(graph_ids)
    assert autonomy.budget(branch.id).spent_literature_queries == 1
    assert autonomy.budget(branch.id).spent_citations_ingested == 2


@pytest.mark.asyncio
async def test_literature_challenge_becomes_counterexample_and_propagates(tmp_path):
    research, autonomy = make_system(tmp_path)
    parent = make_branch(research, title="Parent claim")
    child = make_branch(research, parent=parent.id, title="Child claim")
    result = await autonomy.ingest_literature(
        parent.id,
        LiteratureSearchRequest(
            query="counterevidence",
            max_results=1,
            relation=LiteratureRelation.CHALLENGE,
        ),
    )
    assert len(result.counterexample_ids) == 1
    assert research.get_branch(parent.id).status.value == "blocked"
    inherited = research.get_branch(child.id).counterexamples
    assert any(item.source == f"propagated:{result.counterexample_ids[0]}" for item in inherited)
    assert research.get_branch(child.id).status.value == "blocked"


def test_lineage_scoring_records_depth_descendants_and_budget_efficiency(tmp_path):
    research, autonomy = make_system(tmp_path)
    root = make_branch(research, title="Root")
    child = make_branch(research, parent=root.id, title="Child")
    grandchild = make_branch(research, parent=child.id, title="Grandchild")
    scores = {item.branch_id: item for item in autonomy.lineage_scores()}
    assert scores[root.id].depth == 0
    assert scores[root.id].descendant_count == 2
    assert scores[child.id].depth == 1
    assert scores[child.id].descendant_count == 1
    assert scores[grandchild.id].depth == 2
    assert "budget_efficiency" in scores[root.id].factors


def test_counterexample_propagates_to_all_descendants_without_recursion(tmp_path):
    research, autonomy = make_system(tmp_path)
    root = make_branch(research, title="Root")
    child = make_branch(research, parent=root.id, title="Child")
    grandchild = make_branch(research, parent=child.id, title="Grandchild")
    root = research.add_counterexample(
        root.id,
        CounterexampleCreate(
            title="Ancestor contradiction",
            description="The root hypothesis fails on a newly discovered boundary condition.",
            source="pytest://ancestor-negative",
        ),
    )
    source_id = root.counterexamples[-1].id
    assert len(autonomy.list_contradictions()) == 1
    assert any(item.source == f"propagated:{source_id}" for item in research.get_branch(child.id).counterexamples)
    assert any(item.source == f"propagated:{source_id}" for item in research.get_branch(grandchild.id).counterexamples)
    assert len(research.get_branch(child.id).counterexamples) == 1
    assert len(research.get_branch(grandchild.id).counterexamples) == 1


def test_knowledge_challenge_propagates_to_descendant_branch(tmp_path):
    research, autonomy = make_system(tmp_path)
    root = make_branch(research, title="Accepted root")
    child = make_branch(research, parent=root.id, title="Inherited child")
    knowledge = AcceptedKnowledge(
        branch_id=root.id,
        title=root.title,
        statement="A previously accepted scoped statement.",
        evidence_ids=[],
        critic_review_id="critic-test",
        verifier_review_id="verifier-test",
        provenance={"test": True},
    )
    research._accepted[knowledge.id] = knowledge
    research.graph.add_knowledge(knowledge)
    research.evolution.bootstrap(knowledge)
    research._persist()

    version = research.challenge_knowledge(
        knowledge.id,
        payload=__import__(
            "app.research_orchestration.advanced_schemas",
            fromlist=["KnowledgeChallengeCreate"],
        ).KnowledgeChallengeCreate(
            title="New contradiction",
            description="New evidence challenges the accepted knowledge item.",
            source="pytest://knowledge-challenge",
            raised_by="devils-advocate",
        ),
    )
    assert version.state.value == "challenged"
    events = autonomy.list_contradictions()
    assert events[0].trigger.value == "knowledge_challenge"
    assert knowledge.id in events[0].affected_knowledge_ids
    assert child.id in events[0].affected_branch_ids
    assert any(item.source.startswith("propagated:challenge-") for item in research.get_branch(child.id).counterexamples)
