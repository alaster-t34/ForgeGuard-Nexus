from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.benchmark.datasets import OpenEvalBuilder  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Build ForgeGuard OpenEval-RM")
    parser.add_argument("--samples-per-class", type=int, default=56)
    parser.add_argument("--signal-length", type=int, default=2048)
    parser.add_argument("--sample-rate", type=float, default=12_000.0)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    manifest = OpenEvalBuilder(PROJECT_ROOT / "data" / "openeval").build(
        samples_per_class=args.samples_per_class,
        signal_length=args.signal_length,
        sample_rate_hz=args.sample_rate,
        seed=args.seed,
    )
    print(manifest.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
