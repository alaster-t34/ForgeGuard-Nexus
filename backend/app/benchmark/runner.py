from __future__ import annotations

import json
import platform
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import scipy
import sklearn

from app.benchmark.datasets import OpenEvalBuilder, load_open_eval
from app.benchmark.features import feature_matrix
from app.benchmark.metrics import classification_metrics, measure_latency_ms
from app.benchmark.models import BenchmarkClassifier, TinyResNet1DClassifier, build_feature_models
from app.benchmark.schemas import (
    BenchmarkModelResult,
    BenchmarkReport,
    BenchmarkRunRequest,
    RobustnessSliceResult,
)
from app.fault_injection.signal import SensorFault, inject_sensor_fault
from app.models.portable_hgb import PORTABLE_HGB_FORMAT, export_calibrated_hgb


ROBUSTNESS_SLICES: tuple[tuple[str, SensorFault, float], ...] = (
    ("low_snr", SensorFault.LOW_SNR, 0.70),
    ("speed_shift", SensorFault.SPEED_SHIFT, 0.55),
    ("dropout", SensorFault.DROPOUT, 0.45),
    ("clipping", SensorFault.CLIPPING, 0.55),
    ("drift", SensorFault.DRIFT, 0.55),
    ("impulse_interference", SensorFault.IMPULSE_INTERFERENCE, 0.55),
)


