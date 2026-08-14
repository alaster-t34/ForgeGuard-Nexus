from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.benchmark.external_datasets import CWRUAdapter, PaderbornAdapter  # noqa: E402
from app.benchmark.external_runner import ExternalClassificationBenchmarkRunner  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a leakage-resistant benchmark on user-downloaded public bearing data"
    )
    parser.add_argument("dataset", choices=["cwru", "paderborn"])
    parser.add_argument("root", type=Path)
    parser.add_argument("--label-map", type=Path)
    parser.add_argument("--sample-rate", type=float)
    parser.add_argument("--window-size", type=int)
    parser.add_argument("--hop-size", type=int)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.dataset == "cwru":
        loaded = CWRUAdapter().load(
            args.root,
            sample_rate_hz=args.sample_rate or 12_000.0,
            window_size=args.window_size or 2048,
            hop_size=args.hop_size or 1024,
        )
    else:
        if args.label_map is None:
            raise SystemExit("--label-map is required for Paderborn to prevent silent mislabelling")
        loaded = PaderbornAdapter().load(
            args.root,
            args.label_map,
            sample_rate_hz=args.sample_rate or 64_000.0,
            window_size=args.window_size or 4096,
            hop_size=args.hop_size or 2048,
        )
    report = ExternalClassificationBenchmarkRunner(PROJECT_ROOT).run(
        loaded,
        dataset_id=args.dataset,
        seed=args.seed,
    )
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
