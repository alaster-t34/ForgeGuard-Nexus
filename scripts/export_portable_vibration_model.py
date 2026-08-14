from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

import joblib  # noqa: E402
import numpy as np  # noqa: E402
import scipy  # noqa: E402
import sklearn  # noqa: E402

from app.models.portable_hgb import (  # noqa: E402
    PORTABLE_HGB_FORMAT,
    PortableCalibratedHGB,
    export_calibrated_hgb,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export ForgeGuard selected HGB model to portable NPZ")
    parser.add_argument(
        "--joblib",
        type=Path,
        default=PROJECT_ROOT / "backend" / "research" / "artifacts" / "selected_vibration_model.joblib",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT
        / "backend"
        / "research"
        / "artifacts"
        / "selected_vibration_model.portable.npz",
    )
    parser.add_argument(
        "--card",
        type=Path,
        default=PROJECT_ROOT / "backend" / "research" / "artifacts" / "selected_vibration_model.json",
    )
    args = parser.parse_args()

    model = joblib.load(args.joblib)
    export_calibrated_hgb(model, args.output, source_joblib_path=args.joblib)
    portable = PortableCalibratedHGB(args.output)

    card = json.loads(args.card.read_text(encoding="utf-8"))
    card["artifact"] = args.output.relative_to(PROJECT_ROOT).as_posix()
    card["artifact_format"] = PORTABLE_HGB_FORMAT
    card["research_source_artifact"] = args.joblib.relative_to(PROJECT_ROOT).as_posix()
    card["runtime_requirements"] = {
        "python": ">=3.11,<3.13 for native release",
        "numpy": ">=1.26,<3",
        "scikit_learn_inference": "not required by portable artifact",
        "scikit_learn_training": sklearn.__version__,
        "serialization": "NumPy NPZ primitive numeric arrays; allow_pickle=False",
        "compatibility_policy": (
            "Runtime loads the portable numeric artifact. The joblib file is retained only "
            "as a trusted research/training artifact and is not loaded by production startup."
        ),
    }
    card["source_training_environment"] = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "scikit_learn": sklearn.__version__,
        "joblib": joblib.__version__,
    }
    card["portable_model"] = {
        "class": portable.model_class,
        "features": portable.n_features,
        "classes": portable.n_classes,
        "trees": int(portable.tree_classes.size),
        "nodes": int(portable.node_value.size),
        "source_joblib_sha256": portable.source_joblib_sha256,
    }
    args.card.write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "output": str(args.output),
                "format": PORTABLE_HGB_FORMAT,
                "features": portable.n_features,
                "classes": portable.n_classes,
                "trees": int(portable.tree_classes.size),
                "nodes": int(portable.node_value.size),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
