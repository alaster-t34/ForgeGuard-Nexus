from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable


@dataclass(slots=True, frozen=True)
class SpoolFlushResult:
    attempted: int
    delivered: int
    failed: int
    remaining: int
    error: str | None = None


class FrameSpool:
    """Crash-safe local queue for bench frames.

    Frames are written to a temporary file and atomically renamed. A file is
    deleted only after the remote API acknowledges it, so a network outage does
    not silently discard physical-rig evidence.
    """

    def __init__(self, directory: Path, *, max_files: int = 10_000) -> None:
        self.directory = directory
        self.max_files = max_files
        self.directory.mkdir(parents=True, exist_ok=True)
        self.sequence_state_path = self.directory / "sequence.state"

    def pending(self) -> list[Path]:
        return sorted(self.directory.glob("*.json"))


    def next_sequence(self, requested_start: int = 0) -> int:
        persisted = 0
        if self.sequence_state_path.exists():
            try:
                persisted = int(self.sequence_state_path.read_text(encoding="utf-8").strip())
            except (OSError, ValueError):
                persisted = 0
        pending_next = 0
        for path in self.pending():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                pending_next = max(pending_next, int(payload.get("sequence", -1)) + 1)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
        return max(int(requested_start), persisted, pending_next)

    def mark_next_sequence(self, value: int) -> None:
        temporary = self.sequence_state_path.with_suffix(".state.tmp")
        temporary.write_text(str(int(value)), encoding="utf-8")
        # Windows requires a writable handle for FlushFileBuffers, which is
        # what os.fsync delegates to.  A read-only handle raises WinError 9.
        with temporary.open("r+b") as handle:
            os.fsync(handle.fileno())
        temporary.replace(self.sequence_state_path)

    def enqueue(self, payload: dict) -> Path:
        pending = self.pending()
        if len(pending) >= self.max_files:
            raise RuntimeError(
                f"Frame spool is full ({len(pending)}/{self.max_files}); "
                "stop acquisition or free space before continuing"
            )
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        sequence = int(payload.get("sequence", 0))
        node_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(payload.get("node_id", "node")))
        final_path = self.directory / f"{node_id}-{sequence:012d}-{timestamp}.json"
        temporary_path = final_path.with_suffix(".json.tmp")
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        temporary_path.write_text(encoded, encoding="utf-8")
        with temporary_path.open("r+b") as handle:
            os.fsync(handle.fileno())
        temporary_path.replace(final_path)
        return final_path

    async def flush(
        self,
        publish: Callable[[dict], Awaitable[dict]],
        *,
        limit: int = 100,
    ) -> SpoolFlushResult:
        attempted = delivered = failed = 0
        last_error: str | None = None
        for path in self.pending()[: max(0, limit)]:
            attempted += 1
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                await publish(payload)
            except Exception as exc:
                failed += 1
                last_error = f"{type(exc).__name__}: {exc}"
                # Preserve ordering: later frames must not overtake an earlier
                # frame because the server enforces monotonic sequence numbers.
                break
            else:
                path.unlink(missing_ok=True)
                delivered += 1
        return SpoolFlushResult(
            attempted=attempted,
            delivered=delivered,
            failed=failed,
            remaining=len(self.pending()),
            error=last_error,
        )
