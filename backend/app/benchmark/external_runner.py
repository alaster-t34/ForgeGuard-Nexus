from __future__ import annotations

import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import sklearn

from app.benchmark.external_datasets import WindowedSignalDataset
from app.benchmark.features import feature_matrix
from app.benchmark.metrics import classification_metrics, measure_latency_ms
from app.benchmark.models import build_feature_models
from app.fault_injection.signal import SensorFault, inject_sensor_fault


REAL_DATA_ROBUSTNESS: tuple[tuple[str, SensorFault, float], ...] = (
    ("low_snr", SensorFault.LOW_SNR, 0.45),
    ("speed_shift", SensorFault.SPEED_SHIFT, 0.35),
    ("dropout", SensorFault.DROPOUT, 0.30),
    ("clipping", SensorFault.CLIPPING, 0.35),
    ("impulse_interference", SensorFault.IMPULSE_INTERFERENCE, 0.35),
)


def grouped_stratified_split(
    labels: np.ndarray,
    groups: np.ndarray,
    *,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Split by source group while preserving every label in each partition.

    A group is assumed to contain one class. The function fails closed when a
    class has fewer than three source groups instead of leaking windows from the
    same recording into multiple partitions.
    """

    labels = np.asarray(labels, dtype=np.int64)
    groups = np.asarray(groups).astype(str)
    if labels.shape[0] != groups.shape[0]:
        raise ValueError("labels and groups must have the same length")
    rng = np.random.default_rng(seed)
    train_groups: set[str] = set()
    validation_groups: set[str] = set()
    test_groups: set[str] = set()

    for label in sorted(np.unique(labels).tolist()):
        label_groups = sorted(set(groups[labels == label].tolist()))
        if len(label_groups) < 3:
            raise ValueError(
                f"Label {label} has only {len(label_groups)} source groups; "
                "at least 3 are required for leakage-free train/validation/test splits"
            )
        shuffled = np.asarray(label_groups, dtype=object)
        rng.shuffle(shuffled)
        count = len(shuffled)
        validation_count = max(1, int(round(count * 0.2)))
        test_count = max(1, int(round(count * 0.2)))
        if validation_count + test_count >= count:
            validation_count = test_count = 1
        train_count = count - validation_count - test_count
        train_groups.update(str(item) for item in shuffled[:train_count])
        validation_groups.update(
            str(item) for item in shuffled[train_count : train_count + validation_count]
        )
        test_groups.update(str(item) for item in shuffled[train_count + validation_count :])

    train = np.isin(groups, list(train_groups))
    validation = np.isin(groups, list(validation_groups))
    test = np.isin(groups, list(test_groups))
    if np.any(train & validation) or np.any(train & test) or np.any(validation & test):
        raise AssertionError("Group leakage detected in external benchmark split")
    if not train.any() or not validation.any() or not test.any():
        raise ValueError("External benchmark produced an empty partition")
    return train, validation, test


class ExternalClassificationBenchmarkRunner:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.report_dir = project_root / "artifacts" / "benchmarks" / "external"
        self.model_dir = project_root / "backend" / "research" / "artifacts" / "external"

    def run(
        self,
        dataset: WindowedSignalDataset,
        *,
        dataset_id: str,
        seed: int = 42,
        confidence_threshold: float = 0.62,
    ) -> dict[str, Any]:
        train_mask, validation_mask, test_mask = grouped_stratified_split(
            dataset.labels, dataset.groups, seed=seed
        )
        features, feature_names = feature_matrix(dataset.signals, dataset.sample_rate_hz)
        models = build_feature_models(seed)
        results: list[dict[str, Any]] = []
        scores: dict[str, float] = {}
        run_id = f"EXT-{dataset_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        run_model_dir = self.model_dir / run_id
        run_model_dir.mkdir(parents=True, exist_ok=True)

        for model in models:
            started = time.perf_counter()
            model.fit(
                features[train_mask],
                dataset.signals[train_mask],
                dataset.labels[train_mask],
                features[validation_mask],
                dataset.signals[validation_mask],
                dataset.labels[validation_mask],
            )
            train_seconds = time.perf_counter() - started
            probabilities = model.predict_proba(features[test_mask], dataset.signals[test_mask])
            metrics = classification_metrics(
                dataset.labels[test_mask],
                probabilities,
                confidence_threshold=confidence_threshold,
            )
            latency_p50, latency_p95 = measure_latency_ms(
                lambda: model.predict_proba(
                    features[test_mask][:1], dataset.signals[test_mask][:1]
                ),
                iterations=40,
            )
            robustness: list[dict[str, Any]] = []
            for slice_index, (name, fault, severity) in enumerate(REAL_DATA_ROBUSTNESS):
                corrupted = np.stack(
                    [
                        inject_sensor_fault(
                            signal,
                            fault,
                            severity=severity,
                            seed=seed * 100_000 + slice_index * 10_000 + index,
                        )
                        for index, signal in enumerate(dataset.signals[test_mask])
                    ]
                )
                corrupted_features, _ = feature_matrix(corrupted, dataset.sample_rate_hz)
                corrupted_probabilities = model.predict_proba(corrupted_features, corrupted)
                corrupted_metrics = classification_metrics(
                    dataset.labels[test_mask],
                    corrupted_probabilities,
                    confidence_threshold=confidence_threshold,
                )
                robustness.append(
                    {
                        "slice": name,
                        "macro_f1": float(corrupted_metrics["macro_f1"]),
                        "balanced_accuracy": float(corrupted_metrics["balanced_accuracy"]),
                        "abstention_rate": float(corrupted_metrics["abstention_rate"]),
                        "accepted_accuracy": corrupted_metrics["accepted_accuracy"],
                    }
                )
            artifact = run_model_dir / f"{model.model_id}.joblib"
            model_size = model.save(artifact)
            robust_mean = float(np.mean([item["macro_f1"] for item in robustness]))
            result = {
                "model_id": model.model_id,
                "family": model.family,
                "train_seconds": train_seconds,
                "latency_p50_ms": latency_p50,
                "latency_p95_ms": latency_p95,
                "model_size_bytes": model_size,
                **metrics,
                "robustness": robustness,
                "robust_mean_macro_f1": robust_mean,
                "artifact": str(artifact.relative_to(self.project_root)),
            }
            results.append(result)
            scores[model.model_id] = (
                0.45 * float(metrics["macro_f1"])
                + 0.20 * float(metrics["balanced_accuracy"])
                + 0.20 * robust_mean
                + 0.15 * max(0.0, 1.0 - float(metrics["expected_calibration_error"]))
                - 0.005 * float(np.log1p(latency_p95))
            )

        best_model_id = max(scores, key=scores.get)
        report = {
            "id": run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "dataset_id": dataset_id,
            "sample_rate_hz": dataset.sample_rate_hz,
            "labels": dataset.label_names,
            "samples": int(dataset.signals.shape[0]),
            "signal_length": int(dataset.signals.shape[1]),
            "source_groups": int(np.unique(dataset.groups).size),
            "split": {
                "policy": "label-stratified source-group split; no recording group crosses partitions",
                "train_samples": int(train_mask.sum()),
                "validation_samples": int(validation_mask.sum()),
                "test_samples": int(test_mask.sum()),
                "train_groups": int(np.unique(dataset.groups[train_mask]).size),
                "validation_groups": int(np.unique(dataset.groups[validation_mask]).size),
                "test_groups": int(np.unique(dataset.groups[test_mask]).size),
            },
            "seed": seed,
            "feature_names": feature_names,
            "environment": {
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "numpy": np.__version__,
                "scikit_learn": sklearn.__version__,
            },
            "models": results,
            "best_model_id": best_model_id,
            "selection_score": scores[best_model_id],
            "selection_rule": (
                "0.45 macro-F1 + 0.20 balanced accuracy + 0.20 corruption robustness + "
                "0.15 calibration term - latency penalty"
            ),
            "scientific_boundary": [
                "The report applies only to the disclosed source files and group split.",
                "No model is promoted to production without test-rig calibration and safety review.",
                "Dataset license and citation remain the responsibility of the data user.",
            ],
        }
        self.report_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.report_dir / f"{dataset_id}-latest.json"
        markdown_path = self.report_dir / f"{dataset_id}-latest.md"
        json_path.write_text(json.dumps(report, indent=2, default=_json_default), encoding="utf-8")
        markdown_path.write_text(self._markdown(report), encoding="utf-8")
        return report

    @staticmethod
    def _markdown(report: dict[str, Any]) -> str:
        rows = [
            "| Model | Macro-F1 | Balanced acc. | ECE | Robust mean F1 | p95 ms |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for item in report["models"]:
            rows.append(
                f"| `{item['model_id']}` | {item['macro_f1']:.4f} | "
                f"{item['balanced_accuracy']:.4f} | "
                f"{item['expected_calibration_error']:.4f} | "
                f"{item['robust_mean_macro_f1']:.4f} | {item['latency_p95_ms']:.3f} |"
            )
        return f"""# ForgeGuard external real-data benchmark

Run: `{report['id']}`  
Dataset: **{report['dataset_id']}**  
Source groups: **{report['source_groups']}**  
Split: {report['split']['policy']}

{chr(10).join(rows)}

Selected model: **`{report['best_model_id']}`**

## Boundary

This report is valid only for the locally supplied public-dataset files. Source recordings are
not redistributed by ForgeGuard. A public-dataset result does not replace physical-rig testing.
"""


def _json_default(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
