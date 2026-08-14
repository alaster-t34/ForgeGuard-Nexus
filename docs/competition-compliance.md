# GOAI Boundless Agents compliance matrix

This document maps the implementation to the official competition requirements. It is a development control document, not marketing copy.

| Competition requirement | ForgeGuard implementation | Verifiable evidence |
|---|---|---|
| Real industry scenario | Rotating-equipment health management for maintenance and production teams | Seed asset, simulated/real edge inputs, explicit user roles |
| Agent capability | Typed perception, diagnosis, reliability, planning, work-order, verification, and governance roles | `/api/v1/incidents/{id}` trace |
| Complete task loop | Anomaly input → evidence → diagnosis → RUL → plan → approval → work order → verification | UI demo and `test_closed_loop.py` |
| Tool use | Asset master, FMEA retrieval, inventory, production context, work-order system | `tool_calls` audit array |
| Knowledge enhancement | Controlled FMEA and safety knowledge with citations | `knowledge/` and knowledge evidence items |
| Multi-modal data | Vibration, temperature, speed/load, acoustic/current fields, image observations and raw bench windows | Incident input schema, BenchGateway, rig campaign manifest and evidence archive |
| Multi-round interaction | Scenario input, option selection, human approval, post-maintenance verification | Web console workflow |
| Failure handling | Unknown asset/campaign, invalid state, low-quality/conflicting evidence, duplicate mutation, network outage spool, injected error/timeout/empty tool result, unresolved verification | HTTP handling, idempotency tests, edge spool, fault campaign and conflict scenario |
| Product experience | Responsive industrial control console, structured evidence and plan comparison | Browser screenshot and live UI |
| Reproducibility | Dependency-light frontend, deterministic backend path, public OpenEval set, executable synthetic and user-downloaded real-data benchmarks, tests, Docker/Make targets | `data/openeval`, `run_external_benchmark.py`, benchmark reports, README and tests |
| Safety boundary | No direct production control; high-risk actions require authorized approval | governance notes and high-risk tool gate |
| Data compliance | Synthetic demo data; real data requires authorization and minimization | `data-compliance.md` |
| Open reuse | Hardware/model/tool adapter interfaces and Apache-2.0 core | `edge-node`, model registry, license |
| Edge deployment evidence | Jetson AGX Orin reference profile with platform discovery, strict preflight, replay mode, and wipe/deployment controls | `deploy/jetson-5`, `docs/jetson-deployment.md`, edge platform metadata |

## Red-line controls

- The product does not directly start, stop, or release real production equipment.
- Continued operation and maintenance timing remain decisions of authorized personnel.
- Low-quality or contradictory evidence triggers reacquisition or escalation.
- Every high-risk tool call is blocked until the workflow records human approval.
- Existing user models and third-party models are disclosed separately from new code.
