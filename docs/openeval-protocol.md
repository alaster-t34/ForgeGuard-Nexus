# ForgeGuard OpenEval-RM protocol

OpenEval-RM is an openly redistributable, deterministic rotating-machinery evaluation set. It exists so the complete model and Agent pipeline can be reproduced without private factory data or a paid cloud API.

## What it contains

- waveform tensor in compressed NumPy form;
- eight labels: normal, imbalance, misalignment, outer race, inner race, ball, lubrication and looseness;
- machine-group train, validation and test splits;
- RPM, load, severity, simulated machine identity and provenance for every sample;
- SHA-256 hash and machine-readable manifest;
- submission template and standalone scoring code.

## What it does not claim

OpenEval-RM is physics-informed synthetic data. It is suitable for:

- regression tests;
- robustness comparisons;
- fault-injection campaigns;
- model API validation;
- public competition reproducibility.

It is not a replacement for CWRU, Paderborn, XJTU-SY, MVTec or a physical test rig, and it must not be described as factory data.

## Split integrity

Samples are grouped by simulated machine identity. A machine cannot appear in more than one split. Calibration and model selection use the validation machines only. The test set remains untouched until final evaluation.

## Build and score

```bash
PYTHONPATH=backend python scripts/build_openeval.py
PYTHONPATH=backend python scripts/score_openeval.py --write-template
PYTHONPATH=backend python scripts/score_openeval.py my_predictions.csv
```

Submission columns:

```text
sample_id,predicted_label,confidence
```

The scorer reports accuracy, macro-F1, balanced accuracy, calibration error and per-class recall.

## External benchmark registry

`data/openeval/manifest.json` records official source pages and license boundaries for CWRU, Paderborn, XJTU-SY, MVTec AD and MVTec AD 2. Their data is deliberately not bundled. Use `scripts/inspect_external_dataset.py` after obtaining the data from the official source.
