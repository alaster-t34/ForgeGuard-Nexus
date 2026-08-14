# ForgeGuard model benchmark

Run: `BMR-20260723T124116Z`  
Dataset: **ForgeGuard OpenEval-RM 0.1.0**  
Split: Machine-group split: simulated machine IDs 00-08 train, 09-10 validation, 11-13 test. No window from a machine appears in multiple splits.

| Model | Macro-F1 | Balanced acc. | ECE | p95 latency (ms) | Robust mean F1 |
|---|---:|---:|---:|---:|---:|
| `dsp-calibrated-rf-v0.2` | 0.9590 | 0.9583 | 0.1686 | 47.318 | 0.6619 |
| `dsp-calibrated-et-v0.2` | 0.9168 | 0.9167 | 0.1169 | 47.587 | 0.6683 |
| `dsp-calibrated-hgb-v0.2` | 0.9342 | 0.9375 | 0.1590 | 13.912 | 0.7166 |
| `dsp-calibrated-logreg-v0.2` | 0.9590 | 0.9583 | 0.2862 | 0.863 | 0.0588 |
| `dsp-calibrated-rbf-svm-v0.2` | 0.9590 | 0.9583 | 0.2967 | 1.432 | 0.0421 |

Selected model: **`dsp-calibrated-hgb-v0.2`**

Selection rule: 0.45 macro-F1 + 0.20 balanced accuracy + 0.20 mean robustness macro-F1 + 0.15 calibration term - latency penalty

## Scientific boundary

- OpenEval-RM is an openly redistributable, physics-informed regression benchmark.
- It does not establish real-factory accuracy.
- External CWRU, Paderborn, XJTU-SY, MVTec AD and MVTec AD 2 evaluations must be reported separately with their source licenses.
- Physical-rig measurements must include sensor placement, calibration, sampling, load, speed and acquisition timestamps.
