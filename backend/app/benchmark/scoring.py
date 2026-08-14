from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score

from app.benchmark.metrics import expected_calibration_error
from app.csv_policy import SUBMISSION_CSV_POLICY, decode_csv_bytes, ensure_csv_size


def write_submission_template(dataset_dir: Path) -> Path:
    metadata_path = dataset_dir / "metadata.jsonl"
    rows = [json.loads(line) for line in metadata_path.read_text(encoding="utf-8").splitlines()]
    test_rows = [row for row in rows if row["split"] == "test"]
    output = dataset_dir / "submission_template.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["sample_id", "predicted_label", "confidence"]
        )
        writer.writeheader()
        for row in test_rows:
            writer.writerow(
                {
                    "sample_id": row["sample_id"],
                    "predicted_label": "normal",
                    "confidence": "0.5",
                }
            )
    ensure_csv_size(output.stat().st_size, SUBMISSION_CSV_POLICY)
    return output


def score_submission(dataset_dir: Path, submission_path: Path) -> dict[str, object]:
    metadata = [
        json.loads(line)
        for line in (dataset_dir / "metadata.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    truth = {row["sample_id"]: row["fault_mode"] for row in metadata if row["split"] == "test"}
    submission_bytes = submission_path.read_bytes()
    text, _ = decode_csv_bytes(submission_bytes, SUBMISSION_CSV_POLICY)
    csv.field_size_limit(SUBMISSION_CSV_POLICY.max_cell_characters)
    predictions: dict[str, tuple[str, float]] = {}
    reader = csv.DictReader(io.StringIO(text), delimiter=",")
    required_columns = ["sample_id", "predicted_label", "confidence"]
    if reader.fieldnames != required_columns:
        raise ValueError(
            "Submission header must be exactly: sample_id,predicted_label,confidence"
        )
    for row_number, row in enumerate(reader, 1):
        if row_number > SUBMISSION_CSV_POLICY.max_rows:
            raise ValueError(
                f"Submission exceeds {SUBMISSION_CSV_POLICY.max_rows:,} data rows"
            )
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"Submission row {row_number} has an invalid column count")
        try:
            sample_id = row["sample_id"]
            if sample_id in predictions:
                raise ValueError(f"Duplicate sample_id: {sample_id}")
            confidence = float(row["confidence"])
            if not 0.0 <= confidence <= 1.0:
                raise ValueError(f"Confidence out of range for {sample_id}")
            predictions[sample_id] = (row["predicted_label"], confidence)
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, ValueError) and str(exc).startswith(
                ("Duplicate sample_id", "Confidence out of range")
            ):
                raise
            raise ValueError(f"Invalid submission row {row_number}: {exc}") from exc
    missing = sorted(set(truth) - set(predictions))
    extra = sorted(set(predictions) - set(truth))
    if missing or extra:
        raise ValueError(f"Submission mismatch: missing={len(missing)}, extra={len(extra)}")

    labels = sorted(set(truth.values()))
    label_to_index = {label: index for index, label in enumerate(labels)}
    y_true = np.asarray([label_to_index[truth[sample_id]] for sample_id in sorted(truth)], dtype=np.int64)
    y_pred_labels = [predictions[sample_id][0] for sample_id in sorted(truth)]
    unknown = sorted(set(y_pred_labels) - set(labels))
    if unknown:
        raise ValueError(f"Unknown predicted labels: {unknown}")
    y_pred = np.asarray([label_to_index[label] for label in y_pred_labels], dtype=np.int64)
    confidence = np.asarray([predictions[sample_id][1] for sample_id in sorted(truth)], dtype=np.float64)
    probability = np.full((len(y_true), len(labels)), 1e-9, dtype=np.float64)
    if len(labels) > 1:
        residual = (1.0 - confidence) / (len(labels) - 1)
        probability[:] = residual[:, None]
    probability[np.arange(len(y_true)), y_pred] = confidence
    probability /= probability.sum(axis=1, keepdims=True)

    matrix = confusion_matrix(y_true, y_pred, labels=np.arange(len(labels)))
    per_class_recall = {
        labels[index]: float(matrix[index, index] / max(1, matrix[index].sum()))
        for index in range(len(labels))
    }
    return {
        "samples": len(y_true),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "expected_calibration_error": expected_calibration_error(y_true, probability),
        "per_class_recall": per_class_recall,
        "labels": labels,
    }
