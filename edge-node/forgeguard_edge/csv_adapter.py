from __future__ import annotations

import codecs
import csv
import io
import math
from itertools import chain
from pathlib import Path

from forgeguard_edge.contracts import RawFrame


class CsvReplayAdapter:
    MAX_BYTES = 128 * 1024 * 1024
    MAX_ROWS = 1_000_000
    MAX_COLUMNS = 256
    MAX_CELL_CHARACTERS = 1024 * 1024
    DELIMITERS = ",;\t|"

    def __init__(
        self,
        path: Path,
        source_id: str = "csv-replay",
        *,
        signal_column: str | int | None = None,
        sample_rate_hz: float = 25_600.0,
    ) -> None:
        self.path = path
        self.source_id = source_id
        self.signal_column = signal_column
        self.sample_rate_hz = sample_rate_hz

    @staticmethod
    def _decode(content: bytes) -> tuple[str, str]:
        if content.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
            return content.decode("utf-16"), "utf-16"
        for encoding in ("utf-8-sig", "gb18030"):
            try:
                return content.decode(encoding), encoding
            except UnicodeDecodeError:
                continue
        raise ValueError("CSV encoding is not supported; use UTF-8, GB18030 or UTF-16")

    @staticmethod
    def _numeric(value: str) -> bool:
        try:
            return math.isfinite(float(value.strip()))
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _normalized(value: str) -> str:
        return "".join(character for character in value.casefold() if character.isalnum())

    def _reader(self, text: str, dialect: csv.Dialect):
        try:
            for row in csv.reader(io.StringIO(text), dialect):
                if not any(cell.strip() for cell in row):
                    continue
                if len(row) > self.MAX_COLUMNS:
                    raise ValueError(
                        f"CSV has {len(row)} columns; the limit is {self.MAX_COLUMNS}"
                    )
                if any(len(cell) > self.MAX_CELL_CHARACTERS for cell in row):
                    raise ValueError("CSV cell exceeds the 1 MiB character limit")
                yield row
        except csv.Error as exc:
            raise ValueError(f"CSV format error: {exc}") from exc

    async def acquire(self) -> RawFrame:
        size = self.path.stat().st_size
        if size > self.MAX_BYTES:
            raise ValueError("CSV file exceeds the 128 MB edge replay limit")
        text, encoding = self._decode(self.path.read_bytes())
        csv.field_size_limit(self.MAX_CELL_CHARACTERS)
        try:
            dialect = csv.Sniffer().sniff(text[:16_384], delimiters=self.DELIMITERS)
        except csv.Error:
            dialect = csv.excel

        first_pass = self._reader(text, dialect)
        first = next(first_pass, None)
        if first is None:
            raise ValueError(f"CSV file is empty: {self.path}")
        has_header = not all(self._numeric(cell) for cell in first)
        headers = (
            [cell.strip() or f"column_{index}" for index, cell in enumerate(first)]
            if has_header
            else [f"column_{index}" for index in range(len(first))]
        )
        numeric_counts = [0] * len(headers)
        row_count = 0

        def inspect(row: list[str]) -> None:
            nonlocal row_count
            row_count += 1
            if row_count > self.MAX_ROWS:
                raise ValueError(f"CSV exceeds the {self.MAX_ROWS:,}-row edge replay limit")
            for index in range(len(headers)):
                if index < len(row) and self._numeric(row[index]):
                    numeric_counts[index] += 1

        if not has_header:
            inspect(first)
        for row in first_pass:
            inspect(row)

        selected_index: int | None = None
        selected = "" if self.signal_column is None else str(self.signal_column).strip()
        if selected:
            if selected in headers:
                selected_index = headers.index(selected)
            else:
                folded = self._normalized(selected)
                folded_headers = [self._normalized(header) for header in headers]
                if folded in folded_headers:
                    selected_index = folded_headers.index(folded)
                else:
                    try:
                        candidate = int(selected)
                        if 0 <= candidate < len(headers):
                            selected_index = candidate
                    except ValueError:
                        pass
            if selected_index is None:
                raise ValueError(
                    f"Signal column '{selected}' was not found. Available columns: "
                    + ", ".join(headers)
                )
        else:
            folded_headers = [self._normalized(header) for header in headers]
            for preferred in (
                "acceleration_x",
                "acceleration",
                "vibration",
                "signal",
                "amplitude",
                "sensor_value",
                "value",
                "ch1",
            ):
                folded = self._normalized(preferred)
                if folded in folded_headers:
                    candidate = folded_headers.index(folded)
                    if numeric_counts[candidate] > 0:
                        selected_index = candidate
                        break
            if selected_index is None:
                if max(numeric_counts, default=0) == 0:
                    raise ValueError(f"No numeric samples found in {self.path}")
                selected_index = max(
                    range(len(headers)), key=lambda index: (numeric_counts[index], index)
                )
            selected = headers[selected_index]

        values: list[float] = []
        skipped = 0
        second_pass = self._reader(text, dialect)
        next(second_pass, None)
        if not has_header:
            second_pass = chain((first,), second_pass)
        for row in second_pass:
            if selected_index >= len(row) or not self._numeric(row[selected_index]):
                skipped += 1
                continue
            values.append(float(row[selected_index].strip()))
        if not values:
            raise ValueError(f"No numeric samples found in {self.path}")
        return RawFrame(
            source_id=self.source_id,
            modality="vibration",
            sampling_rate_hz=self.sample_rate_hz,
            payload=values,
            metadata={
                "path": str(self.path),
                "sample_count": len(values),
                "signal_column": selected,
                "encoding": encoding,
                "delimiter": dialect.delimiter,
                "data_rows": row_count,
                "skipped_rows": skipped,
            },
        )
