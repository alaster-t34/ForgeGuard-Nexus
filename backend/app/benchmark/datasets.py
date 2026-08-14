from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.benchmark.schemas import OpenEvalManifest, PublicDatasetSpec
from app.csv_policy import OPEN_EVAL_INDEX_POLICY, ensure_csv_size
from app.fault_injection.signal import PhysicalFault, generate_rotating_machine_signal


LABELS = [
    PhysicalFault.NORMAL.value,
    PhysicalFault.IMBALANCE.value,
    PhysicalFault.MISALIGNMENT.value,
    PhysicalFault.OUTER_RACE.value,
    PhysicalFault.INNER_RACE.value,
    PhysicalFault.BALL.value,
    PhysicalFault.LUBRICATION.value,
    PhysicalFault.LOOSENESS.value,
]


EXTERNAL_DATASETS = [
    PublicDatasetSpec(
        id="cwru-bearing",
        name="Case Western Reserve University Bearing Data Center",
        modalities=["vibration"],
        task=["fault-classification", "cross-load-robustness"],
        source_url="https://engineering.case.edu/bearingdatacenter/download-data-file",
        license="Source terms must be checked before redistribution",
        redistribution="download_by_user",
        notes="12 kHz and 48 kHz drive-end data plus fan-end data; seeded faults and documented load conditions.",
        citation="Case Western Reserve University Bearing Data Center.",
    ),
    PublicDatasetSpec(
        id="paderborn-bearing",
        name="Paderborn University Bearing DataCenter",
        modalities=["vibration", "motor-current", "speed", "torque", "temperature"],
        task=["fault-classification", "cross-condition-generalization"],
        source_url="https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter/data-sets-and-download",
        license="CC BY-NC 4.0",
        redistribution="download_by_user",
        notes="Healthy, artificial-damage and accelerated-life bearings under four operating conditions.",
        citation="Lessmeier et al., KAt-DataCenter, Paderborn University.",
    ),
    PublicDatasetSpec(
        id="xjtu-sy",
        name="XJTU-SY Bearing Run-to-Failure Dataset",
        modalities=["vibration"],
        task=["remaining-useful-life", "degradation-detection"],
        source_url="https://github.com/WangBiaoXJTU/xjtu-sy-bearing-datasets",
        license="Public research dataset; verify source terms before redistribution",
        redistribution="download_by_user",
        notes="Complete run-to-failure trajectories for 15 rolling-element bearings.",
        citation="Wang et al., IEEE Transactions on Reliability, 2020, DOI: 10.1109/TR.2018.2882682.",
    ),
    PublicDatasetSpec(
        id="mvtec-ad",
        name="MVTec AD",
        modalities=["image", "segmentation-mask"],
        task=["visual-anomaly-detection", "anomaly-localization"],
        source_url="https://www.mvtec.com/research-teaching/datasets/mvtec-ad",
        license="CC BY-NC-SA 4.0",
        redistribution="download_by_user",
        notes="15 categories with defect-free training images and anomalous test images with pixel-level annotations.",
    ),
    PublicDatasetSpec(
        id="mvtec-ad-2",
        name="MVTec AD 2",
        modalities=["image", "segmentation-mask"],
        task=["visual-anomaly-detection", "distribution-shift-robustness"],
        source_url="https://www.mvtec.com/research-teaching/datasets/mvtec-ad-2",
        license="CC BY-NC-SA 4.0",
        redistribution="download_by_user",
        notes="Eight challenging scenarios, lighting shifts, public and private evaluation partitions.",
    ),
]


@dataclass(slots=True)
class OpenEvalData:
    signals: np.ndarray
    labels: np.ndarray
    label_names: list[str]
    split: np.ndarray
    metadata: list[dict[str, Any]]
    sample_rate_hz: float


