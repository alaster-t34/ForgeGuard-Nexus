# System architecture

```text
Sensors / Cameras / Files / Enterprise APIs
                 │
       Hardware-neutral Edge Node
                 │ typed observations
                 ▼
       Evidence & Tool Gateway
   asset · FMEA · inventory · MES · search
                 │ audited calls
                 ▼
┌──────────────────────────────────────────────┐
│ Agent workflow                              │
│ perception → diagnosis → reliability        │
│              → maintenance planner          │
│              → human governance             │
│              → work order → verification    │
└──────────────────────────────────────────────┘
                 │
       Evidence bundle + UI + API
```

## Invariants

1. A plan cannot be created without diagnosis and reliability results.
2. A work order cannot be issued without a valid selected option and human approval.
3. An incident cannot be resolved without post-maintenance verification.
4. Conflicting/poor evidence cannot silently become a certain diagnosis.
5. External search and enterprise tools are called through registered contracts only.
