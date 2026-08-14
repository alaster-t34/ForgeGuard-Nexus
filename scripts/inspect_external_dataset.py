from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.benchmark.external_datasets import (  # noqa: E402
    CWRUAdapter,
    MVTecDirectoryAdapter,
    PaderbornAdapter,
    XJTUSYAdapter,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a locally downloaded public benchmark")
    parser.add_argument("dataset", choices=["cwru", "paderborn", "xjtu-sy", "mvtec"])
    parser.add_argument("root", type=Path)
    parser.add_argument("--label-map", type=Path)
    args = parser.parse_args()
    if args.dataset == "cwru":
        data = CWRUAdapter().load(args.root)
        result = {"samples": len(data.labels), "labels": data.label_names, "groups": len(set(data.groups))}
    elif args.dataset == "paderborn":
        if args.label_map is None:
            raise SystemExit("--label-map is required for Paderborn")
        data = PaderbornAdapter().load(args.root, args.label_map)
        result = {"samples": len(data.labels), "labels": data.label_names, "groups": len(set(data.groups))}
    elif args.dataset == "xjtu-sy":
        trajectories = XJTUSYAdapter().load_trajectories(args.root)
        result = {"trajectories": len(trajectories), "assets": [item.asset_id for item in trajectories]}
    else:
        records = MVTecDirectoryAdapter().index(args.root)
        result = {"images": len(records), "anomalies": sum(bool(item["is_anomaly"]) for item in records)}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
