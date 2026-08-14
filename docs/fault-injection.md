# Fault-injection and resilience protocol

ForgeGuard tests both the physical evidence path and the enterprise-tool path. Fault injection is deterministic, seeded and recorded.

## Signal faults

Physical signatures:

- imbalance;
- misalignment;
- outer-race, inner-race and ball defects using bearing characteristic frequencies;
- lubrication degradation;
- mechanical looseness.

Sensor and acquisition faults:

- controlled low SNR;
- contiguous dropout;
- bias drift;
- ADC clipping;
- reduced effective bit depth;
- speed/context inconsistency;
- sparse impulse interference.

The integrity gate checks clipping, dropout, DC offset, effective amplitude resolution, spectral noise floor, sparse impulses and RPM/order consistency. A corrupt channel is not silently treated as a reliable mechanical fault.

## Workflow faults

`ToolRegistry` can inject an error, timeout or empty result into a named tool for a bounded number of calls. Every failure still produces a completed audit record with status, error and timestamps. The mechanism is intended for tests and controlled demonstrations, not production sabotage.

## Latest automated campaign

- clean physical-fault classification accuracy: **1.000**;
- corrupted-signal safe-response rate: **1.000**;
- workflow-fault containment rate: **1.000**.

Artifacts:

- `artifacts/fault-campaigns/latest.json`;
- `artifacts/fault-campaigns/latest.md`;
- raw evidence under `artifacts/bench-evidence/`.

## Run

```bash
PYTHONPATH=backend python scripts/run_fault_campaign.py --seed 43
```

## Safety boundary

These tests validate software behavior and evidence handling. They do not authorize destructive testing on a machine. Physical fault seeding, overspeed, overload and lubrication starvation require a guarded test rig, written procedure and competent supervision.
