from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HELPER_PATH = ROOT / "scripts" / "native_env.py"


def _supported_python_info() -> dict[str, object]:
    return {
        "version": "3.11.9",
        "major": 3,
        "minor": 11,
        "executable": sys.executable,
        "platform": sys.platform,
        "machine": "test-machine",
    }


def _load_helper(path: Path = HELPER_PATH, module_name: str = "forgeguard_native_env"):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dependency_fingerprint_is_semantic_and_covers_both_lock_files(tmp_path, monkeypatch) -> None:
    helper = _load_helper()
    first = tmp_path / "backend.lock"
    second = tmp_path / "edge.lock"
    first.write_text("# comment\r\nscikit-learn==1.8.0\r\nnumpy==1.26.4\r\n", encoding="utf-8")
    second.write_text("pyserial==3.5\n", encoding="utf-8")
    monkeypatch.setattr(helper, "LOCK_FILES", (first, second))
    fingerprint_a = helper.dependency_fingerprint()

    # Formatting, comments and package order do not represent a dependency change.
    first.write_text("numpy==1.26.4\n\nscikit-learn==1.8.0  # ignored?\n", encoding="utf-8")
    # Inline comments are not valid exact pins in our lock format, so use a pure reorder.
    first.write_text("numpy==1.26.4\n# another comment\nscikit-learn==1.8.0\n", encoding="utf-8")
    fingerprint_b = helper.dependency_fingerprint()

    assert fingerprint_a == fingerprint_b
    assert len(fingerprint_a) == 64
    expected = helper._parse_locked_requirements()
    assert expected["scikit-learn"] == "1.8.0"
    assert expected["pyserial"] == "3.5"


def test_environment_state_reuses_matching_persistent_environment(tmp_path, monkeypatch) -> None:
    helper = _load_helper()
    monkeypatch.setattr(helper, "venv_python", lambda _venv: Path(sys.executable))
    monkeypatch.setattr(helper, "_run_python_info", lambda _python: _supported_python_info())
    payload = helper.write_state(tmp_path)
    ready, reason = helper.environment_status(tmp_path)
    assert ready is True
    assert reason == "ready"
    assert payload["dependency_fingerprint"] == helper.dependency_fingerprint()

    marker = tmp_path / helper.STATE_FILE
    state = json.loads(marker.read_text(encoding="utf-8"))
    state["dependency_fingerprint"] = "0" * 64
    marker.write_text(json.dumps(state), encoding="utf-8")
    ready, reason = helper.environment_status(tmp_path)
    assert ready is False
    assert reason == "locked dependency set changed"


def test_environment_status_repairs_missing_or_stale_marker_without_pip(tmp_path, monkeypatch) -> None:
    helper = _load_helper(module_name="forgeguard_native_env_repair")
    monkeypatch.setattr(helper, "venv_python", lambda _venv: Path(sys.executable))
    monkeypatch.setattr(helper, "_run_python_info", lambda _python: _supported_python_info())

    calls = {"verify": 0, "write": 0}

    def fake_verify(_venv: Path):
        calls["verify"] += 1
        return {"python": "test", "failures": []}

    original_write = helper.write_state

    def counted_write(venv: Path):
        calls["write"] += 1
        return original_write(venv)

    monkeypatch.setattr(helper, "verify_environment", fake_verify)
    monkeypatch.setattr(helper, "write_state", counted_write)

    ready, reason = helper.environment_status(tmp_path, repair=True)
    assert ready is True
    assert "reused after state repair" in reason
    assert calls == {"verify": 1, "write": 1}
    assert (tmp_path / helper.STATE_FILE).is_file()

    # A subsequent launch takes the fast marker path and does not verify again.
    ready, reason = helper.environment_status(tmp_path, repair=True)
    assert ready is True
    assert reason == "ready"
    assert calls == {"verify": 1, "write": 1}


def test_state_created_in_one_extracted_copy_is_reused_by_another(tmp_path, monkeypatch) -> None:
    # The state fingerprint contains only the semantic dependency set, never the
    # project path or application version. Simulate two separately extracted copies.
    helper_a = _load_helper(module_name="forgeguard_native_env_copy_a")
    helper_b = _load_helper(module_name="forgeguard_native_env_copy_b")
    monkeypatch.setattr(helper_a, "venv_python", lambda _venv: Path(sys.executable))
    monkeypatch.setattr(helper_b, "venv_python", lambda _venv: Path(sys.executable))
    monkeypatch.setattr(helper_a, "_run_python_info", lambda _python: _supported_python_info())
    monkeypatch.setattr(helper_b, "_run_python_info", lambda _python: _supported_python_info())

    helper_a.write_state(tmp_path)
    ready, reason = helper_b.environment_status(tmp_path)
    assert ready is True
    assert reason == "ready"


def test_native_installers_use_external_pointer_and_repair_mode() -> None:
    linux_install = (ROOT / "deploy" / "linux" / "install-native.sh").read_text(encoding="utf-8")
    linux_run = (ROOT / "deploy" / "linux" / "run-native.sh").read_text(encoding="utf-8")
    windows_install = (ROOT / "deploy" / "windows" / "install-native.ps1").read_text(encoding="utf-8")
    windows_run = (ROOT / "deploy" / "windows" / "run-native.ps1").read_text(encoding="utf-8")
    launcher = (ROOT / "windows-launcher" / "main_windows.go").read_text(encoding="utf-8")
    service = (ROOT / "deploy" / "linux" / "forgeguard.service").read_text(encoding="utf-8")

    assert "venv-path.txt" in linux_install
    assert "--repair" in linux_install
    assert "Dependency installation skipped" in linux_install
    assert "venv-path.txt" in linux_run
    assert "--repair" in linux_run

    assert "ForgeGuardNexus" in windows_install
    assert "venv-path.txt" in windows_install
    assert "Write-Utf8NoBom" in windows_install
    assert "--repair" in windows_install
    assert "Dependency installation skipped" in windows_install
    assert "venv-path.txt" in windows_run
    assert "--repair" in windows_run

    assert 'readPointer(filepath.Join(runtimeHome, "venv-path.txt"))' in launcher
    assert "FORGEGUARD_RUNTIME_HOME" in launcher
    assert "TrimPrefix" in launcher
    assert '"--repair", "--quiet"' in launcher
    assert "nativeEnvironmentReady" in launcher
    assert "deploy/linux/run-native.sh" in service
    assert ".venv/bin/uvicorn" not in service
    assert "-m venv .venv" not in linux_install
    assert "-m venv .venv" not in windows_install
