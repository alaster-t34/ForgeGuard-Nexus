# ForgeGuard Nexus 5.0

**Evidence-driven industrial maintenance agents with human-governed execution and post-maintenance verification.**

ForgeGuard Nexus is an Industrial AI Agent platform for rotating machinery and critical assets. It does not stop at fault classification: it connects equipment evidence, data-quality gating, diagnosis, RUL/risk, FMEA knowledge, inventory, production context, workforce constraints, human approval, work orders, and post-maintenance verification into one auditable task loop.

> GOAI Boundless Agents track: **AI + Industrial Manufacturing**  
> Release candidate: **v0.7.9**  
> License: **Apache-2.0**

## Why ForgeGuard

A conventional predictive-maintenance model may tell an engineer that a bearing looks abnormal. A real maintenance decision still has to answer:

- Is the evidence trustworthy enough to act on?
- What is the likely failure mode and remaining risk window?
- Is the right spare part available?
- Is a qualified technician available?
- What production window minimizes operational impact?
- Which action is safe enough to approve?
- After maintenance, how do we prove the asset actually recovered?

ForgeGuard turns those questions into a governed Agent workflow instead of a single model output or a generic chat interface.

## End-to-end task loop

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

Safety invariants are deterministic: a plan cannot bypass required evidence, a high-risk work order cannot bypass approval, and an incident cannot be resolved without post-maintenance verification.

## What is implemented

- 13 role-bounded Agents covering data quality, perception, industrial knowledge, diagnosis, RUL/risk, human safety, energy/environment, resilience, maintenance planning, governance, work orders, verification, and coordination.
- Real-time / near-real-time signal input, HTTP frames, serial acquisition, CSV replay, and historical CSV analysis.
- Vibration quality checks for clipping, dropout, DC offset, effective resolution, noise inconsistency, and conflicting evidence.
- Interpretable time/frequency/envelope features and a CPU-deployable vibration baseline.
- Inventory, production, technician-skill, asset, FMEA, work-order, and audit tools.
- Human-in-the-loop approval for high-risk actions.
- Post-maintenance verification that can reject closure and reopen an incident.
- Docker, Windows/Linux native, and Jetson deployment paths.
- Deterministic core workflow that does not require a commercial LLM or API key.

## Verifiable evidence

### Model benchmark

The checked-in benchmark report is generated from `artifacts/benchmarks/latest.json` on the project-generated **ForgeGuard OpenEval-RM 0.1.0** synthetic regression dataset.

Selected deployment model: `dsp-calibrated-hgb-v0.2`

| Metric | Result |
|---|---:|
| Macro-F1 | 0.9342 |
| Balanced accuracy | 0.9375 |
| CPU p95 latency | 13.912 ms |
| Accepted accuracy after abstention | 0.9872 |
| Mean robustness Macro-F1 | 0.7166 |

The dataset is physics-informed synthetic data and is not presented as factory accuracy. See [`docs/model-benchmark-results.md`](docs/model-benchmark-results.md).

### Fault-injection campaign

The reproducible software/signal fault campaign reports:

| Check | Result |
|---|---:|
| Clean injected-fault classification accuracy | 1.000 |
| Corrupted-signal safe-response rate | 1.000 |
| Workflow-fault containment rate | 1.000 |

This is regression/safety-behavior evidence, not a plant safety case. See [`artifacts/fault-campaigns/latest.md`](artifacts/fault-campaigns/latest.md).

## Quick start

### Docker - recommended

Requirements: Docker Engine/Desktop with Compose v2.

```bash
git clone <YOUR_REPOSITORY_URL>
cd ForgeGuard-Nexus
docker compose -f compose.yaml up -d --build api
```

Open:

```text
http://localhost:8000
```

Health endpoint:

```text
http://localhost:8000/api/v1/health
```

Stop:

```bash
docker compose -f compose.yaml down
```

### Linux native

See [`docs/NATIVE_ENVIRONMENT_ZH.md`](docs/NATIVE_ENVIRONMENT_ZH.md) and `deploy/linux/`.

### Windows native / desktop launcher