class OpenEvalBuilder:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir

    def build(
        self,
        *,
        samples_per_class: int = 56,
        signal_length: int = 2048,
        sample_rate_hz: float = 12_000.0,
        seed: int = 42,
    ) -> OpenEvalManifest:
        if samples_per_class < 1:
            raise ValueError("samples_per_class must be positive")
        if samples_per_class * len(LABELS) > OPEN_EVAL_INDEX_POLICY.max_rows:
            raise ValueError(
                f"OpenEval index exceeds {OPEN_EVAL_INDEX_POLICY.max_rows:,} rows"
            )
        if not 64 <= signal_length <= 262_144:
            raise ValueError("signal_length must be between 64 and 262144")
        if not 64.0 <= sample_rate_hz <= 1_000_000.0:
            raise ValueError("sample_rate_hz must be between 64 and 1000000")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        duration_seconds = signal_length / sample_rate_hz
        signals: list[np.ndarray] = []
        labels: list[int] = []
        splits: list[str] = []
        metadata: list[dict[str, Any]] = []
        rng = np.random.default_rng(seed)

        for label_index, label in enumerate(LABELS):
            for sample_index in range(samples_per_class):
                machine_index = sample_index % 14
                if machine_index <= 8:
                    split = "train"
                elif machine_index <= 10:
                    split = "validation"
                else:
                    split = "test"
                rpm = float(rng.uniform(1_350, 2_350))
                load = float(rng.uniform(35, 105))
                severity = 0.0 if label == PhysicalFault.NORMAL.value else float(rng.uniform(0.25, 0.95))
                waveform = generate_rotating_machine_signal(
                    label,
                    sample_rate_hz=sample_rate_hz,
                    duration_seconds=duration_seconds,
                    rpm=rpm,
                    load_percent=load,
                    severity=severity,
                    seed=seed * 100_000 + label_index * 10_000 + sample_index,
                )
                signals.append(waveform)
                labels.append(label_index)
                splits.append(split)
                metadata.append(
                    {
                        "sample_id": f"FGOE-{label_index:02d}-{sample_index:04d}",
                        "machine_id": f"SIM-RM-{machine_index:02d}",
                        "fault_mode": label,
                        "severity": severity,
                        "rpm": rpm,
                        "load_percent": load,
                        "split": split,
                        "provenance": "ForgeGuard physics-informed generator",
                    }
                )

        signal_array = np.stack(signals).astype(np.float32)
        label_array = np.asarray(labels, dtype=np.int16)
        split_array = np.asarray(splits, dtype="U10")
        npz_path = self.output_dir / "forgeguard_openeval_rm_v0_1.npz"
        np.savez_compressed(
            npz_path,
            signals=signal_array,
            labels=label_array,
            splits=split_array,
            label_names=np.asarray(LABELS, dtype="U32"),
            sample_rate_hz=np.asarray([sample_rate_hz], dtype=np.float64),
        )

        index_path = self.output_dir / "index.csv"
        with index_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(metadata[0].keys()))
            writer.writeheader()
            writer.writerows(metadata)
        ensure_csv_size(index_path.stat().st_size, OPEN_EVAL_INDEX_POLICY)

        metadata_path = self.output_dir / "metadata.jsonl"
        with metadata_path.open("w", encoding="utf-8") as handle:
            for item in metadata:
                handle.write(json.dumps(item, ensure_ascii=False) + "\n")

        dataset_hash = hashlib.sha256(npz_path.read_bytes()).hexdigest()
        manifest = OpenEvalManifest(
            name="ForgeGuard OpenEval-RM",
            version="0.1.0",
            license="Apache-2.0",
            description=(
                "Deterministic physics-informed rotating-machinery evaluation set for model, "
                "agent and robustness regression. It is openly redistributable but must not be "
                "represented as experimental plant data."
            ),
            sample_rate_hz=sample_rate_hz,
            signal_length=signal_length,
            labels=LABELS,
            split_policy=(
                "Machine-group split: simulated machine IDs 00-08 train, 09-10 validation, "
                "11-13 test. No window from a machine appears in multiple splits."
            ),
            generator_commit="competition-edition-v0.2",
            dataset_sha256=dataset_hash,
            samples=len(metadata),
            external_benchmarks=EXTERNAL_DATASETS,
        )
        (self.output_dir / "manifest.json").write_text(
            manifest.model_dump_json(indent=2), encoding="utf-8"
        )
        (self.output_dir / "README.md").write_text(
            self._readme(manifest), encoding="utf-8"
        )
        return manifest

    @staticmethod
    def _readme(manifest: OpenEvalManifest) -> str:
        labels = "\n".join(f"- `{item}`" for item in manifest.labels)
        return f"""# {manifest.name} {manifest.version}

{manifest.description}

## Contents

- `forgeguard_openeval_rm_v0_1.npz`: waveform tensor, integer labels, split names and label names.
- `index.csv`: compact human-readable sample index.
- `metadata.jsonl`: complete per-sample generation metadata.
- `manifest.json`: provenance, hash, split policy and external benchmark registry.

## Labels

{labels}

## Split policy

{manifest.split_policy}

## License and scientific boundary

The generator and generated OpenEval-RM data are Apache-2.0. This dataset is intended for
software regression, robustness testing and open benchmark demonstrations. It is synthetic,
although its fault signatures use transparent rotating-machinery formulas. It must not be used
to claim real-factory accuracy. Real-data claims require separate evaluation on the external
public datasets listed in `manifest.json` and on a disclosed physical test rig.

SHA-256: `{manifest.dataset_sha256}`
"""


def load_open_eval(path: Path) -> OpenEvalData:
    payload = np.load(path, allow_pickle=False)
    metadata_path = path.parent / "metadata.jsonl"
    metadata = [json.loads(line) for line in metadata_path.read_text(encoding="utf-8").splitlines()]
    return OpenEvalData(
        signals=payload["signals"].astype(np.float32),
        labels=payload["labels"].astype(np.int64),
        label_names=[str(item) for item in payload["label_names"].tolist()],
        split=payload["splits"].astype(str),
        metadata=metadata,
        sample_rate_hz=float(payload["sample_rate_hz"][0]),
    )
