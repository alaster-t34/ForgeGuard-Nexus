from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK_FILES = (
    ROOT / "backend" / "requirements.lock.txt",
    ROOT / "edge-node" / "requirements.lock.txt",
)
STATE_FILE = ".forgeguard-env.json"
SCHEMA_VERSION = 4
MIN_PYTHON = (3, 11)
MAX_PYTHON_EXCLUSIVE = (3, 13)


def _utf8_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _canonical_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _parse_locked_requirements() -> dict[str, str]:
    """Return a semantic package/version map.

    The environment fingerprint intentionally ignores comments, blank lines,
    lock-file order and line endings. Those formatting-only changes must never
    trigger a reinstall.
    """

    expected: dict[str, str] = {}
    for path in LOCK_FILES:
        if not path.is_file():
            raise FileNotFoundError(f"missing lock file: {path}")
        for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            line = line.split(";", 1)[0].strip()
            if "==" not in line:
                raise ValueError(
                    f"native lock entries must use exact pins: {path}:{line_number}: {raw}"
                )
            name, version = line.split("==", 1)
            name = name.split("[", 1)[0].strip()
            canonical = _canonical_name(name)
            version = version.strip()
            previous = expected.get(canonical)
            if previous is not None and previous != version:
                raise ValueError(
                    f"conflicting lock versions for {canonical}: {previous} vs {version}"
                )
            expected[canonical] = version
    return dict(sorted(expected.items()))


def dependency_fingerprint() -> str:
    payload = {
        "format": "forgeguard-native-requirements-v1",
        "requirements": _parse_locked_requirements(),
    }
    canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _run_python_info(python_path: Path) -> dict[str, object]:
    code = (
        "import json,platform,sys;"
        "print(json.dumps({'version':platform.python_version(),"
        "'major':sys.version_info.major,'minor':sys.version_info.minor,"
        "'executable':sys.executable,'platform':sys.platform,"
        "'machine':platform.machine()}))"
    )
    result = subprocess.run(
        [str(python_path), "-c", code],
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=_utf8_subprocess_env(),
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "virtual environment Python failed")
    return json.loads(result.stdout.strip())


def _python_version_supported(info: dict[str, object]) -> bool:
    version = (int(info["major"]), int(info["minor"]))
    return MIN_PYTHON <= version < MAX_PYTHON_EXCLUSIVE


def state_path(venv_dir: Path) -> Path:
    return venv_dir / STATE_FILE


def _state_matches(venv_dir: Path, info: dict[str, object]) -> tuple[bool, str]:
    marker = state_path(venv_dir)
    if not marker.is_file():
        return False, f"missing state marker: {marker}"
    try:
        state = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"invalid state marker: {exc}"
    if state.get("schema_version") != SCHEMA_VERSION:
        return False, "environment state schema changed"
    if state.get("dependency_fingerprint") != dependency_fingerprint():
        return False, "locked dependency set changed"
    if state.get("python_major_minor") != f"{info['major']}.{info['minor']}":
        return False, "virtual environment Python version changed"
    if state.get("platform") != str(info["platform"]):
        return False, "virtual environment belongs to another operating system"
    if _canonical_name(str(state.get("machine", ""))) != _canonical_name(str(info["machine"])):
        return False, "virtual environment belongs to another CPU architecture"
    return True, "ready"


def environment_status(venv_dir: Path, *, repair: bool = False) -> tuple[bool, str]:
    """Check whether an existing environment can be reused.

    With repair=True, a missing/stale marker is self-healed after verifying the
    actually installed packages and bundled model. This prevents a deleted
    marker, a newly extracted project directory, or formatting-only lock-file
    changes from causing a full pip reinstall.
    """

    python_path = venv_python(venv_dir)
    if not python_path.is_file():
        return False, f"missing interpreter: {python_path}"
    try:
        info = _run_python_info(python_path)
    except Exception as exc:  # noqa: BLE001 - surfaced to installer/launcher
        return False, f"virtual environment interpreter is unusable: {exc}"
    if not _python_version_supported(info):
        return False, f"Python {info['version']} is outside the supported 3.11/3.12 range"

    matches, reason = _state_matches(venv_dir, info)
    if matches:
        return True, reason
    if not repair:
        return False, reason

    try:
        verify_environment(venv_dir)
        write_state(venv_dir)
    except Exception as exc:  # noqa: BLE001
        return False, f"{reason}; installed environment verification failed: {exc}"
    return True, f"reused after state repair ({reason})"


