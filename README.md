# ForgeGuard Nexus

**Verified Scientific-Agent Platform for controlled autonomous research orchestration, evidence-governed reasoning, and industrial AI verification.**

> Version: **v0.10.0**  
> First verified domain: **industrial rotating machinery / maintenance agents**  
> License: **Apache-2.0**

ForgeGuard started as an evidence-driven Industrial 5.0 maintenance-agent system. It now treats scientific work itself as a governed runtime:

- v0.8 introduced Research Branches, Cross-pollination, deterministic gates, independent criticism, verification, and Accepted Knowledge.
- v0.9 added the Research Scheduler, persistent Evidence DAG, five-role Adversarial Research Council, and versioned Knowledge Evolution.
- **v0.10 adds a controlled autonomous research loop:** registered automatic experiments, literature retrieval into the Evidence Graph, branch resource budgets, research-lineage scoring, and contradiction propagation.

The industrial workflow remains intact as ForgeGuard's first scientific/engineering validation domain rather than the definition of the whole platform.

## Core research lifecycle

```text
Research Question
      |
      v
Research Scheduler
 generate / fork / kill
      |
      v
Research Branch
 Question / Hypothesis / Evidence / Counterexample
 Experiment / Result / Status
      |
      +-------------------------+
      |                         |
      v                         v
Literature Retrieval     Controlled Experiments
      |                         |
      +------------+------------+
                   v
              Evidence DAG
                   |
                   v
          Branch Resource Budget
                   |
                   v
          Research Lineage Score
                   |
                   v
 Independent Critic + Verifier
                   |
                   v
   Adversarial Research Council
 Researcher / Devil's Advocate
 Literature Critic / Experiment Critic
 Formal Verifier
                   |
                   v
          Accepted Knowledge v1
                   |
              new contradiction
                   v
              Challenged
          /          |          \
     Revised      Revoked     Superseded
        |                         |
        +------> Accepted v2 <----+
```

The platform does not use model confidence as a promotion criterion.

## Research Scheduler

The scheduler consumes recorded research state and can:

- generate branches from unresolved cross-pollination obstacles;
- fork around unresolved counterexamples;
- fork failed or inconclusive experiments into recovery branches;
- create revalidation branches when Accepted Knowledge is challenged;
- archive rejected branches or branches with terminal Council failures.

Every decision is persisted with its source, target, trigger, reason, and timestamp.

## Evidence Graph

Branch arrays remain for API compatibility, but scientific relationships are mirrored into a persistent DAG.

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

Relations include:

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

Any edge that would create a cycle is rejected before persistence. Circular provenance therefore cannot quietly become an argument just because enough arrows were drawn.

## Adversarial Research Council

A branch cannot enter Accepted Knowledge until a five-role Council passes:

1. Researcher
2. Devil's Advocate
3. Literature Critic
4. Experiment Critic
5. Formal Verifier

Actor IDs must be distinct. Role-specific graph coverage is enforced, and FAIL, REVISE, or blocking objections prevent promotion.

## Knowledge Evolution

Accepted Knowledge is explicitly revisable:

```text
Accepted v1
    |
    v
Challenged
    |
    +--> Revised ------> Accepted v2
    +--> Superseded ---> Accepted replacement
    +--> Revoked
```

Historical versions are preserved. Revision or supersession can only point to replacement knowledge that has independently passed the full Research Gate and Council.

## v0.10 autonomous research loop

### Controlled automatic experiments

ForgeGuard does **not** expose arbitrary shell or Python execution through the research API. Automatic experiments must use registered deterministic executors:

- `numeric_threshold`
- `graph_integrity`
- `evidence_replay`
- `branch_consistency`

Every run:

1. consumes the branch resource budget before execution;
2. creates a normal ExperimentRecord;
3. executes a registered handler;
4. writes the result back through the research service;
5. updates the Evidence DAG;
6. records a stable `forgeguard://autonomy/experiments/...` artifact URI.

### Literature retrieval into the Evidence Graph

The autonomy layer reuses ForgeGuard's existing policy-controlled `SearchBroker` rather than inventing a parallel retrieval stack.

Depending on configuration, retrieval can use:

- controlled local knowledge;
- OpenAlex;
- Crossref;
- optional SearXNG.

External retrieval remains gated by ForgeGuard settings. Citations retain source URL, provider, publication date, query, and relation metadata.

A retrieved work can be ingested as:

- `context`: literature evidence;
- `support`: literature evidence supporting the current research context;
- `challenge`: negative evidence / counterexample.

Challenge-mode literature immediately participates in contradiction propagation.

### Branch resource budgets

Each research branch has persistent limits for:

- automatic experiment runs;
- literature queries;
- citations ingested;
- compute units.

Operations that would exceed a limit are rejected before the expensive action begins. The budget is a research-governance primitive, not a billing system.

### Research lineage scoring

Each branch receives a deterministic 0-100 process score based on recorded state:

- evidence accumulation;
- experiment accumulation;
- negative-result resolution;
- verified status;
- lineage fertility / useful descendants;
- budget efficiency.

Rejected/archived branches and unresolved counterexamples receive penalties.

The lineage score is a scheduling and triage signal, **not a probability that the hypothesis is scientifically true**.

### Knowledge contradiction propagation

A new counterexample on an ancestor branch propagates to every descendant branch as inherited negative evidence. Descendants become blocked until the inherited contradiction is addressed.

