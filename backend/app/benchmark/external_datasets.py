from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from scipy.io import loadmat

from app.csv_policy import XJTU_CSV_POLICY, ensure_csv_size


@dataclass(slots=True)
class WindowedSignalDataset:
    signals: np.ndarray
    labels: np.ndarray
    label_names: list[str]
    groups: np.ndarray
    sample_rate_hz: float
    metadata: list[dict[str, object]]


@dataclass(slots=True)
class RULTrajectory:
    asset_id: str
    horizontal: list[np.ndarray]
    vertical: list[np.ndarray]
    timestamps: list[str]
    sample_rate_hz: float
    metadata: dict[str, object]


def _window(signal: np.ndarray, window_size: int, hop_size: int) -> Iterable[np.ndarray]:
    values = np.asarray(signal, dtype=np.float32).reshape(-1)
    if values.size < window_size:
        yield np.pad(values, (0, window_size - values.size), mode="edge")
        return
    for start in range(0, values.size - window_size + 1, hop_size):
        yield values[start : start + window_size]


def _first_numeric_vector(value: object) -> np.ndarray | None:
    if isinstance(value, np.ndarray):
        if np.issubdtype(value.dtype, np.number) and value.size >= 64:
            return np.asarray(value, dtype=np.float32).reshape(-1)
        if value.dtype == object:
            for item in value.reshape(-1):
                found = _first_numeric_vector(item)
                if found is not None:
                    return found
    if hasattr(value, "_fieldnames"):
        for field in value._fieldnames:
            found = _first_numeric_vector(getattr(value, field))
            if found is not None:
                return found
    return None


class CWRUAdapter:
    """Load official CWRU MATLAB files after the user downloads them.

    Files are not redistributed by ForgeGuard. The adapter prefers drive-end
    acceleration variables ending in ``DE_time`` and falls back to the first
    sufficiently long numeric vector.
    """

    LABEL_PATTERNS = (
        (re.compile(r"(?:^|[_-])normal", re.I), "normal"),
        (re.compile(r"(?:^|[_-])IR", re.I), "inner_race"),
        (re.compile(r"(?:^|[_-])OR", re.I), "outer_race"),
        (re.compile(r"(?:^|[_-])B(?:\d|[_-])", re.I), "ball"),
    )

    def load(
        self,
        root: Path,
        *,
        sample_rate_hz: float = 12_000.0,
        window_size: int = 2048,
        hop_size: int = 1024,
    ) -> WindowedSignalDataset:
        files = sorted(root.rglob("*.mat"))
        if not files:
            raise FileNotFoundError(f"No .mat files found under {root}")
        label_names = ["normal", "inner_race", "outer_race", "ball"]
        signals: list[np.ndarray] = []
        labels: list[int] = []
        groups: list[str] = []
        metadata: list[dict[str, object]] = []
        for file in files:
            label = self._label(file)
            if label is None:
                continue
            payload = loadmat(file, squeeze_me=True, struct_as_record=False)
            candidates = [
                np.asarray(value, dtype=np.float32).reshape(-1)
                for key, value in payload.items()
                if key.lower().endswith("de_time")
                and isinstance(value, np.ndarray)
                and np.issubdtype(value.dtype, np.number)
            ]
            signal = candidates[0] if candidates else None
            if signal is None:
                for key, value in payload.items():
                    if key.startswith("__"):
                        continue
                    signal = _first_numeric_vector(value)
                    if signal is not None:
                        break
            if signal is None:
                continue
            for window_index, frame in enumerate(_window(signal, window_size, hop_size)):
                signals.append(frame)
                labels.append(label_names.index(label))
                groups.append(file.stem)
                metadata.append(
                    {
                        "source_file": str(file),
                        "window_index": window_index,
                        "label": label,
                        "group": file.stem,
                        "dataset": "CWRU",
                    }
                )
        if not signals:
            raise ValueError("No labeled CWRU vibration vectors could be extracted")
        return WindowedSignalDataset(
            signals=np.stack(signals),
            labels=np.asarray(labels, dtype=np.int64),
            label_names=label_names,
            groups=np.asarray(groups),
            sample_rate_hz=sample_rate_hz,
            metadata=metadata,
        )

    @classmethod
    def _label(cls, path: Path) -> str | None:
        name = path.stem
        if name.isdigit():
            sidecar = path.with_suffix(".json")
            if sidecar.exists():
                return str(json.loads(sidecar.read_text(encoding="utf-8"))["label"])
        for pattern, label in cls.LABEL_PATTERNS:
            if pattern.search(name):
                return label
        return None


