# ForgeGuard Nexus

**Verified Scientific-Agent Platform for autonomous research orchestration, evidence-governed reasoning, and industrial AI verification.**

> Version: **v0.9.0**  
> First verified domain: **industrial rotating machinery / maintenance agents**  
> License: **Apache-2.0**

ForgeGuard started as an evidence-driven Industrial 5.0 maintenance-agent system. v0.8.0 added research branches, cross-pollination, deterministic gates, independent criticism, verification, and Accepted Knowledge. v0.9.0 adds four harder layers above that foundation:

1. **Research Scheduler** — automatically generate, fork, and kill branches from explicit research-state signals.
2. **Evidence Graph** — model Claim → Evidence → Counterexample → Experiment as a persistent DAG rather than loose arrays.
3. **Adversarial Research Council** — require five independent scientific roles before promotion.
4. **Knowledge Evolution** — let Accepted Knowledge become Challenged, Revised, Revoked, or Superseded without deleting history.

The industrial workflow remains intact. It is ForgeGuard's first scientific/engineering validation domain, not the definition of the whole platform.

## The core idea

A scientific-agent system should not let one model generate a hypothesis, grade its own evidence, dismiss its own counterexamples, and then promote the result to "knowledge" because the prose sounded authoritative.

ForgeGuard now separates the lifecycle into explicit state machines:

```text
Research Question
      |
      v
Research Scheduler
  generate / fork / kill
      |
      v
Research Branch
  Question
  Hypothesis
  Evidence
  Counterexample
  Experiment
  Result
  Status
      |
      v
Evidence DAG
Claim -> Evidence -> Counterexample -> Experiment
      |
      v
Independent critic + verifier
      |
      v
Adversarial Research Council
  Researcher
  Devil's Advocate
  Literature Critic
  Experiment Critic
  Formal Verifier
      |
      v
Accepted Knowledge v1
      |
      | new negative evidence
      v
Challenged
  |        |        |
Revised  Revoked  Superseded
```

## Research Scheduler

The scheduler consumes recorded state, not model confidence.

It can:

- **GENERATE** a branch from a cross-pollination obstacle;
- **FORK** a branch around an unresolved counterexample;
- **FORK** a failed or inconclusive experiment into a recovery branch;
- **FORK** a revalidation branch when Accepted Knowledge is challenged;
- **KILL / ARCHIVE** rejected branches;
- **KILL / ARCHIVE** branches whose latest adversarial council reaches a terminal FAIL verdict.

Every scheduler run is persisted with action, reason, source branch, target branch, related state identifier, and timestamp.

## Evidence Graph

Branch arrays remain for API compatibility, but scientific relationships are now mirrored into a persistent DAG.

Node types include:

```text
Claim
Evidence
Counterexample
Experiment
Result
Review
Council review
Knowledge
Challenge
```

Edge types include:

```text
supports
contradicts
tests
derived_from
reviews
verifies
challenges
revises
supersedes
forked_from
```

Any inserted edge that would create a cycle is rejected before persistence. Circular provenance therefore cannot quietly become a scientific argument just because enough arrows were drawn.

## Adversarial Research Council

A branch cannot enter Accepted Knowledge until a five-role council passes:

1. **Researcher**
2. **Devil's Advocate**
3. **Literature Critic**
4. **Experiment Critic**
5. **Formal Verifier**

The council enforces distinct actor IDs. One agent cannot satisfy independence by wearing five role labels.

Role-specific coverage is also enforced:

- Devil's Advocate must inspect graph state.
- Literature Critic must cover literature nodes when they exist.
- Experiment Critic must cover experiment nodes when they exist.
- Formal Verifier must cover all required graph nodes captured when the session opens.
- FAIL, REVISE, or blocking objections prevent promotion.

## Knowledge Evolution

Accepted Knowledge is explicitly revisable.

```text
Accepted v1
    |
    | new counterexample / negative result
    v
Challenged
    |
    +--> Revised ------> Accepted v2
    |
    +--> Superseded ---> Accepted replacement
    |
    +--> Revoked
```

Historical versions are preserved rather than silently rewritten.

