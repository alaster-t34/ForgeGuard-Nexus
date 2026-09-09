# ForgeGuard Nexus

**Verified Scientific-Agent Platform for research orchestration, evidence-governed reasoning, and industrial AI verification.**

> Version: **v0.8.0**  
> First verified domain: **industrial rotating machinery / maintenance agents**  
> License: **Apache-2.0**

ForgeGuard started as an evidence-driven Industrial 5.0 maintenance-agent system. v0.8.0 adds the missing layer above those agents: a **research orchestration layer** that treats questions, hypotheses, evidence, counterexamples, experiments, independent criticism, verification, and accepted knowledge as first-class objects.

The industrial workflow is still fully supported. It is now the platform's first scientific/engineering validation domain rather than the definition of the whole product.

## The core idea

A useful scientific-agent system should not let one model generate a hypothesis, grade its own evidence, dismiss its own counterexamples, and then promote the result to "knowledge" because it sounded convincing.

ForgeGuard separates those responsibilities:

```text
Research Question
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
Research Gate
Hypothesis
   ↓
Evidence + negative-result handling
   ↓
Independent critic
   ↓
Independent verifier
   ↓
Accepted Knowledge
```

## Research Branches

Every branch persists:

```text
Question
Hypothesis
Evidence
Counterexample
Experiment
Result
Status
```

Branches can be active, blocked, under review, verified, rejected, or archived. An unresolved counterexample blocks acceptance instead of becoming an inconvenient paragraph that mysteriously disappears from the final answer.

## Cross-pollination

Branches can send compact research-transfer packets to other branches:

```text
Best lemma
Best negative result
Unresolved obstacle
Useful tool
```

This is designed to move both progress and failure information across parallel research paths. Negative results are useful state, not discarded chat history.

## Deterministic Research Gate

Promotion into Accepted Knowledge is controlled by explicit checks. The current gate requires:

- a recorded hypothesis;
- evidence;
- no unresolved counterexample;
- a recorded result;
- reproducible evidence/experiment or formal proof/derivation support;
- a passing independent critic review;
- a passing verifier review;
- different critic and verifier actor identities;
- verifier coverage of all current evidence.

Model confidence is not an acceptance criterion.

See [`docs/RESEARCH_ORCHESTRATION.md`](docs/RESEARCH_ORCHESTRATION.md) for the complete state model and API.

## Research Console

Start ForgeGuard and open:

```text
http://localhost:8000/ui/research.html
```

The Research Nexus console shows:

- branch overview and status;
- Question / Hypothesis / Evidence / Counterexample / Experiment / Result / Status;
- live deterministic Gate reports;
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
GET  /api/v1/research/branches
POST /api/v1/research/branches
GET  /api/v1/research/branches/{branch_id}/gate
POST /api/v1/research/branches/{branch_id}/accept
GET  /api/v1/research/accepted-knowledge
GET  /api/v1/research/cross-pollination
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
backend/app/research_orchestration/  research branches, gate, accepted knowledge
backend/app/                         FastAPI, industrial agents, tools and runtime
frontend/research.html               scientific orchestration console
frontend/research.js                 research API client and gate UI
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

Research runtime state is stored in `runtime-data/research-state.json` and uses atomic replacement on writes.

## Verification

Useful entry points:

```bash
python scripts/verify_v079.py
python scripts/run_benchmarks.py --without-cnn
python scripts/run_fault_campaign.py
cd backend && pytest -q
```

`backend/tests/test_research_orchestration.py` specifically verifies that unresolved counterexamples block acceptance, critic/verifier identity separation is enforced, and a fully reviewed branch can enter Accepted Knowledge.

CI runs the backend test matrix on Linux and Windows with Python 3.11/3.12 and syntax-checks both frontend consoles.

## Data, knowledge, and safety boundaries

- OpenEval-RM is synthetic regression evidence, not factory accuracy.
- External datasets such as CWRU, Paderborn, and XJTU-SY are not redistributed.
- Raw plant/rig evidence is excluded from Git by default.
- High-risk industrial actions still require an authorized human approver.
- Maintenance incidents still require post-maintenance verification before closure.
- A research branch is **not** accepted knowledge merely because an LLM produced it.
- "Verified Scientific-Agent Platform" describes the platform's explicit verification machinery. It does not mean every generated claim is scientifically true, nor does it replace peer review, replication, certification, or physical safety validation.

See [`NOTICE.md`](NOTICE.md), [`SECURITY.md`](SECURITY.md), [`docs/data-compliance.md`](docs/data-compliance.md), and [`docs/RESEARCH_ORCHESTRATION.md`](docs/RESEARCH_ORCHESTRATION.md).

## License

Apache License 2.0. Third-party, dataset, model, prior-work, and deployment boundaries are documented in [`NOTICE.md`](NOTICE.md).
