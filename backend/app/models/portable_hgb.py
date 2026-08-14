from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np

PORTABLE_HGB_FORMAT = "forgeguard-portable-calibrated-hgb-v1"


def _as_text(value: np.ndarray | str) -> str:
    if isinstance(value, str):
        return value
    array = np.asarray(value)
    return str(array.item())


def _sigmoid(values: np.ndarray) -> np.ndarray:
    """Numerically stable logistic function without a SciPy dependency."""

    values = np.asarray(values, dtype=np.float64)
    result = np.empty_like(values)
    positive = values >= 0.0
    result[positive] = 1.0 / (1.0 + np.exp(-values[positive]))
    negative = ~positive
    exp_values = np.exp(values[negative])
    result[negative] = exp_values / (1.0 + exp_values)
    return result


class PortableCalibratedHGB:
    """Portable numeric inference for a calibrated HistGradientBoosting model.

    The artifact contains only primitive NumPy arrays and is loaded with
    ``allow_pickle=False``. It therefore avoids the Python-object and NumPy RNG
    state compatibility problems of joblib/pickle model files.
    """

    def __init__(self, artifact_path: Path) -> None:
        self.artifact_path = Path(artifact_path)
        with np.load(self.artifact_path, allow_pickle=False) as payload:
            format_version = _as_text(payload["format_version"])
            if format_version != PORTABLE_HGB_FORMAT:
                raise RuntimeError(
                    f"Unsupported portable model format {format_version!r}; "
                    f"expected {PORTABLE_HGB_FORMAT!r}."
                )
            self.n_features = int(np.asarray(payload["n_features"]).item())
            self.n_classes = int(np.asarray(payload["n_classes"]).item())
            self.classes = np.asarray(payload["classes"], dtype=np.int64)
            self.baseline = np.asarray(payload["baseline"], dtype=np.float64).reshape(-1)
            self.calibration_a = np.asarray(payload["calibration_a"], dtype=np.float64).reshape(-1)
            self.calibration_b = np.asarray(payload["calibration_b"], dtype=np.float64).reshape(-1)
            self.tree_offsets = np.asarray(payload["tree_offsets"], dtype=np.int64)
            self.tree_classes = np.asarray(payload["tree_classes"], dtype=np.int32)
            self.node_value = np.asarray(payload["node_value"], dtype=np.float64)
            self.node_feature_idx = np.asarray(payload["node_feature_idx"], dtype=np.int64)
            self.node_threshold = np.asarray(payload["node_threshold"], dtype=np.float64)
            self.node_missing_go_to_left = np.asarray(
                payload["node_missing_go_to_left"], dtype=np.uint8
            )
            self.node_left = np.asarray(payload["node_left"], dtype=np.int32)
            self.node_right = np.asarray(payload["node_right"], dtype=np.int32)
            self.node_is_leaf = np.asarray(payload["node_is_leaf"], dtype=np.uint8)
            self.source_joblib_sha256 = _as_text(payload["source_joblib_sha256"])

        self._validate()

    def _validate(self) -> None:
        if self.classes.shape != (self.n_classes,):
            raise RuntimeError("Portable model class vector is inconsistent.")
        if self.baseline.shape != (self.n_classes,):
            raise RuntimeError("Portable model baseline is inconsistent.")
        if self.calibration_a.shape != (self.n_classes,):
            raise RuntimeError("Portable model calibration coefficients are inconsistent.")
        if self.calibration_b.shape != (self.n_classes,):
            raise RuntimeError("Portable model calibration intercepts are inconsistent.")
        if self.tree_offsets.ndim != 1 or self.tree_offsets.size != self.tree_classes.size + 1:
            raise RuntimeError("Portable model tree index is inconsistent.")
        if int(self.tree_offsets[0]) != 0 or int(self.tree_offsets[-1]) != self.node_value.size:
            raise RuntimeError("Portable model node offsets are inconsistent.")
        node_count = self.node_value.size
        node_arrays = (
            self.node_feature_idx,
            self.node_threshold,
            self.node_missing_go_to_left,
            self.node_left,
            self.node_right,
            self.node_is_leaf,
        )
        if any(array.size != node_count for array in node_arrays):
            raise RuntimeError("Portable model node arrays have different lengths.")
        if np.any(self.tree_classes < 0) or np.any(self.tree_classes >= self.n_classes):
            raise RuntimeError("Portable model contains an invalid tree class index.")

    @property
    def model_class(self) -> str:
        return "PortableCalibratedHGB"

    def decision_function(self, features: np.ndarray) -> np.ndarray:
        x = np.asarray(features, dtype=np.float64)
        if x.ndim == 1:
            x = x.reshape(1, -1)
        if x.ndim != 2 or x.shape[1] != self.n_features:
            raise ValueError(
                f"Expected feature matrix shaped (n, {self.n_features}), got {x.shape}."
            )

        raw = np.broadcast_to(self.baseline, (x.shape[0], self.n_classes)).copy()
        sample_count = x.shape[0]

        if sample_count == 1:
            row = x[0]
            for tree_index, class_index in enumerate(self.tree_classes):
                start = int(self.tree_offsets[tree_index])
                end = int(self.tree_offsets[tree_index + 1])
                local_node = 0
                while not bool(self.node_is_leaf[start + local_node]):
                    global_node = start + local_node
                    feature_index = int(self.node_feature_idx[global_node])
                    value = float(row[feature_index])
                    if np.isnan(value):
                        go_left = bool(self.node_missing_go_to_left[global_node])
                    else:
                        go_left = value <= float(self.node_threshold[global_node])
                    local_node = int(
                        self.node_left[global_node] if go_left else self.node_right[global_node]
                    )
                    if local_node < 0 or start + local_node >= end:
                        raise RuntimeError(
                            "Portable model traversal left the current tree bounds."
                        )
                raw[0, int(class_index)] += self.node_value[start + local_node]
            return raw

        for tree_index, class_index in enumerate(self.tree_classes):
            start = int(self.tree_offsets[tree_index])
            end = int(self.tree_offsets[tree_index + 1])
            local_node = np.zeros(sample_count, dtype=np.int32)

            # The selected HGB model contains only numeric splits. Child indexes
            # are local to each tree and node depth is bounded, so this loop is
            # deterministic and inexpensive for real-time single-window inference.
            while True:
                global_node = start + local_node
                is_leaf = self.node_is_leaf[global_node].astype(bool)
                if bool(np.all(is_leaf)):
                    break
                active = np.flatnonzero(~is_leaf)
                active_global = global_node[active]
                feature_index = self.node_feature_idx[active_global]
                values = x[active, feature_index]
                missing = np.isnan(values)
                go_left = np.where(
                    missing,
                    self.node_missing_go_to_left[active_global].astype(bool),
                    values <= self.node_threshold[active_global],
                )
                local_node[active] = np.where(
                    go_left,
                    self.node_left[active_global],
                    self.node_right[active_global],
                )
                if np.any(local_node < 0) or np.any(start + local_node >= end):
                    raise RuntimeError("Portable model traversal left the current tree bounds.")

            raw[:, int(class_index)] += self.node_value[start + local_node]

        return raw

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        raw = self.decision_function(features)
        calibrated = _sigmoid(-(raw * self.calibration_a + self.calibration_b))
        denominator = calibrated.sum(axis=1, keepdims=True)
        invalid = (~np.isfinite(denominator)) | (denominator <= 0.0)
        if np.any(invalid):
            calibrated[invalid[:, 0], :] = 1.0
            denominator = calibrated.sum(axis=1, keepdims=True)
        probabilities = calibrated / denominator
        return probabilities.astype(np.float64, copy=False)