class BenchmarkRunner:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.dataset_dir = project_root / "data" / "openeval"
        self.artifact_dir = project_root / "backend" / "research" / "artifacts"
        self.report_dir = project_root / "artifacts" / "benchmarks"
        self.latest_report: BenchmarkReport | None = None

    def run(self, request: BenchmarkRunRequest) -> BenchmarkReport:
        manifest = OpenEvalBuilder(self.dataset_dir).build(
            samples_per_class=request.samples_per_class,
            signal_length=request.signal_length,
            sample_rate_hz=request.sample_rate_hz,
            seed=request.seed,
        )
        dataset_path = self.dataset_dir / "forgeguard_openeval_rm_v0_1.npz"
        dataset = load_open_eval(dataset_path)
        all_features, feature_names = feature_matrix(dataset.signals, dataset.sample_rate_hz)
        train_mask = dataset.split == "train"
        validation_mask = dataset.split == "validation"
        test_mask = dataset.split == "test"
        x_train_features = all_features[train_mask]
        x_train_raw = dataset.signals[train_mask]
        y_train = dataset.labels[train_mask]
        x_validation_features = all_features[validation_mask]
        x_validation_raw = dataset.signals[validation_mask]
        y_validation = dataset.labels[validation_mask]
        x_test_features = all_features[test_mask]
        x_test_raw = dataset.signals[test_mask]
        y_test = dataset.labels[test_mask]

        models: list[BenchmarkClassifier] = build_feature_models(request.seed)
        if request.include_cnn:
            try:
                models.append(
                    TinyResNet1DClassifier(
                        classes=len(dataset.label_names), epochs=request.cnn_epochs, seed=request.seed
                    )
                )
            except Exception as exc:  # pragma: no cover - optional dependency path
                self._write_optional_skip("tiny-resnet1d", exc)

        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        results: list[BenchmarkModelResult] = []
        score_by_model: dict[str, float] = {}
        model_paths: dict[str, Path] = {}
        model_instances: dict[str, BenchmarkClassifier] = {}

        for model in models:
            start = time.perf_counter()
            model.fit(
                x_train_features,
                x_train_raw,
                y_train,
                x_validation_features,
                x_validation_raw,
                y_validation,
            )
            train_seconds = time.perf_counter() - start
            probabilities = model.predict_proba(x_test_features, x_test_raw)
            metrics = classification_metrics(
                y_test, probabilities, confidence_threshold=request.confidence_threshold
            )
            latency_p50, latency_p95 = measure_latency_ms(
                lambda: model.predict_proba(x_test_features[:1], x_test_raw[:1]), iterations=60
            )
            robustness: list[RobustnessSliceResult] = []
            for slice_index, (slice_name, fault, severity) in enumerate(ROBUSTNESS_SLICES):
                corrupted = np.stack(
                    [
                        inject_sensor_fault(
                            waveform,
                            fault,
                            severity=severity,
                            seed=request.seed * 10_000 + slice_index * 1_000 + index,
                        )
                        for index, waveform in enumerate(x_test_raw)
                    ]
                )
                corrupted_features, _ = feature_matrix(corrupted, dataset.sample_rate_hz)
                corrupted_probabilities = model.predict_proba(corrupted_features, corrupted)
                slice_metrics = classification_metrics(
                    y_test,
                    corrupted_probabilities,
                    confidence_threshold=request.confidence_threshold,
                )
                robustness.append(
                    RobustnessSliceResult(
                        slice_name=slice_name,
                        accuracy=float(slice_metrics["accuracy"]),
                        macro_f1=float(slice_metrics["macro_f1"]),
                        balanced_accuracy=float(slice_metrics["balanced_accuracy"]),
                        mean_confidence=float(slice_metrics["mean_confidence"]),
                        abstention_rate=float(slice_metrics["abstention_rate"]),
                        accepted_accuracy=(
                            float(slice_metrics["accepted_accuracy"])
                            if slice_metrics["accepted_accuracy"] is not None
                            else None
                        ),
                    )
                )

            suffix = ".pt" if model.model_id.startswith("tiny-resnet") else ".joblib"
            model_path = self.artifact_dir / f"{model.model_id}{suffix}"
            model_size = model.save(model_path)
            model_paths[model.model_id] = model_path
            model_instances[model.model_id] = model
            robustness_f1 = float(np.mean([item.macro_f1 for item in robustness]))
            result = BenchmarkModelResult(
                model_id=model.model_id,
                family=model.family,
                train_seconds=train_seconds,
                latency_p50_ms=latency_p50,
                latency_p95_ms=latency_p95,
                accuracy=float(metrics["accuracy"]),
                macro_f1=float(metrics["macro_f1"]),
                balanced_accuracy=float(metrics["balanced_accuracy"]),
                log_loss=float(metrics["log_loss"]),
                brier_score=float(metrics["brier_score"]),
                expected_calibration_error=float(metrics["expected_calibration_error"]),
                abstention_rate=float(metrics["abstention_rate"]),
                accepted_accuracy=(
                    float(metrics["accepted_accuracy"])
                    if metrics["accepted_accuracy"] is not None
                    else None
                ),
                model_size_bytes=model_size,
                robustness=robustness,
                notes=[
                    "Machine-group test split prevents windows from the same simulated machine crossing splits.",
                    "Robustness slices are applied only after the held-out split is fixed.",
                ],
            )
            results.append(result)
            score_by_model[model.model_id] = (
                0.45 * result.macro_f1
                + 0.20 * result.balanced_accuracy
                + 0.20 * robustness_f1
                + 0.15 * max(0.0, 1.0 - result.expected_calibration_error)
                - 0.005 * np.log1p(result.latency_p95_ms)
            )

        best_model_id = max(score_by_model, key=score_by_model.get)
        best_path = model_paths[best_model_id]
        selected_path = self.artifact_dir / (
            "selected_vibration_model.pt" if best_path.suffix == ".pt" else "selected_vibration_model.joblib"
        )
        shutil.copy2(best_path, selected_path)

        runtime_path = selected_path
        artifact_format = "torch-checkpoint" if selected_path.suffix == ".pt" else "joblib-pickle"
        runtime_requirements: dict[str, str] = {
            "python": ">=3.11,<3.13 for native release",
            "numpy": np.__version__,
            "scikit_learn_training": sklearn.__version__,
            "serialization": artifact_format,
        }
        research_source_artifact: str | None = None
        if best_model_id == "dsp-calibrated-hgb-v0.2":
            selected_model = model_instances[best_model_id]
            fitted = getattr(selected_model, "estimator", None)
            if fitted is None:
                raise RuntimeError("Selected HGB model is not fitted")
            runtime_path = self.artifact_dir / "selected_vibration_model.portable.npz"
            export_calibrated_hgb(fitted, runtime_path, source_joblib_path=selected_path)
            artifact_format = PORTABLE_HGB_FORMAT
            research_source_artifact = str(selected_path.relative_to(self.project_root))
            runtime_requirements = {
                "python": ">=3.11,<3.13 for native release",
                "numpy": ">=1.26,<3",
                "scikit_learn_inference": "not required by portable artifact",
                "scikit_learn_training": sklearn.__version__,
                "serialization": "NumPy NPZ primitive numeric arrays; allow_pickle=False",
                "compatibility_policy": (
                    "Production startup loads only the portable numeric artifact. "
                    "The joblib file is retained as a trusted research artifact."
                ),
            }

        card: dict[str, Any] = {
            "model_id": best_model_id,
            "artifact": str(runtime_path.relative_to(self.project_root)),
            "artifact_format": artifact_format,
            "feature_names": feature_names,
            "label_names": dataset.label_names,
            "sample_rate_hz": dataset.sample_rate_hz,
            "signal_length": request.signal_length,
            "confidence_threshold": request.confidence_threshold,
            "dataset_sha256": manifest.dataset_sha256,
            "selection_score": score_by_model[best_model_id],
            "runtime_requirements": runtime_requirements,
            "source_training_environment": {
                "python": platform.python_version(),
                "numpy": np.__version__,
                "scipy": scipy.__version__,
                "scikit_learn": sklearn.__version__,
                "joblib": joblib.__version__,
            },
        }
        if research_source_artifact is not None:
            card["research_source_artifact"] = research_source_artifact
        (self.artifact_dir / "selected_vibration_model.json").write_text(
            json.dumps(card, indent=2), encoding="utf-8"
        )
        (self.artifact_dir / "feature_names.json").write_text(
            json.dumps(feature_names, indent=2), encoding="utf-8"
        )

        report = BenchmarkReport(
            id=f"BMR-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
            dataset_name=manifest.name,
            dataset_version=manifest.version,
            train_samples=int(np.sum(train_mask)),
            validation_samples=int(np.sum(validation_mask)),
            test_samples=int(np.sum(test_mask)),
            labels=dataset.label_names,
            split_policy=manifest.split_policy,
            seed=request.seed,
            environment=self._environment(),
            models=results,
            best_model_id=best_model_id,
            selection_rule=(
                "0.45 macro-F1 + 0.20 balanced accuracy + 0.20 mean robustness macro-F1 + "
                "0.15 calibration term - latency penalty"
            ),
            artifact_paths={
                "dataset": str(dataset_path.relative_to(self.project_root)),
                "manifest": str((self.dataset_dir / "manifest.json").relative_to(self.project_root)),
                "selected_model": str(runtime_path.relative_to(self.project_root)),
                "selected_model_card": str(
                    (self.artifact_dir / "selected_vibration_model.json").relative_to(self.project_root)
                ),
            },
            limitations=[
                "OpenEval-RM is physics-informed synthetic data, not a substitute for plant measurements.",
                "External public datasets are registered but not redistributed because their licenses and download workflows differ.",
                "A championship submission still requires disclosed physical-rig results and cross-dataset validation.",
            ],
        )
        report_json = self.report_dir / "latest.json"
        report_json.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        (self.report_dir / f"{report.id}.json").write_text(
            report.model_dump_json(indent=2), encoding="utf-8"
        )
        (self.report_dir / "latest.md").write_text(self._markdown(report), encoding="utf-8")
        self.latest_report = report
        return report

    def load_latest(self) -> BenchmarkReport | None:
        if self.latest_report:
            return self.latest_report
        path = self.report_dir / "latest.json"
        if not path.exists():
            return None
        self.latest_report = BenchmarkReport.model_validate_json(path.read_text(encoding="utf-8"))
        return self.latest_report

    def manifest(self) -> dict[str, Any] | None:
        path = self.dataset_dir / "manifest.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def _write_optional_skip(self, model_id: str, exc: Exception) -> None:
        self.report_dir.mkdir(parents=True, exist_ok=True)
        (self.report_dir / f"{model_id}-skipped.txt").write_text(
            f"{type(exc).__name__}: {exc}\n", encoding="utf-8"
        )

    @staticmethod
    def _environment() -> dict[str, str]:
        values = {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
        }
        try:
            import torch

            values["torch"] = torch.__version__
        except Exception:
            values["torch"] = "not-installed"
        return values

    @staticmethod
    def _markdown(report: BenchmarkReport) -> str:
        rows = [
            "| Model | Macro-F1 | Balanced acc. | ECE | p95 latency (ms) | Robust mean F1 |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for model in report.models:
            robust = float(np.mean([item.macro_f1 for item in model.robustness]))
            rows.append(
                f"| `{model.model_id}` | {model.macro_f1:.4f} | {model.balanced_accuracy:.4f} | "
                f"{model.expected_calibration_error:.4f} | {model.latency_p95_ms:.3f} | {robust:.4f} |"
            )
        return f"""# ForgeGuard model benchmark

Run: `{report.id}`  
Dataset: **{report.dataset_name} {report.dataset_version}**  
Split: {report.split_policy}

{chr(10).join(rows)}

Selected model: **`{report.best_model_id}`**

Selection rule: {report.selection_rule}

## Scientific boundary

- OpenEval-RM is an openly redistributable, physics-informed regression benchmark.
- It does not establish real-factory accuracy.
- External CWRU, Paderborn, XJTU-SY, MVTec AD and MVTec AD 2 evaluations must be reported separately with their source licenses.
- Physical-rig measurements must include sensor placement, calibration, sampling, load, speed and acquisition timestamps.
"""
