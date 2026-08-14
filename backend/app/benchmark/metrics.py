from __future__ import annotations

import time
from collections.abc import Callable

import numpy as np
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, log_loss


def multiclass_brier(y_true: np.ndarray, probabilities: np.ndarray, classes: int) -> float:
    targets = np.eye(classes, dtype=np.float64)[y_true]
    return float(np.mean(np.sum((probabilities - targets) ** 2, axis=1)))


def expected_calibration_error(
    y_true: np.ndarray, probabilities: np.ndarray, bins: int = 12
) -> float:
    confidence = np.max(probabilities, axis=1)
    predictions = np.argmax(probabilities, axis=1)
    correct = predictions == y_true
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    for lower, upper in zip(edges[:-1], edges[1:], strict=True):
        mask = (confidence > lower) & (confidence <= upper)
        if not np.any(mask):
            continue
        ece += float(np.mean(mask)) * abs(float(np.mean(correct[mask])) - float(np.mean(confidence[mask])))
    return ece


def classification_metrics(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    *,
    confidence_threshold: float,
) -> dict[str, float | None]:
    probabilities = np.asarray(probabilities, dtype=np.float64)
    probabilities = np.clip(probabilities, 1e-12, None)
    probabilities = probabilities / np.sum(probabilities, axis=1, keepdims=True)
    predictions = np.argmax(probabilities, axis=1)
    confidence = np.max(probabilities, axis=1)
    accepted = confidence >= confidence_threshold
    return {
        "accuracy": float(accuracy_score(y_true, predictions)),
        "macro_f1": float(f1_score(y_true, predictions, average="macro", zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, predictions)),
        "log_loss": float(log_loss(y_true, probabilities, labels=np.arange(probabilities.shape[1]))),
        "brier_score": multiclass_brier(y_true, probabilities, probabilities.shape[1]),
        "expected_calibration_error": expected_calibration_error(y_true, probabilities),
        "mean_confidence": float(np.mean(confidence)),
        "abstention_rate": float(1.0 - np.mean(accepted)),
        "accepted_accuracy": (
            float(accuracy_score(y_true[accepted], predictions[accepted])) if np.any(accepted) else None
        ),
    }


def measure_latency_ms(predict_one: Callable[[], object], iterations: int = 80) -> tuple[float, float]:
    timings: list[float] = []
    for _ in range(5):
        predict_one()
    for _ in range(iterations):
        start = time.perf_counter()
        predict_one()
        timings.append((time.perf_counter() - start) * 1000.0)
    return float(np.percentile(timings, 50)), float(np.percentile(timings, 95))