class PaderbornAdapter:
    """Load Paderborn MATLAB recordings with an explicit label mapping.

    Paderborn bearing IDs encode experimental provenance. To avoid silently
    mislabelling a scientific dataset, ForgeGuard requires a JSON mapping from
    bearing ID (for example ``K001`` or ``KA01``) to the project label.
    """

    def load(
        self,
        root: Path,
        label_map_path: Path,
        *,
        sample_rate_hz: float = 64_000.0,
        window_size: int = 4096,
        hop_size: int = 2048,
    ) -> WindowedSignalDataset:
        label_map = json.loads(label_map_path.read_text(encoding="utf-8"))
        label_names = sorted(set(str(value) for value in label_map.values()))
        signals: list[np.ndarray] = []
        labels: list[int] = []
        groups: list[str] = []
        metadata: list[dict[str, object]] = []
        for file in sorted(root.rglob("*.mat")):
            bearing_id = next((key for key in label_map if key in file.stem), None)
            if bearing_id is None:
                continue
            payload = loadmat(file, squeeze_me=True, struct_as_record=False)
            vector = None
            for key, value in payload.items():
                if key.startswith("__"):
                    continue
                vector = _first_numeric_vector(value)
                if vector is not None:
                    break
            if vector is None:
                continue
            label = str(label_map[bearing_id])
            for window_index, frame in enumerate(_window(vector, window_size, hop_size)):
                signals.append(frame)
                labels.append(label_names.index(label))
                groups.append(bearing_id)
                metadata.append(
                    {
                        "source_file": str(file),
                        "window_index": window_index,
                        "label": label,
                        "group": bearing_id,
                        "dataset": "Paderborn",
                    }
                )
        if not signals:
            raise ValueError("No mapped Paderborn recordings could be extracted")
        return WindowedSignalDataset(
            signals=np.stack(signals),
            labels=np.asarray(labels, dtype=np.int64),
            label_names=label_names,
            groups=np.asarray(groups),
            sample_rate_hz=sample_rate_hz,
            metadata=metadata,
        )


class XJTUSYAdapter:
    """Load XJTU-SY run-to-failure CSV folders without redistributing data."""

    def load_trajectories(
        self,
        root: Path,
        *,
        sample_rate_hz: float = 25_600.0,
    ) -> list[RULTrajectory]:
        trajectories: list[RULTrajectory] = []
        bearing_dirs = sorted(path for path in root.rglob("Bearing*") if path.is_dir())
        for directory in bearing_dirs:
            horizontal: list[np.ndarray] = []
            vertical: list[np.ndarray] = []
            timestamps: list[str] = []
            for file in sorted(directory.glob("*.csv"), key=self._numeric_sort_key):
                ensure_csv_size(file.stat().st_size, XJTU_CSV_POLICY)
                array = np.genfromtxt(
                    file,
                    delimiter=",",
                    skip_header=1,
                    max_rows=XJTU_CSV_POLICY.max_rows + 1,
                    encoding="utf-8-sig",
                )
                if array.ndim == 1:
                    array = array.reshape(1, -1)
                if array.shape[0] > XJTU_CSV_POLICY.max_rows:
                    raise ValueError(
                        f"{file} exceeds {XJTU_CSV_POLICY.max_rows:,} data rows"
                    )
                if not 2 <= array.shape[1] <= XJTU_CSV_POLICY.max_columns:
                    raise ValueError(
                        f"{file} must contain 2-{XJTU_CSV_POLICY.max_columns} columns"
                    )
                horizontal.append(np.asarray(array[:, 0], dtype=np.float32))
                vertical.append(np.asarray(array[:, 1], dtype=np.float32))
                timestamps.append(file.stem)
            if horizontal:
                trajectories.append(
                    RULTrajectory(
                        asset_id=directory.name,
                        horizontal=horizontal,
                        vertical=vertical,
                        timestamps=timestamps,
                        sample_rate_hz=sample_rate_hz,
                        metadata={"source_directory": str(directory), "dataset": "XJTU-SY"},
                    )
                )
        if not trajectories:
            raise FileNotFoundError(f"No XJTU-SY bearing trajectories found under {root}")
        return trajectories

    @staticmethod
    def _numeric_sort_key(path: Path) -> tuple[int, str]:
        match = re.search(r"(\d+)", path.stem)
        return (int(match.group(1)) if match else 0, path.name)


class MVTecDirectoryAdapter:
    """Create an image-level index for official MVTec AD/AD2 directories."""

    def index(self, root: Path) -> list[dict[str, object]]:
        records: list[dict[str, object]] = []
        for image in sorted(root.rglob("*.png")) + sorted(root.rglob("*.jpg")):
            parts = image.relative_to(root).parts
            if "ground_truth" in parts:
                continue
            split = "train" if "train" in parts else "test" if "test" in parts else "unknown"
            defect_type = image.parent.name
            category = parts[0] if parts else "unknown"
            records.append(
                {
                    "path": str(image),
                    "category": category,
                    "split": split,
                    "defect_type": defect_type,
                    "is_anomaly": split == "test" and defect_type != "good",
                }
            )
        if not records:
            raise FileNotFoundError(f"No MVTec images found under {root}")
        return records
