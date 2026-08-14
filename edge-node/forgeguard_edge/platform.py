from __future__ import annotations

import json
import os
import platform
import re
import shutil
import socket
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


_TEGRA_PATTERN = re.compile(
    r"#\s*R(?P<release>\d+)\s*\(release\),\s*REVISION:\s*(?P<revision>[0-9.]+)",
    re.IGNORECASE,
)


@dataclass(slots=True)
class PlatformCheck:
    name: str
    ok: bool
    detail: str
    required: bool = True


@dataclass(slots=True)
class PlatformReport:
    hostname: str
    architecture: str
    kernel: str
    operating_system: str
    python_version: str
    device_model: str | None
    is_jetson: bool
    l4t_release: str | None
    l4t_revision: str | None
    cuda_version: str | None
    tensorrt_version: str | None
    docker_version: str | None
    nvidia_runtime_configured: bool
    gpu_device_nodes: list[str] = field(default_factory=list)
    storage: list[dict[str, Any]] = field(default_factory=list)
    checks: list[PlatformCheck] = field(default_factory=list)

    @property
    def hardware_label(self) -> str:
        if self.device_model:
            return self.device_model
        return f"{self.architecture} edge computer"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip("\x00\n ")
    except OSError:
        return None


def parse_nv_tegra_release(text: str | None) -> tuple[str | None, str | None]:
    if not text:
        return None, None
    match = _TEGRA_PATTERN.search(text)
    if not match:
        return None, None
    return match.group("release"), match.group("revision")


def _run(command: list[str], timeout: float = 4.0) -> str | None:
    try:
        completed = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    output = completed.stdout.strip()
    return output or None


def _first_version(text: str | None) -> str | None:
    if not text:
        return None
    match = re.search(r"(?<!\d)(\d+\.\d+(?:\.\d+)?)(?!\d)", text)
    return match.group(1) if match else None


def _detect_cuda_version() -> str | None:
    version_json = Path("/usr/local/cuda/version.json")
    if version_json.exists():
        try:
            payload = json.loads(version_json.read_text(encoding="utf-8"))
            cuda = payload.get("cuda")
            if isinstance(cuda, dict) and cuda.get("version"):
                return str(cuda["version"])
        except (OSError, json.JSONDecodeError):
            pass
    output = _run(["nvcc", "--version"])
    if output:
        match = re.search(r"release\s+([0-9.]+)", output)
        if match:
            return match.group(1)
    return None


def _detect_tensorrt_version() -> str | None:
    package = _run(["dpkg-query", "-W", "-f=${Version}", "libnvinfer10"])
    if package:
        return package.split("-")[0]
    python_value = _run(
        [
            "python3",
            "-c",
            "import tensorrt as trt; print(trt.__version__)",
        ]
    )
    return _first_version(python_value)


def _detect_docker_version() -> str | None:
    output = _run(["docker", "version", "--format", "{{.Server.Version}}"])
    return _first_version(output)


def _nvidia_runtime_configured() -> bool:
    daemon = _read_text(Path("/etc/docker/daemon.json"))
    if daemon:
        try:
            payload = json.loads(daemon)
            if payload.get("default-runtime") == "nvidia":
                return True
            runtimes = payload.get("runtimes") or {}
            if "nvidia" in runtimes:
                return True
        except json.JSONDecodeError:
            pass
    output = _run(["docker", "info", "--format", "{{json .Runtimes}}"])
    return bool(output and "nvidia" in output.lower())


def _storage_inventory() -> list[dict[str, Any]]:
    output = _run(
        [
            "lsblk",
            "--json",
            "--bytes",
            "--output",
            "NAME,TYPE,SIZE,MODEL,MOUNTPOINTS",
        ]
    )
    if not output:
        return []
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return []
    devices: list[dict[str, Any]] = []
    for item in payload.get("blockdevices", []):
        if item.get("type") != "disk":
            continue
        devices.append(
            {
                "name": item.get("name"),
                "size_bytes": item.get("size"),
                "model": (item.get("model") or "").strip() or None,
                "mountpoints": item.get("mountpoints") or [],
            }
        )
    return devices


def collect_platform_report() -> PlatformReport:
    tegra_text = _read_text(Path("/etc/nv_tegra_release"))
    l4t_release, l4t_revision = parse_nv_tegra_release(tegra_text)
    model = _read_text(Path("/proc/device-tree/model"))
    is_jetson = bool(l4t_release or (model and "jetson" in model.lower()))
    gpu_nodes = sorted(
        str(path)
        for pattern in ("/dev/nvhost-*", "/dev/nvidia*", "/dev/tegra*")
        for path in Path("/dev").glob(Path(pattern).name)
    )
    report = PlatformReport(
        hostname=socket.gethostname(),
        architecture=platform.machine(),
        kernel=platform.release(),
        operating_system=platform.platform(),
        python_version=platform.python_version(),
        device_model=model,
        is_jetson=is_jetson,
        l4t_release=l4t_release,
        l4t_revision=l4t_revision,
        cuda_version=_detect_cuda_version(),
        tensorrt_version=_detect_tensorrt_version(),
        docker_version=_detect_docker_version(),
        nvidia_runtime_configured=_nvidia_runtime_configured(),
        gpu_device_nodes=gpu_nodes,
        storage=_storage_inventory(),
    )
    report.checks = build_preflight_checks(report)
    return report


def build_preflight_checks(report: PlatformReport) -> list[PlatformCheck]:
    l4t_current = False
    if report.l4t_release and report.l4t_revision:
        try:
            l4t_current = int(report.l4t_release) > 39 or (
                int(report.l4t_release) == 39 and float(report.l4t_revision) >= 2.0
            )
        except ValueError:
            l4t_current = False
    checks = [
        PlatformCheck(
            "architecture",
            report.architecture in {"aarch64", "arm64"},
            f"detected {report.architecture}; Jetson targets should report aarch64",
        ),
        PlatformCheck(
            "jetson_identity",
            report.is_jetson,
            report.device_model or "no Jetson identity detected",
        ),
        PlatformCheck(
            "jetson_linux",
            l4t_current,
            (
                f"L4T R{report.l4t_release} revision {report.l4t_revision}"
                if report.l4t_release
                else "missing /etc/nv_tegra_release"
            ),
        ),
        PlatformCheck(
            "cuda",
            report.cuda_version is not None,
            report.cuda_version or "CUDA toolkit not detected",
        ),
        PlatformCheck(
            "tensorrt",
            report.tensorrt_version is not None,
            report.tensorrt_version or "TensorRT not detected",
        ),
        PlatformCheck(
            "docker",
            report.docker_version is not None,
            report.docker_version or "Docker server not detected",
        ),
        PlatformCheck(
            "nvidia_container_runtime",
            report.nvidia_runtime_configured,
            "NVIDIA runtime available" if report.nvidia_runtime_configured else "runtime not configured",
        ),
        PlatformCheck(
            "gpu_device_nodes",
            bool(report.gpu_device_nodes),
            ", ".join(report.gpu_device_nodes[:6]) or "no GPU device nodes detected",
        ),
        PlatformCheck(
            "tegrastats",
            shutil.which("tegrastats") is not None,
            shutil.which("tegrastats") or "tegrastats not found",
            required=False,
        ),
    ]
    return checks


def preflight_ok(report: PlatformReport) -> bool:
    return all(check.ok for check in report.checks if check.required)
