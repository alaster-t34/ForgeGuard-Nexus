from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run disclosed Anomalib visual baselines")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "backend/research/anomalib_benchmark.yaml")
    parser.add_argument("--dataset-root", type=Path)
    parser.add_argument("--category")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    root = args.dataset_root or Path(config["dataset"]["root"])
    category = args.category or config["dataset"]["category"]
    if not root.exists() and not args.dry_run:
        raise SystemExit(
            f"Dataset root does not exist: {root}. Download the official dataset under its license first."
        )
    commands: list[list[str]] = []
    for model in config["models"]:
        commands.append(
            [
                sys.executable,
                "-m",
                "anomalib.cli.cli",
                "train",
                "--model",
                model,
                "--data",
                "anomalib.data.MVTecAD",
                "--data.root",
                str(root),
                "--data.category",
                category,
                "--seed_everything",
                str(config["runtime"]["seed"]),
            ]
        )
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config": str(args.config),
        "dataset_root": str(root),
        "category": category,
        "commands": commands,
        "dry_run": args.dry_run,
    }
    output_dir = PROJECT_ROOT / "artifacts" / "visual-benchmarks"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "run-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    if args.dry_run:
        return
    try:
        import anomalib  # noqa: F401
    except ImportError as exc:
        raise SystemExit("Install the optional visual benchmark environment: pip install 'anomalib[openvino,cpu]'") from exc
    for command in commands:
        subprocess.run(command, cwd=PROJECT_ROOT, check=True)


if __name__ == "__main__":
    main()
