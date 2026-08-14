from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.fault_injection.campaign import FaultCampaignRunner  # noqa: E402
from app.runtime import runtime  # noqa: E402


async def run(seed: int) -> None:
    report = await FaultCampaignRunner(PROJECT_ROOT, runtime.bench, runtime.tools).run(seed=seed)
    print(report.model_dump_json(indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ForgeGuard signal and workflow fault campaign")
    parser.add_argument("--seed", type=int, default=43)
    args = parser.parse_args()
    asyncio.run(run(args.seed))


if __name__ == "__main__":
    main()
