from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import AsyncIterator

import numpy as np

from forgeguard_edge.adapters.serial_line import SerialLineAdapter
from forgeguard_edge.bench_client import BenchNodeConfig, ForgeGuardBenchClient, csv_windows
from forgeguard_edge.csv_adapter import CsvReplayAdapter
from forgeguard_edge.features import StatisticalVibrationFeatures
from forgeguard_edge.live_client import ForgeGuardLiveClient
from forgeguard_edge.platform import collect_platform_report, preflight_ok
from forgeguard_edge.spool import FrameSpool


async def inspect_file(path: Path, signal_column: str | None = None) -> None:
    frame = await CsvReplayAdapter(path, signal_column=signal_column).acquire()
    features = await StatisticalVibrationFeatures().infer(frame)
    print(json.dumps({"frame": frame.model_dump(mode="json"), "features": features}, indent=2))


def node_config(args: argparse.Namespace, *, transport: str) -> BenchNodeConfig:
    platform_report = collect_platform_report()
    hardware = platform_report.hardware_label if args.hardware == "auto" else args.hardware
    operating_system = (
        platform_report.operating_system
        if args.operating_system in {None, "auto"}
        else args.operating_system
    )
    return BenchNodeConfig(
        node_id=args.node_id,
        asset_id=args.asset_id,
        name=args.name,
        hardware=hardware,
        nominal_sample_rate_hz=args.sample_rate,
        sensor_position=args.sensor_position,
        sensor_mounting=args.sensor_mounting,
        transport=transport,
        operating_system=operating_system,
        channel=args.channel,
        unit=args.unit,
        platform_metadata={
            "architecture": platform_report.architecture,
            "device_model": platform_report.device_model,
            "is_jetson": platform_report.is_jetson,
            "l4t_release": platform_report.l4t_release,
            "l4t_revision": platform_report.l4t_revision,
            "cuda_version": platform_report.cuda_version,
            "tensorrt_version": platform_report.tensorrt_version,
        },
    )


async def publish_windows(
    args: argparse.Namespace,
    windows: AsyncIterator[np.ndarray],
    *,
    transport: str,
    source_metadata: dict[str, object],
) -> None:
    config = node_config(args, transport=transport)
    client = ForgeGuardBenchClient(
        args.server,
        timeout_seconds=args.timeout,
        retries=args.retries,
    )
    spool = FrameSpool(args.spool_dir, max_files=args.spool_max_files)
    registered = await client.register(config)
    print(json.dumps({"registered": registered}, indent=2))

    campaign_id = args.campaign_id
    if args.campaign_manifest is not None:
        campaign_payload = json.loads(args.campaign_manifest.read_text(encoding="utf-8"))
        if campaign_payload.get("node_id") != config.node_id:
            raise ValueError("Campaign manifest node_id does not match --node-id")
        if campaign_payload.get("asset_id") != config.asset_id:
            raise ValueError("Campaign manifest asset_id does not match --asset-id")
        campaign = await client.register_campaign(campaign_payload)
        campaign_id = str(campaign["campaign_id"])
        print(json.dumps({"campaign": campaign}, indent=2))

    flush = await spool.flush(client.publish_payload, limit=args.flush_limit)
    if flush.attempted:
        print(json.dumps({"spool_flush": asdict(flush)}, default=str))

    sequence = spool.next_sequence(args.sequence_start)
    frame_count = 0
    async for window in windows:
        payload = client.frame_payload(
            config,
            window,
            sequence=sequence,
            rpm=args.rpm,
            load_percent=args.load,
            campaign_id=campaign_id,
            temperature_c=args.temperature,
            open_incident=args.open_incident,
            metadata={**source_metadata, "edge_sequence": sequence},
        )
        if spool.pending():
            queued = spool.enqueue(payload)
            try:
                flush = await spool.flush(client.publish_payload, limit=args.flush_limit)
            except Exception as exc:  # defensive; FrameSpool normally contains this
                print(
                    json.dumps(
                        {
                            "status": "spooled",
                            "sequence": sequence,
                            "path": str(queued),
                            "error": f"{type(exc).__name__}: {exc}",
                        },
                        ensure_ascii=False,
                    ),
                    file=sys.stderr,
                )
            else:
                print(json.dumps({"spool_flush": asdict(flush)}, default=str))
        else:
            try:
                result = await client.publish_payload(payload)
            except Exception as exc:
                queued = spool.enqueue(payload)
                print(
                    json.dumps(
                        {
                            "status": "spooled",
                            "sequence": sequence,
                            "path": str(queued),
                            "error": f"{type(exc).__name__}: {exc}",
                        },
                        ensure_ascii=False,
                    ),
                    file=sys.stderr,
                )
            else:
                print(json.dumps(result, ensure_ascii=False))
        sequence += 1
        spool.mark_next_sequence(sequence)
        frame_count += 1
        if args.max_frames is not None and frame_count >= args.max_frames:
            break
        if args.interval > 0:
            await asyncio.sleep(args.interval)


