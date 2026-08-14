from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from forgeguard_edge.contracts import RawFrame


@dataclass(slots=True)
class SerialLineAdapter:
    """Optional newline-delimited serial acquisition adapter.

    Each line may contain one float or comma-separated floats. Importing the
    module does not require pyserial; the dependency is checked only when the
    adapter is used.
    """

    port: str
    baudrate: int = 921_600
    sample_rate_hz: float = 25_600.0
    samples_per_frame: int = 4096
    source_id: str = "serial-vibration"

    async def acquire(self) -> RawFrame:
        try:
            import serial
        except ImportError as exc:  # pragma: no cover - optional hardware path
            raise RuntimeError("Install forgeguard-edge-node[serial] to use SerialLineAdapter") from exc
        values: list[float] = []
        with serial.Serial(self.port, self.baudrate, timeout=2.0) as connection:
            while len(values) < self.samples_per_frame:
                line = connection.readline().decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                for cell in line.split(","):
                    try:
                        values.append(float(cell))
                    except ValueError:
                        continue
                    if len(values) >= self.samples_per_frame:
                        break
        return RawFrame(
            source_id=self.source_id,
            timestamp=datetime.now(timezone.utc),
            modality="vibration",
            sampling_rate_hz=self.sample_rate_hz,
            payload=values,
            metadata={"port": self.port, "baudrate": self.baudrate},
        )