Source for the Windows launcher is included in `windows-launcher/`. Prebuilt EXE files are intentionally kept out of Git history and should be published as GitHub Release assets. See [`docs/WINDOWS_EXE_ZH.md`](docs/WINDOWS_EXE_ZH.md).

### Jetson

See [`docs/jetson-deployment.md`](docs/jetson-deployment.md) and `deploy/jetson-5/`.

## GOAI competition package

Competition-specific material is consolidated under [`docs/goai/`](docs/goai/):

- [`GOAI_SUBMISSION_ZH.md`](docs/goai/GOAI_SUBMISSION_ZH.md) - judge-facing project narrative and requirement mapping.
- [`DEMO_SCRIPT_2MIN_ZH.md`](docs/goai/DEMO_SCRIPT_2MIN_ZH.md) - 2-minute hero demo storyboard.
- [`SUBMISSION_CHECKLIST_ZH.md`](docs/goai/SUBMISSION_CHECKLIST_ZH.md) - final submission checklist.
- [`GITHUB_PUBLISH_ZH.md`](docs/goai/GITHUB_PUBLISH_ZH.md) - clean repository publishing steps.
- [`RELEASE_ASSETS_ZH.md`](docs/goai/RELEASE_ASSETS_ZH.md) - files intentionally excluded from Git history and where to publish them.
- [`submission/project-intro-500zh.txt`](docs/goai/submission/project-intro-500zh.txt) - compressed project description for the preliminary submission form.
- Existing preliminary PPT/PDF are preserved in [`docs/goai/submission/`](docs/goai/submission/).

## Repository layout

```text
backend/                 FastAPI backend, Agent workflow, tools, benchmark code
edge-node/               hardware-neutral edge acquisition/replay client
frontend/                dependency-light web console
backend/knowledge/       controlled FMEA and safety knowledge
backend/research/        model registry and selected model artifacts
data/openeval/           open synthetic regression dataset + provenance
artifacts/benchmarks/    benchmark reports
artifacts/fault-campaigns/ fault-injection results
artifacts/design/        design assets
deploy/                  Windows/Linux/Jetson deployment scripts
scripts/                 benchmark, verification and packaging utilities
docs/                    architecture, QA, compliance and deployment docs
docs/goai/               competition-facing package
simulator/               deterministic demo/replay inputs
windows-launcher/        Windows launcher source
```

## Data and model boundary

- OpenEval-RM is project-generated synthetic data for reproducible regression and robustness testing.
- CWRU, Paderborn, XJTU-SY and other external datasets are not redistributed; users must obtain them from their official sources under the corresponding terms.
- Raw plant/rig evidence is excluded from Git by default.
- Production inference uses the portable NPZ artifact; model provenance and benchmark scope are documented.
- Synthetic/public/physical-rig evidence must remain clearly separated in any publication or competition claim.

See [`NOTICE.md`](NOTICE.md), [`docs/data-compliance.md`](docs/data-compliance.md), and [`docs/external-dataset-licenses.md`](docs/external-dataset-licenses.md).

## Safety boundary

ForgeGuard is a decision-support system. It does **not** directly authorize or control real production equipment. High-risk actions require an authorized human approver and enterprise safety procedures. Low-quality or contradictory evidence triggers reacquisition/escalation rather than a forced deterministic maintenance conclusion.

See [`SECURITY.md`](SECURITY.md) and [`docs/competition-compliance.md`](docs/competition-compliance.md).

## Tests and verification

Useful entry points:

```bash
python scripts/verify_v079.py
python scripts/run_benchmarks.py --without-cnn
python scripts/run_fault_campaign.py
```

Backend tests live in `backend/tests/`; edge tests live in `edge-node/tests/`. GitHub Actions are configured in `.github/workflows/ci.yml`.

## Full product documentation

The original long-form Chinese README is preserved at [`docs/README_FULL_ZH.md`](docs/README_FULL_ZH.md).

## License

Apache License 2.0. Third-party, dataset, model, prior-work, and deployment boundaries are documented in [`NOTICE.md`](NOTICE.md).
