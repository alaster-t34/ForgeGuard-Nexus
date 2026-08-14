from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.benchmark.scoring import score_submission, write_submission_template  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Score ForgeGuard OpenEval-RM predictions")
    parser.add_argument("submission", type=Path, nargs="?")
    parser.add_argument("--write-template", action="store_true")
    args = parser.parse_args()
    dataset_dir = PROJECT_ROOT / "data" / "openeval"
    if args.write_template:
        print(write_submission_template(dataset_dir))
        return
    if args.submission is None:
        raise SystemExit("submission path is required unless --write-template is used")
    print(json.dumps(score_submission(dataset_dir, args.submission), indent=2))


if __name__ == "__main__":
    main()