async def stream_file(args: argparse.Namespace) -> None:
    windows = csv_windows(
        args.csv,
        window_size=args.window_size,
        hop_size=args.hop_size,
        signal_column=args.signal_column,
        sample_rate_hz=args.sample_rate,
    )
    await publish_windows(
        args,
        windows,
        transport="file",
        source_metadata={"source_file": str(args.csv), "source_type": "csv-replay"},
    )


async def serial_windows(args: argparse.Namespace) -> AsyncIterator[np.ndarray]:
    adapter = SerialLineAdapter(
        port=args.port,
        baudrate=args.baudrate,
        sample_rate_hz=args.sample_rate,
        samples_per_frame=args.window_size,
        source_id=args.node_id,
    )
    while True:
        frame = await adapter.acquire()
        yield np.asarray(frame.payload, dtype=np.float32)
        await asyncio.sleep(0)


async def publish_live_windows(
    args: argparse.Namespace,
    windows: AsyncIterator[np.ndarray],
    *,
    source_type: str,
) -> None:
    client = ForgeGuardLiveClient(args.server, timeout_seconds=args.timeout)
    session = await client.create_session(
        {
            "asset_id": args.asset_id,
            "node_id": args.node_id,
            "name": args.name,
            "source": "external",
            "sample_rate_hz": args.sample_rate,
            "rpm": args.rpm,
            "load_percent": args.load,
            "open_incident": args.open_incident,
        }
    )
    session_id = str(session["id"])
    print(json.dumps({"live_session": session}, ensure_ascii=False, indent=2))
    frame_count = 0
    try:
        async for window in windows:
            result = await client.publish_frame(
                session_id,
                window,
                rpm=args.rpm,
                load_percent=args.load,
                temperature_c=args.temperature,
                metadata={
                    "source_type": source_type,
                    "edge_node_id": args.node_id,
                    "frame_index": frame_count,
                },
            )
            summary = {
                "session_id": session_id,
                "frame": result.get("total_frames"),
                "accepted": (result.get("last_analysis") or {}).get("accepted"),
                "quality": ((result.get("last_analysis") or {}).get("quality") or {}).get("score"),
                "model_result": (result.get("last_analysis") or {}).get("model_result"),
                "incident_id": result.get("incident_id"),
            }
            print(json.dumps(summary, ensure_ascii=False))
            frame_count += 1
            if args.max_frames is not None and frame_count >= args.max_frames:
                break
            if args.interval > 0:
                await asyncio.sleep(args.interval)
    finally:
        stopped = await client.stop_session(session_id)
        print(json.dumps({"stopped": stopped}, ensure_ascii=False))


async def stream_live_file(args: argparse.Namespace) -> None:
    windows = csv_windows(
        args.csv,
        window_size=args.window_size,
        hop_size=args.hop_size,
        signal_column=args.signal_column,
        sample_rate_hz=args.sample_rate,
    )
    await publish_live_windows(args, windows, source_type="csv-live-replay")


async def stream_live_serial(args: argparse.Namespace) -> None:
    await publish_live_windows(args, serial_windows(args), source_type="serial-live")


