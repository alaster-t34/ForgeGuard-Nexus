# Research basis and benchmark plan

ForgeGuard does not label a model "best" merely because it is recent. Candidate models enter the platform only through a declared adapter, license review, leakage-free evaluation, calibration, latency measurement, and an explicit fallback path.

## Verified research basis

| Work | Intended role | Adoption status | Publicly explainable boundary |
|---|---|---|---|
| AssetOpsBench, arXiv:2506.03828 | Industrial asset agent tasks, MCP-style tools, work-order evaluation | Architecture and evaluation reference | ForgeGuard does not copy its scenarios as proprietary work; our new scope is real edge evidence, contradiction-aware maintenance decisions, proof-carrying work orders and post-maintenance verification. |
| BearLLM, arXiv:2408.11281 | Unified vibration-language bearing health reasoning | Research adapter candidate | Not shipped as a trained model. It must pass cross-machine, cross-load and leakage-free testing before activation. |
| IndusAgent, arXiv:2605.20682 | Tool-augmented open-vocabulary visual anomaly reasoning | Research adapter candidate | We adopt the active crop/enhance/retrieve pattern, not unverified benchmark claims or undisclosed weights. |
| Triad, arXiv:2503.13184 | Manufacturing-process-aware multimodal anomaly reasoning | Evaluation candidate | Useful for ambiguous surface defects; requires a domain-specific instruction and calibration study. |
| ECHO, arXiv:2508.14689 | Frequency-aware machine-signal foundation representation | Evaluation candidate | Compared against DSP and supervised baselines; not allowed to replace interpretable checks without evidence. |
| THEMIS, arXiv:2510.03911 | Foundation embeddings for time-series anomaly detection | Evaluation candidate | Requires independent reproduction and robustness tests before production use. |
| Anomalib 2.x | Reproducible visual anomaly training/deployment portfolio | Optional adapter implemented | A model is chosen by validation data, latency, memory, calibration and license, not by name or leaderboard alone. |

## Model selection gates

Every model candidate must satisfy all applicable gates:

1. **Data split integrity:** asset-wise or machine-wise separation; no test-label threshold tuning.
2. **Domain declaration:** camera, lighting, part geometry, load, speed, sensor placement and sampling rate.
3. **Calibration:** reliability diagram, expected calibration error and threshold stability.
4. **Robustness:** missing channel, corrupted channel, domain shift, noise, blur, illumination and load/speed shift.
5. **Uncertainty:** abstention/coverage curves and a human escalation policy.
6. **Latency and resources:** p50/p95 latency, memory, model size and power envelope on the declared target.
7. **Operational value:** false-alarm cost, missed-failure cost, lead time and work-order usefulness.
8. **Reproducibility:** fixed configuration, model/data hashes, environment lock and repeatable report.
9. **License and provenance:** code, model, dataset and generated-data disclosures.
10. **Safety invariant:** model output cannot bypass approval, verification or equipment-control boundaries.

## Competition evaluation pack

The release will maintain machine-readable evaluation artifacts:

```text
evals/
├── visual_anomaly/
├── vibration_diagnosis/
├── rul_uncertainty/
├── retrieval_grounding/
├── agent_trajectory/
├── safety_red_team/
└── closed_loop_business_value/
```

Minimum reported metrics:

- visual: image AUROC, pixel AUROC/AUPRO where applicable, F1 at a fixed validation threshold, calibration error;
- vibration: macro F1, cross-machine performance, noise/load/speed robustness and abstention quality;
- RUL: RMSE, MAE, calibration/coverage of p10-p90, early/late risk asymmetry and per-asset results;
- retrieval: Recall@K, evidence precision, citation correctness and unsupported-claim rate;
- agent: task completion, tool correctness, state-transition validity, intervention rate, cost and latency;
- business loop: time-to-triage, work-order completeness, false escalation rate and verification pass/reopen rate.
