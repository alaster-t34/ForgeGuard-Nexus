from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.benchmark.runner import BenchmarkRunner  # noqa: E402
from app.benchmark.schemas import BenchmarkRunRequest  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ForgeGuard vibration model benchmarks")
    parser.add_argument("--samples-per-class", type=int, default=56)
    parser.add_argument("--signal-length", type=int, default=2048)
    parser.add_argument("--sample-rate", type=float, default=12_000.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cnn-epochs", type=int, default=8)
    parser.add_argument("--without-cnn", action="store_true")
    args = parser.parse_args()
    report = BenchmarkRunner(PROJECT_ROOT).run(
        BenchmarkRunRequest(
            samples_per_class=args.samples_per_class,
            signal_length=args.signal_length,
            sample_rate_hz=args.sample_rate,
            seed=args.seed,
            include_cnn=not args.without_cnn,
            cnn_epochs=args.cnn_epochs,
        )
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