def export_calibrated_hgb(
    calibrated_model: Any,
    artifact_path: Path,
    *,
    source_joblib_path: Path | None = None,
) -> Path:
    """Export the selected sklearn model into the portable numeric format."""

    calibrated_classifiers = getattr(calibrated_model, "calibrated_classifiers_", None)
    if not calibrated_classifiers or len(calibrated_classifiers) != 1:
        raise TypeError("Expected one ensemble=False calibrated classifier.")
    calibrated = calibrated_classifiers[0]
    frozen = getattr(calibrated, "estimator", None)
    estimator = getattr(frozen, "estimator", frozen)
    if estimator is None or estimator.__class__.__name__ != "HistGradientBoostingClassifier":
        raise TypeError("Portable exporter currently supports HistGradientBoostingClassifier only.")

    predictors = getattr(estimator, "_predictors", None)
    if predictors is None:
        raise TypeError("The fitted HGB estimator does not expose predictors.")

    tree_offsets = [0]
    tree_classes: list[int] = []
    node_value: list[np.ndarray] = []
    node_feature_idx: list[np.ndarray] = []
    node_threshold: list[np.ndarray] = []
    node_missing_go_to_left: list[np.ndarray] = []
    node_left: list[np.ndarray] = []
    node_right: list[np.ndarray] = []
    node_is_leaf: list[np.ndarray] = []

    for iteration in predictors:
        for class_index, predictor in enumerate(iteration):
            nodes = predictor.nodes
            if np.any(nodes["is_categorical"]):
                raise TypeError("Categorical HGB splits are not supported by the portable exporter.")
            node_value.append(np.asarray(nodes["value"], dtype=np.float64))
            node_feature_idx.append(np.asarray(nodes["feature_idx"], dtype=np.int64))
            node_threshold.append(np.asarray(nodes["num_threshold"], dtype=np.float64))
            node_missing_go_to_left.append(
                np.asarray(nodes["missing_go_to_left"], dtype=np.uint8)
            )
            node_left.append(np.asarray(nodes["left"], dtype=np.int32))
            node_right.append(np.asarray(nodes["right"], dtype=np.int32))
            node_is_leaf.append(np.asarray(nodes["is_leaf"], dtype=np.uint8))
            tree_classes.append(class_index)
            tree_offsets.append(tree_offsets[-1] + int(nodes.shape[0]))

    calibrators = list(getattr(calibrated, "calibrators", ()))
    classes = np.asarray(getattr(calibrated_model, "classes_"), dtype=np.int64)
    if len(calibrators) != classes.size:
        raise TypeError("Expected one sigmoid calibrator per class.")
    if any(not hasattr(item, "a_") or not hasattr(item, "b_") for item in calibrators):
        raise TypeError("Only sigmoid calibration is supported by the portable exporter.")

    source_sha256 = ""
    if source_joblib_path is not None and Path(source_joblib_path).is_file():
        digest = hashlib.sha256()
        with Path(source_joblib_path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        source_sha256 = digest.hexdigest()

    artifact_path = Path(artifact_path)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        artifact_path,
        format_version=np.asarray(PORTABLE_HGB_FORMAT),
        n_features=np.asarray(int(getattr(estimator, "n_features_in_")), dtype=np.int64),
        n_classes=np.asarray(classes.size, dtype=np.int64),
        classes=classes,
        baseline=np.asarray(estimator._baseline_prediction, dtype=np.float64).reshape(-1),
        calibration_a=np.asarray([item.a_ for item in calibrators], dtype=np.float64),
        calibration_b=np.asarray([item.b_ for item in calibrators], dtype=np.float64),
        tree_offsets=np.asarray(tree_offsets, dtype=np.int64),
        tree_classes=np.asarray(tree_classes, dtype=np.int32),
        node_value=np.concatenate(node_value).astype(np.float64, copy=False),
        node_feature_idx=np.concatenate(node_feature_idx).astype(np.int64, copy=False),
        node_threshold=np.concatenate(node_threshold).astype(np.float64, copy=False),
        node_missing_go_to_left=np.concatenate(node_missing_go_to_left).astype(
            np.uint8, copy=False
        ),
        node_left=np.concatenate(node_left).astype(np.int32, copy=False),
        node_right=np.concatenate(node_right).astype(np.int32, copy=False),
        node_is_leaf=np.concatenate(node_is_leaf).astype(np.uint8, copy=False),
        source_joblib_sha256=np.asarray(source_sha256),
    )
    return artifact_path
