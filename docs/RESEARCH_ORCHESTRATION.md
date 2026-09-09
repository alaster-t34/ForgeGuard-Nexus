# ForgeGuard Research Orchestration Layer

ForgeGuard Nexus v0.8.0 introduces a research orchestration layer above the existing industrial-agent runtime. The industrial maintenance workflow remains a first verified domain, but it is no longer the architectural boundary of the project.

## Core object: Research Branch

Every research branch is represented as an explicit stateful object with:

```text
Question
Hypothesis
Evidence
Counterexample
Experiment
Result
Status
```

A branch is not a chat thread. It is an auditable research record. Evidence, negative results, experiment artifacts, critic reviews and verifier reviews are persisted independently from the generated prose that may describe them.

Branch states:

```text
proposed -> active -> blocked / under_review -> verified
                              \-> rejected
```

An unresolved counterexample automatically places a non-terminal branch in `blocked` state.

## Cross-pollination

Research branches can publish a compact transfer packet:

```text
Best lemma
Best negative result
Unresolved obstacle
Useful tool
```

The packet records its source branch and target branches. Negative results are first-class transfers because preventing repeated failed work is part of useful scientific orchestration.

API:

```text
POST /api/v1/research/branches/{branch_id}/cross-pollinate
GET  /api/v1/research/cross-pollination
```

## Research Gate

The acceptance path is deterministic:

```text
Hypothesis
   |
   v
Evidence + counterexample handling
   |
   v
Independent critic
   |
   v
Independent verifier
   |
   v
Accepted Knowledge
```

The current gate checks all of the following:

1. A hypothesis is present.
2. At least one evidence record exists.
3. Every recorded counterexample is resolved.
4. A branch result is recorded.
5. The claim has reproducible evidence, a reproducible passed experiment, or formal proof/derivation evidence.
6. The latest critic review passes, has no blocking objection, and names checked evidence.
7. The latest verifier review passes, has no blocking objection, and names checked evidence.
8. Critic and verifier have different actor IDs.
9. The verifier explicitly covers every current evidence record.

If any condition fails, `POST /api/v1/research/branches/{branch_id}/accept` returns a conflict instead of creating Accepted Knowledge.

The gate intentionally does **not** use model confidence, self-evaluation scores, eloquence, majority vote among copies of the same agent, or a prompt instruction such as "be critical" as a substitute for independent verification.

## Accepted Knowledge

Accepted Knowledge is a separate ledger. Each accepted item preserves:

- branch ID;
- scoped result statement;
- evidence IDs;
- critic review ID;
- verifier review ID;
- question, hypothesis, counterexample IDs and experiment IDs;
- the exact deterministic gate checks that were satisfied at acceptance time.

This distinction is important: a branch may contain useful speculation, but only a gated result is promoted into accepted knowledge.

## API surface

```text
GET    /api/v1/research/overview
GET    /api/v1/research/branches
POST   /api/v1/research/branches
GET    /api/v1/research/branches/{branch_id}
POST   /api/v1/research/branches/{branch_id}/evidence
POST   /api/v1/research/branches/{branch_id}/counterexamples
POST   /api/v1/research/branches/{branch_id}/counterexamples/{counterexample_id}/resolve
POST   /api/v1/research/branches/{branch_id}/experiments
POST   /api/v1/research/branches/{branch_id}/experiments/{experiment_id}
POST   /api/v1/research/branches/{branch_id}/result
POST   /api/v1/research/branches/{branch_id}/reviews/critic
POST   /api/v1/research/branches/{branch_id}/reviews/verifier
GET    /api/v1/research/branches/{branch_id}/gate
POST   /api/v1/research/branches/{branch_id}/accept
GET    /api/v1/research/accepted-knowledge
POST   /api/v1/research/branches/{branch_id}/cross-pollinate
GET    /api/v1/research/cross-pollination
```

Interactive API documentation remains available at `/docs`.

## Research Console

Open:

```text
http://localhost:8000/ui/research.html
```

The console exposes:

- research overview metrics;
- branch cards with all seven required fields;
- deterministic Research Gate reports;
- Cross-pollination feed;
- Accepted Knowledge ledger;
- branch creation.

The existing industrial runtime remains at `/`.

## Persistence and reproducibility

Research orchestration state is stored in:

```text
runtime-data/research-state.json
```

Writes use a temporary file and atomic replace. The state carries a schema version. A malformed runtime state file is treated as unavailable evidence and is never silently accepted as trusted knowledge.

## Verification tests

`backend/tests/test_research_orchestration.py` verifies at least three safety properties:

- unresolved counterexamples block acceptance;
- one actor cannot serve as both critic and verifier merely by changing its role label;
- an independently reviewed, evidence-covered branch can enter Accepted Knowledge.

These tests are part of the normal GitHub Actions backend matrix on Python 3.11 and 3.12 for Linux and Windows.

## Scope boundary

"Verified Scientific-Agent Platform" means that ForgeGuard provides explicit verification machinery and provenance for claims processed through this gate. It does **not** mean every generated hypothesis is scientifically true, that an automated verifier replaces domain experts, or that a software gate is equivalent to peer review, replication, certification or a physical safety case.

That boundary is deliberate. Scientific software should make unsupported confidence harder to hide, not merely give it a nicer dashboard.
