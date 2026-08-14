# Agent Contracts

Each Agent accepts an `IncidentRecord`, returns a validated Pydantic contract and emits a `TraceStep`.

| Agent | Required input | Output | Hard safety rule |
|---|---|---|---|
| Evidence Quality | Raw incident input | Evidence quality item | May force reacquisition |
| Diagnosis | Evidence ledger | DiagnosisResult | Must expose contradictions |
| Reliability | Diagnosis + telemetry | ReliabilityResult | RUL is a quantile interval |
| Human Safety | Reliability + operating state | SafetyAssessment | Approval and LOTO constraints |
| Sustainability | Asset energy + incident | SustainabilityAssessment | Estimates must list assumptions |
| Resilience | Inventory + production + workforce | ResilienceAssessment | Must provide offline fallback |
| Planner | All assessments | MaintenancePlan | Contraindicated options cannot be auto-recommended |
| Governance | Plan + human decision | HumanApproval | High-risk tools remain blocked without approval |
| Verification | Pre/post evidence | VerificationResult | No incident close without pass |

Tool calls are recorded with risk, arguments, status, result summary and error. A language model never receives direct access to `work_order.issue`.
