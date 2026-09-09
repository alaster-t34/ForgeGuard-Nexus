# ForgeGuard Nexus v0.9.0 — Advanced Research Layers

ForgeGuard v0.9.0 extends the v0.8.0 Verified Scientific-Agent Platform with four stateful research-control layers. These layers are designed to make scientific work auditable, adversarial, revisable, and branch-aware rather than merely conversational.

## 1. Research Scheduler

The scheduler performs deterministic branch management.

It can:

- **GENERATE** a new research branch when cross-pollination exposes an unresolved obstacle.
- **FORK** a branch when an unresolved counterexample appears.
- **FORK** a branch when an experiment fails or is inconclusive.
- **FORK** a revalidation branch when Accepted Knowledge is challenged.
- **KILL / ARCHIVE** a rejected branch.
- **KILL / ARCHIVE** a branch whose latest adversarial council has reached a terminal FAIL verdict.

The scheduler does **not** generate scientific conclusions from model confidence. Its inputs are explicit recorded states: counterexamples, experiments, council verdicts, cross-pollination obstacles, and knowledge challenges.

Scheduler state is persisted in:

`runtime-data/research-scheduler.json`

Primary API:

- `POST /api/v1/research/scheduler/tick`
- `GET /api/v1/research/scheduler/runs`

A scheduler run records every decision with source branch, target branch, related evidence/challenge identifier, reason, and timestamp.

## 2. Evidence Graph

The original branch arrays remain for API compatibility, but they are no longer the authoritative relationship model.

ForgeGuard now maintains a persistent directed acyclic evidence graph.

### Node kinds

- Claim
- Evidence
- Counterexample
- Experiment
- Result
- Review
- Council review
- Knowledge
- Challenge

### Edge kinds

- supports
- contradicts
- tests
- derived_from
- reviews
- verifies
- challenges
- revises
- supersedes
- forked_from

Typical structure:

```text
Evidence --------supports--------> Claim
Counterexample --contradicts-----> Claim
Experiment ------tests-----------> Claim
Result ----------derived_from----> Evidence
Result ----------derived_from----> Experiment
Knowledge -------derived_from----> Result
Challenge -------challenges------> Knowledge
Knowledge v2 ----revises---------> Knowledge v1
```

Every newly inserted edge is checked for cycles. A relationship that would create circular provenance is rejected before persistence.

Graph state is persisted in:

`runtime-data/evidence-graph.json`

Primary API:

- `GET /api/v1/research/evidence-graph`
- `GET /api/v1/research/evidence-graph?branch_id=<branch>`
- `POST /api/v1/research/evidence-graph/edges`

The graph snapshot exposes its topological order so independent tooling can audit the DAG invariant.

## 3. Adversarial Research Council

A branch cannot enter Accepted Knowledge merely because a researcher, critic, and verifier agree.

v0.9.0 adds a five-role adversarial council:

1. **Researcher**
2. **Devil's Advocate**
3. **Literature Critic**
4. **Experiment Critic**
5. **Formal Verifier**

A council session snapshots the evidence graph that exists when the session is opened.

The council enforces:

- all five roles are present;
- all five roles use distinct actor IDs;
- FAIL or REVISE verdicts block acceptance;
- blocking objections block acceptance;
- the Devil's Advocate must inspect graph nodes;
- Literature Critic must cover literature evidence when literature nodes exist;
- Experiment Critic must cover experiment nodes when experiments exist;
- Formal Verifier must cover all required graph nodes captured by the session.

This means one model cannot satisfy independence merely by changing its role label.

Council state is persisted in:

`runtime-data/research-council.json`

Primary API:

- `POST /api/v1/research/branches/{branch_id}/council`
- `GET /api/v1/research/council`
- `POST /api/v1/research/council/{session_id}/contributions`
- `GET /api/v1/research/council/{session_id}/evaluation`

The Research Gate now includes both:

- `evidence_graph_acyclic`
- `adversarial_research_council`

A branch cannot be accepted if either check fails.

## 4. Knowledge Evolution

Accepted Knowledge is explicitly non-final.

The version state machine is:

```text
Accepted v1
    |
    | new counterexample / negative result
    v
Challenged
    |
    | adversarial revalidation
    +------> Revised ------> Accepted v2
    |
    +------> Superseded ---> Accepted replacement
    |
    +------> Revoked
```

Historical versions are never silently overwritten.

### Accepted

The current version passed the complete deterministic Research Gate and the Adversarial Research Council.

### Challenged

A new challenge has been recorded and linked into the Evidence Graph.

### Revised

The old version remains in history as Revised. A new Accepted successor must already have passed the complete Gate and Council.

### Superseded

The old version is terminal and replaced by a different Accepted Knowledge item that independently passed verification.

### Revoked

The accepted statement is withdrawn. No replacement is implied.

Evolution state is persisted in:

`runtime-data/knowledge-evolution.json`

Primary API:

- `GET /api/v1/research/knowledge-evolution`
- `POST /api/v1/research/knowledge/{knowledge_id}/challenge`
- `POST /api/v1/research/knowledge/{knowledge_id}/revoke`
- `POST /api/v1/research/knowledge/{knowledge_id}/revise/{replacement_knowledge_id}`
- `POST /api/v1/research/knowledge/{knowledge_id}/supersede/{replacement_knowledge_id}`

A revision or supersession cannot nominate arbitrary text as the successor. The replacement ID must already exist in Accepted Knowledge.

## Updated acceptance invariant

A branch enters Accepted Knowledge only when all of the following hold:

1. Hypothesis exists.
2. Evidence exists.
3. No unresolved counterexample remains.
4. Result is recorded.
5. Reproducible support or formal proof/derivation exists.
6. Independent critic passes.
7. Independent verifier passes.
8. Critic and verifier identities differ.
9. Verifier covers all current evidence records.
10. Evidence Graph remains acyclic.
11. Five-role Adversarial Research Council passes.

The acceptance decision is therefore based on recorded state and deterministic invariants, not on an agent's self-reported confidence.

## Research Nexus UI

`/ui/research.html` now exposes:

- branch overview;
- advanced system metrics;
- scheduler execution;
- evidence graph counts;
- council session state;
- knowledge evolution versions;
- accepted knowledge ledger;
- cross-pollination feed;
- deterministic gate reports.

The UI is a control surface over the real APIs. It does not fabricate branch, graph, council, scheduler, or knowledge-evolution state.

## Scope boundary

"Verified Scientific-Agent Platform" means ForgeGuard has explicit verification machinery, provenance, adversarial review, versioned knowledge, and deterministic promotion rules.

It does **not** mean:

- every generated hypothesis is true;
- literature retrieval is automatically complete;
- a passing experiment proves universal validity;
- formal verification exists where no formal model was provided;
- the system replaces peer review, replication, certification, or physical safety cases.

The purpose of these layers is to make unsupported certainty harder to produce and easier to audit, challenge, and revoke.