async def stream_serial(args: argparse.Namespace) -> None:
    await publish_windows(
        args,
        serial_windows(args),
        transport="serial",
        source_metadata={
            "source_type": "serial-line",
            "port": args.port,
            "baudrate": args.baudrate,
        },
    )


def add_common_stream_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--server", default="http://127.0.0.1:8000")
    parser.add_argument("--node-id", default="BENCH-NODE-001")
    parser.add_argument("--asset-id", default="FG-BRG-001")
    parser.add_argument("--name", default="Competition rotating-machinery bench")
    parser.add_argument("--hardware", default="auto")
    parser.add_argument("--operating-system", default="auto")
    parser.add_argument("--sample-rate", type=float, default=25_600.0)
    parser.add_argument("--window-size", type=int, default=4096)
    parser.add_argument("--sequence-start", type=int, default=0)
    parser.add_argument("--rpm", type=float, default=1800.0)
    parser.add_argument("--load", type=float, default=70.0)
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--channel", default="acceleration_x")
    parser.add_argument(
        "--signal-column",
        default=None,
        help="CSV signal column name or zero-based index; defaults to automatic detection",
    )
    parser.add_argument("--unit", default="g")
    parser.add_argument("--sensor-position", default="drive-end bearing housing, radial")
    parser.add_argument(
        "--sensor-mounting",
        default="stud or magnetic base; disclose actual method",
    )
    parser.add_argument("--interval", type=float, default=0.0)
    parser.add_argument("--open-incident", action="store_true")
    parser.add_argument("--campaign-id", default=None)
    parser.add_argument("--campaign-manifest", type=Path, default=None)
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--timeout", type=float, default=12.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--spool-dir", type=Path, default=Path("runtime-data/edge-spool"))
    parser.add_argument("--spool-max-files", type=int, default=10_000)
    parser.add_argument("--flush-limit", type=int, default=100)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ForgeGuard hardware-neutral edge gateway")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect a local vibration CSV")
    inspect_parser.add_argument("csv", type=Path)
    inspect_parser.add_argument("--signal-column", default=None)

    stream_parser = subparsers.add_parser("stream-csv", help="Register and stream CSV windows")
    stream_parser.add_argument("csv", type=Path)
    stream_parser.add_argument("--hop-size", type=int, default=2048)
    add_common_stream_arguments(stream_parser)

    serial_parser = subparsers.add_parser(
        "stream-serial",
        help="Acquire newline-delimited samples from a real serial DAQ and stream them",
    )
    serial_parser.add_argument("--port", required=True)
    serial_parser.add_argument("--baudrate", type=int, default=921_600)
    add_common_stream_arguments(serial_parser)

    live_csv_parser = subparsers.add_parser(
        "stream-live-csv",
        help="Replay CSV windows through the real-time detection session API",
    )
    live_csv_parser.add_argument("csv", type=Path)
    live_csv_parser.add_argument("--hop-size", type=int, default=2048)
    add_common_stream_arguments(live_csv_parser)

    live_serial_parser = subparsers.add_parser(
        "stream-live-serial",
        help="Stream a serial DAQ through the real-time detection session API",
    )
    live_serial_parser.add_argument("--port", required=True)
    live_serial_parser.add_argument("--baudrate", type=int, default=921_600)
    add_common_stream_arguments(live_serial_parser)

    subparsers.add_parser("platform-info", help="Print detected edge platform metadata")
    subparsers.add_parser(
        "jetson-preflight",
        help="Validate Jetson Linux, CUDA, TensorRT, Docker, and NVIDIA runtime",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "inspect":
        asyncio.run(inspect_file(args.csv, args.signal_column))
    elif args.command == "stream-csv":
        asyncio.run(stream_file(args))
    elif args.command == "stream-serial":
        asyncio.run(stream_serial(args))
    elif args.command == "stream-live-csv":
        asyncio.run(stream_live_file(args))
    elif args.command == "stream-live-serial":
        asyncio.run(stream_live_serial(args))
    else:
        report = collect_platform_report()
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
        if args.command == "jetson-preflight" and not preflight_ok(report):
            raise SystemExit(2)


if __name__ == "__main__":
    main()