def verify_environment(venv_dir: Path) -> dict[str, object]:
    python_path = venv_python(venv_dir)
    if not python_path.is_file():
        raise RuntimeError(f"missing interpreter: {python_path}")
    expected = _parse_locked_requirements()
    code = r'''
import json
import os
import platform
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

expected = json.loads(os.environ["FORGEGUARD_EXPECTED_PACKAGES"])
failures = []
for name, wanted in expected.items():
    try:
        actual = version(name)
    except PackageNotFoundError:
        failures.append(f"{name}: missing (expected {wanted})")
        continue
    if actual != wanted:
        failures.append(f"{name}: {actual} (expected {wanted})")

model_class = None
model_format = None
probability_sum = None
if not failures:
    try:
        import numpy as np

        project_root = Path(os.environ["FORGEGUARD_PROJECT_ROOT"])
        sys.path.insert(0, str(project_root / "backend"))
        from app.models.portable_hgb import PortableCalibratedHGB

        card_path = Path(os.environ["FORGEGUARD_MODEL_CARD_PATH"])
        card = json.loads(card_path.read_text(encoding="utf-8"))
        artifact_path = project_root / card["artifact"]
        model = PortableCalibratedHGB(artifact_path)
        probabilities = model.predict_proba(np.zeros((1, model.n_features), dtype=np.float64))
        if probabilities.shape != (1, model.n_classes):
            raise RuntimeError(f"unexpected probability shape: {probabilities.shape}")
        if not np.all(np.isfinite(probabilities)):
            raise RuntimeError("model returned non-finite probabilities")
        probability_sum = float(probabilities.sum())
        if not np.isclose(probability_sum, 1.0, atol=1e-12):
            raise RuntimeError(f"probabilities sum to {probability_sum}, expected 1.0")
        model_class = model.model_class
        model_format = card.get("artifact_format")
    except Exception as exc:
        failures.append(f"portable-model: {type(exc).__name__}: {exc}")

payload = {
    "python": platform.python_version(),
    "platform": sys.platform,
    "machine": platform.machine(),
    "model_class": model_class,
    "model_format": model_format,
    "probability_sum": probability_sum,
    "failures": failures,
}
print(json.dumps(payload))
raise SystemExit(1 if failures else 0)
'''
    env = _utf8_subprocess_env()
    env["FORGEGUARD_EXPECTED_PACKAGES"] = json.dumps(expected)
    env["FORGEGUARD_PROJECT_ROOT"] = str(ROOT)
    env["FORGEGUARD_MODEL_CARD_PATH"] = str(
        ROOT / "backend" / "research" / "artifacts" / "selected_vibration_model.json"
    )
    result = subprocess.run(
        [str(python_path), "-c", code],
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=180,
    )
    if not result.stdout.strip():
        raise RuntimeError(result.stderr.strip() or "environment verification failed")
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    if result.returncode != 0:
        raise RuntimeError("; ".join(payload.get("failures", [])))
    return payload


def write_state(venv_dir: Path) -> dict[str, object]:
    python_path = venv_python(venv_dir)
    info = _run_python_info(python_path)
    if not _python_version_supported(info):
        raise RuntimeError(f"unsupported Python version: {info['version']}")
    requirements = _parse_locked_requirements()
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "dependency_fingerprint": dependency_fingerprint(),
        "requirements": requirements,
        "python_version": info["version"],
        "python_major_minor": f"{info['major']}.{info['minor']}",
        "platform": info["platform"],
        "machine": info["machine"],
        "interpreter": info["executable"],
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "lock_files": [path.relative_to(ROOT).as_posix() for path in LOCK_FILES],
    }
    marker = state_path(venv_dir)
    marker.parent.mkdir(parents=True, exist_ok=True)
    temporary = marker.with_suffix(marker.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(marker)
    return payload


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="ForgeGuard persistent native environment manager")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("fingerprint")
    for name in ("status", "verify", "write"):
        command = sub.add_parser(name)
        command.add_argument("--venv", required=True, type=Path)
        command.add_argument("--quiet", action="store_true")
        if name == "status":
            command.add_argument(
                "--repair",
                action="store_true",
                help="verify installed packages and recreate a missing/stale state marker",
            )
    args = parser.parse_args()

    if args.command == "fingerprint":
        print(dependency_fingerprint())
        return 0
    venv_dir = args.venv.expanduser().resolve()
    if args.command == "status":
        ready, reason = environment_status(venv_dir, repair=args.repair)
        if not args.quiet:
            print(json.dumps({"ready": ready, "reason": reason}, ensure_ascii=False))
        return 0 if ready else 1
    if args.command == "verify":
        try:
            payload = verify_environment(venv_dir)
        except Exception as exc:  # noqa: BLE001
            if not args.quiet:
                print(json.dumps({"verified": False, "error": str(exc)}, ensure_ascii=False))
            return 1
        if not args.quiet:
            print(json.dumps({"verified": True, **payload}, ensure_ascii=False))
        return 0
    if args.command == "write":
        payload = write_state(venv_dir)
        if not args.quiet:
            print(json.dumps(payload, ensure_ascii=False))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