A revision or supersession cannot nominate arbitrary text as the successor. The replacement must already exist in Accepted Knowledge, which means it independently passed the complete Research Gate and Adversarial Research Council.

## Cross-pollination

Branches can send compact research-transfer packets to other branches:

```text
Best lemma
Best negative result
Unresolved obstacle
Useful tool
```

This moves both progress and failure information across parallel research paths. Negative results are useful state, not discarded chat history.

## Deterministic Research Gate

Promotion into Accepted Knowledge now requires all of the following:

- a recorded hypothesis;
- evidence;
- no unresolved counterexample;
- a recorded result;
- reproducible evidence/experiment or formal proof/derivation support;
- a passing independent critic review;
- a passing verifier review;
- different critic and verifier actor identities;
- verifier coverage of all current evidence;
- an acyclic Evidence Graph;
- a passing five-role Adversarial Research Council.

Model confidence is not an acceptance criterion.

See [`docs/RESEARCH_ORCHESTRATION.md`](docs/RESEARCH_ORCHESTRATION.md) for the base research state model and [`docs/ADVANCED_RESEARCH_LAYERS.md`](docs/ADVANCED_RESEARCH_LAYERS.md) for the v0.9 architecture.

## Research Console

Start ForgeGuard and open:

```text
http://localhost:8000/ui/research.html
```

The Research Nexus console shows:

- branch overview and status;
- advanced Research Scheduler metrics and execution;
- Evidence Graph node / edge counts;
- Adversarial Research Council state;
- Knowledge Evolution versions and challenges;
- Question / Hypothesis / Evidence / Counterexample / Experiment / Result / Status;
- deterministic Gate reports;
- Cross-pollination feed;
- Accepted Knowledge ledger;
- new branch creation.

The existing industrial operations console remains at:

```text
http://localhost:8000
```

## Scientific API

Key endpoints:

```text
GET  /api/v1/research/overview
GET  /api/v1/research/system-overview
GET  /api/v1/research/branches
POST /api/v1/research/branches
GET  /api/v1/research/branches/{branch_id}/gate
POST /api/v1/research/branches/{branch_id}/accept

GET  /api/v1/research/evidence-graph
POST /api/v1/research/evidence-graph/edges

POST /api/v1/research/branches/{branch_id}/council
GET  /api/v1/research/council
POST /api/v1/research/council/{session_id}/contributions
GET  /api/v1/research/council/{session_id}/evaluation

POST /api/v1/research/scheduler/tick
GET  /api/v1/research/scheduler/runs

GET  /api/v1/research/knowledge-evolution
POST /api/v1/research/knowledge/{knowledge_id}/challenge
POST /api/v1/research/knowledge/{knowledge_id}/revoke
POST /api/v1/research/knowledge/{knowledge_id}/revise/{replacement_knowledge_id}
POST /api/v1/research/knowledge/{knowledge_id}/supersede/{replacement_knowledge_id}
```

Interactive API documentation is available at `/docs`.

## Industrial validation domain

The original ForgeGuard industrial system remains intact and supplies a concrete domain for scientific-agent verification:

```text
Sensor / Edge / CSV input
        ↓
Data-quality gate + evidence packaging
        ↓
Fault diagnosis + RUL / health risk
        ↓
FMEA + inventory + production + workforce tools
        ↓
Multi-option maintenance planning
        ↓
Human authorization gate
        ↓
Work-order execution
        ↓
Post-maintenance reacquisition
        ↓
Verification: close incident or reopen automatically
        ↓
Audit trail + reusable knowledge
```

The system includes 13 role-bounded industrial agents for evidence quality, perception, industrial knowledge, diagnosis, reliability, safety, sustainability, resilience, planning, governance, work orders, verification, and coordination.

## Existing verifiable engineering evidence

The checked-in model benchmark uses the project-generated **ForgeGuard OpenEval-RM 0.1.0** synthetic regression dataset.

Selected deployment model: `dsp-calibrated-hgb-v0.2`

| Metric | Result |
|---|---:|
| Macro-F1 | 0.9342 |
| Balanced accuracy | 0.9375 |
| CPU p95 latency | 13.912 ms |
| Accepted accuracy after abstention | 0.9872 |
| Mean robustness Macro-F1 | 0.7166 |