When Accepted Knowledge is challenged, the same mechanism pushes a revalidation obligation into descendant branches and records affected knowledge IDs.

Inherited records carry `propagated:` provenance markers so the operation is auditable and cannot recursively fan out forever.

See [`docs/AUTONOMOUS_RESEARCH_LOOP.md`](docs/AUTONOMOUS_RESEARCH_LOOP.md).

## Cross-pollination

Research branches can propagate compact packets containing:

```text
Best lemma
Best negative result
Unresolved obstacle
Useful tool
```

Negative results are retained as useful state instead of being discarded as inconvenient chat history.

## Deterministic Research Gate

Promotion into Accepted Knowledge requires:

- a recorded falsifiable hypothesis;
- evidence;
- no unresolved counterexample;
- a recorded result;
- reproducible evidence/experiment or formal proof/derivation support;
- a passing independent critic review;
- a passing verifier review;
- distinct critic and verifier actor identities;
- verifier coverage of all current evidence;
- an acyclic Evidence Graph;
- a passing five-role Adversarial Research Council.

Model confidence is deliberately not on the list.

## Research Console

Start ForgeGuard and open:

```text
http://localhost:8000/ui/research.html
```

The existing industrial operations console remains at:

```text
http://localhost:8000
```

Interactive API documentation is available at `/docs`.

## Scientific API

Core endpoints include:

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

GET  /api/v1/research/autonomy/overview
GET  /api/v1/research/budgets
GET  /api/v1/research/branches/{branch_id}/budget
POST /api/v1/research/branches/{branch_id}/budget
POST /api/v1/research/branches/{branch_id}/auto-experiments
GET  /api/v1/research/auto-experiments
POST /api/v1/research/branches/{branch_id}/literature
GET  /api/v1/research/literature-runs
GET  /api/v1/research/lineage-scores
POST /api/v1/research/branches/{branch_id}/counterexamples/{counterexample_id}/propagate
GET  /api/v1/research/contradictions
```

## Industrial validation domain

The original ForgeGuard industrial workflow remains intact:

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

The system includes 13 role-bounded industrial agents covering evidence quality, perception, industrial knowledge, diagnosis, reliability, safety, sustainability, resilience, planning, governance, work orders, verification, and coordination.

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

Stop with:

```bash
docker compose -f compose.yaml down
```

## Repository layout

```text
backend/app/research_orchestration/  branches, scheduler, DAG, council, evolution, autonomy
backend/app/                         FastAPI, industrial agents, tools and runtime
frontend/research.html               scientific orchestration console
frontend/                            existing industrial operations console
backend/research/                    model registry and selected artifacts
backend/knowledge/                   controlled FMEA and safety knowledge
data/openeval/                       synthetic regression dataset + provenance
artifacts/                           benchmark, fault-campaign and design evidence
docs/                                architecture, research, QA and deployment docs
edge-node/                           acquisition/replay client
deploy/                              Windows/Linux/Jetson deployment scripts
```

Research state is persisted atomically under `runtime-data/`:

```text
research-state.json
evidence-graph.json
research-council.json
research-scheduler.json
knowledge-evolution.json
research-autonomy.json
```

## Verification

Useful entry points:

```bash
python scripts/verify_v079.py
python scripts/run_benchmarks.py --without-cnn
python scripts/run_fault_campaign.py
cd backend && pytest -q
```

Research regression tests cover gate invariants, Evidence Graph cycle rejection, Council independence, Knowledge Evolution, Scheduler behavior, budget exhaustion, controlled automatic experiments, literature ingestion, lineage scoring, and contradiction propagation.

CI runs the backend test matrix on Linux and Windows with Python 3.11/3.12 and syntax-checks both frontend consoles.

## Data, knowledge, autonomy, and safety boundaries

- OpenEval-RM is synthetic regression evidence, not factory accuracy.
- External datasets such as CWRU, Paderborn, and XJTU-SY are not redistributed.
- Raw plant/rig evidence is excluded from Git by default.
- High-risk industrial actions still require an authorized human approver.
- Maintenance incidents still require post-maintenance verification before closure.
- A research branch is not Accepted Knowledge merely because an LLM produced it.
- Accepted Knowledge can later be challenged, revised, superseded, or revoked.
- Automatic research experiments are registered deterministic executors, not arbitrary remote code execution.
- Literature retrieval is policy-controlled and external network use is configuration-gated.
- A lineage score describes recorded research process quality; it is not scientific truth probability.
- "Verified Scientific-Agent Platform" describes explicit verification machinery. It does not mean every generated claim is true, nor does it replace peer review, replication, certification, or physical safety validation.

See [`NOTICE.md`](NOTICE.md), [`SECURITY.md`](SECURITY.md), [`docs/data-compliance.md`](docs/data-compliance.md), [`docs/RESEARCH_ORCHESTRATION.md`](docs/RESEARCH_ORCHESTRATION.md), [`docs/ADVANCED_RESEARCH_LAYERS.md`](docs/ADVANCED_RESEARCH_LAYERS.md), and [`docs/AUTONOMOUS_RESEARCH_LOOP.md`](docs/AUTONOMOUS_RESEARCH_LOOP.md).

## License

Apache License 2.0. Third-party, dataset, model, prior-work, and deployment boundaries are documented in [`NOTICE.md`](NOTICE.md).
