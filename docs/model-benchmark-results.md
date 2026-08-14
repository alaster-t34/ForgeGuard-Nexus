# Vibration model benchmark results

This report is generated from `artifacts/benchmarks/latest.json`. The benchmark trains real executable models; it does not substitute synthetic performance for real-plant validation.

## Protocol

- Dataset: **ForgeGuard OpenEval-RM 0.1.0**.
- Train/validation/test: **288 / 64 / 96** windows.
- Split: Machine-group split: simulated machine IDs 00-08 train, 09-10 validation, 11-13 test. No window from a machine appears in multiple splits.
- Labels: normal, imbalance, misalignment, outer_race, inner_race, ball, lubrication, looseness.
- Calibration uses the validation machines; test labels are not used for threshold or model fitting.
- Robustness slices are applied only after the held-out split is fixed: low SNR, speed shift, dropout, clipping, drift and sparse impulse interference.

## Results

| Model | Macro-F1 | Balanced acc. | ECE | p95 latency (ms) | Robust mean F1 |
|---|---:|---:|---:|---:|---:|
| `dsp-calibrated-rf-v0.2` | 0.9590 | 0.9583 | 0.1686 | 47.318 | 0.6619 |
| `dsp-calibrated-et-v0.2` | 0.9168 | 0.9167 | 0.1169 | 47.587 | 0.6683 |
| `dsp-calibrated-hgb-v0.2` | 0.9342 | 0.9375 | 0.1590 | 13.912 | 0.7166 |
| `dsp-calibrated-logreg-v0.2` | 0.9590 | 0.9583 | 0.2862 | 0.863 | 0.0588 |
| `dsp-calibrated-rbf-svm-v0.2` | 0.9590 | 0.9583 | 0.2967 | 1.432 | 0.0421 |

Selected deployment artifact: **`dsp-calibrated-hgb-v0.2`**.

Selection rule: 0.45 macro-F1 + 0.20 balanced accuracy + 0.20 mean robustness macro-F1 + 0.15 calibration term - latency penalty.

## Interpretation

The selected histogram-gradient-boosting model is not called universally best. It wins this disclosed benchmark because it preserves materially more performance under signal corruption than the faster linear and kernel baselines, while remaining CPU-deployable. The random-forest baseline has high clean accuracy but lower composite performance.

## Mandatory next evidence

1. Download CWRU and Paderborn from their official sources and execute the included leakage-resistant `run_external_benchmark.py` pipeline; no third-party recordings are bundled.
2. XJTU-SY run-to-failure evaluation for degradation and RUL.
3. Physical-rig data with disclosed sensor, mounting, sampling, speed, load and fault specimen.
4. Repeated-seed confidence intervals and per-class confusion matrices.
5. Deployment latency on the actual competition computer and at least one edge target.

The current result is valid evidence of executable model selection and robustness engineering. It is not evidence of production accuracy.