The dataset is physics-informed synthetic data and is not presented as factory accuracy. See [`docs/model-benchmark-results.md`](docs/model-benchmark-results.md).

The reproducible fault-injection campaign currently reports:

| Check | Result |
|---|---:|
| Clean injected-fault classification accuracy | 1.000 |
| Corrupted-signal safe-response rate | 1.000 |
| Workflow-fault containment rate | 1.000 |

This is regression/safety-behavior evidence, not a plant safety case. See [`artifacts/fault-campaigns/latest.md`](artifacts/fault-campaigns/latest.md).

## Quick start

### Docker

```bash
git clone https://github.com/alaster-t34/ForgeGuard-Nexus.git
cd ForgeGuard-Nexus
docker compose -f compose.yaml up -d --build api
```

Open:

```text
Industrial runtime: http://localhost:8000
Research Nexus:     http://localhost:8000/ui/research.html
API docs:           http://localhost:8000/docs
Health:             http://localhost:8000/api/v1/health
```

Stop:

```bash
docker compose -f compose.yaml down
```

Native Linux, Windows launcher, and Jetson deployment instructions remain under `docs/` and `deploy/`.

## Repository layout

```text
backend/app/research_orchestration/  branches, scheduler, evidence DAG, council, knowledge evolution
backend/app/                         FastAPI, industrial agents, tools and runtime
frontend/research.html               scientific orchestration console
frontend/research.js                 research control API client and gate UI
frontend/research.css                research console design system
frontend/                            existing industrial operations console
backend/research/                    model registry and selected artifacts
backend/knowledge/                   controlled FMEA and safety knowledge
data/openeval/                       synthetic regression dataset + provenance
artifacts/                           benchmark, fault-campaign and design evidence
docs/                                architecture, research, QA and deployment docs
edge-node/                           acquisition/replay client
deploy/                              Windows/Linux/Jetson deployment scripts
```

Research runtime state is persisted atomically under `runtime-data/`:

```text
research-state.json
evidence-graph.json
research-council.json
research-scheduler.json
knowledge-evolution.json
```

## Verification

Useful entry points:

```bash
python scripts/verify_v079.py
python scripts/run_benchmarks.py --without-cnn
python scripts/run_fault_campaign.py
cd backend && pytest -q
```

`backend/tests/test_research_orchestration.py` verifies, among other invariants:

- unresolved counterexamples block acceptance;
- critic/verifier identity separation;
- Evidence Graph cycle rejection;
- five-role Council actor independence;
- accepted knowledge version bootstrap;
- Accepted → Challenged → Revoked transition;
- Scheduler fork creation from negative research state.

CI runs the backend test matrix on Linux and Windows with Python 3.11/3.12 and syntax-checks both frontend consoles.

## Data, knowledge, and safety boundaries

- OpenEval-RM is synthetic regression evidence, not factory accuracy.
- External datasets such as CWRU, Paderborn, and XJTU-SY are not redistributed.
- Raw plant/rig evidence is excluded from Git by default.
- High-risk industrial actions still require an authorized human approver.
- Maintenance incidents still require post-maintenance verification before closure.
- A research branch is **not** accepted knowledge merely because an LLM produced it.
- Accepted Knowledge can later be challenged, revised, superseded, or revoked.
- "Verified Scientific-Agent Platform" describes the platform's explicit verification machinery. It does not mean every generated claim is scientifically true, nor does it replace peer review, replication, certification, or physical safety validation.

See [`NOTICE.md`](NOTICE.md), [`SECURITY.md`](SECURITY.md), [`docs/data-compliance.md`](docs/data-compliance.md), [`docs/RESEARCH_ORCHESTRATION.md`](docs/RESEARCH_ORCHESTRATION.md), and [`docs/ADVANCED_RESEARCH_LAYERS.md`](docs/ADVANCED_RESEARCH_LAYERS.md).

## License

Apache License 2.0. Third-party, dataset, model, prior-work, and deployment boundaries are documented in [`NOTICE.md`](NOTICE.md).
