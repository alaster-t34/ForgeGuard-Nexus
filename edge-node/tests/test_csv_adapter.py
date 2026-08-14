import asyncio

import pytest

from forgeguard_edge.csv_adapter import CsvReplayAdapter


def test_csv_adapter_selects_signal_without_mixing_timestamp(tmp_path):
    path = tmp_path / "waveform.csv"
    path.write_text(
        "timestamp,acceleration_x\n0.0,1.5\n0.1,2.5\n0.2,3.5\n",
        encoding="utf-8",
    )
    frame = asyncio.run(CsvReplayAdapter(path).acquire())
    assert frame.payload == [1.5, 2.5, 3.5]
    assert frame.metadata["signal_column"] == "acceleration_x"
    assert frame.metadata["sample_count"] == 3


def test_csv_adapter_accepts_gb18030_chinese_column(tmp_path):
    path = tmp_path / "中文波形.csv"
    path.write_bytes("时间,振动值\n0,0.25\n1,0.5\n".encode("gb18030"))
    frame = asyncio.run(CsvReplayAdapter(path, signal_column="振动值").acquire())
    assert frame.payload == [0.25, 0.5]
    assert frame.metadata["encoding"] == "gb18030"


def test_csv_adapter_rejects_too_many_columns(tmp_path):
    path = tmp_path / "wide.csv"
    path.write_text(
        ",".join(f"c{index}" for index in range(257))
        + "\n"
        + ",".join("1" for _ in range(257)),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="256"):
        asyncio.run(CsvReplayAdapter(path).acquire())
