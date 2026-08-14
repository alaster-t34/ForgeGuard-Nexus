from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pytest
import sklearn

from app.models.portable_hgb import PORTABLE_HGB_FORMAT, PortableCalibratedHGB
from app.models.vibration_selected import SelectedVibrationAdapter


BACKEND = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND.parent
CARD = BACKEND / "research" / "artifacts" / "selected_vibration_model.json"
PORTABLE = BACKEND / "research" / "artifacts" / "selected_vibration_model.portable.npz"
JOBLIB = BACKEND / "research" / "artifacts" / "selected_vibration_model.joblib"


def test_bundled_runtime_uses_portable_numeric_model() -> None:
    card = json.loads(CARD.read_text(encoding="utf-8"))
    adapter = SelectedVibrationAdapter(CARD)
    assert adapter.model_id == "dsp-calibrated-hgb-v0.2"
    assert adapter._mode == "portable-hgb"
    assert adapter.model.__class__.__name__ == "PortableCalibratedHGB"
    assert card["artifact_format"] == PORTABLE_HGB_FORMAT
    assert card["artifact"].endswith("selected_vibration_model.portable.npz")
    assert card["runtime_requirements"]["serialization"].endswith("allow_pickle=False")


def test_portable_model_matches_trusted_research_artifact() -> None:
    try:
        reference = joblib.load(JOBLIB)
    except (TypeError, ValueError) as exc:
        pytest.skip(
            "The legacy research-only Joblib artifact was serialized with an "
            f"incompatible NumPy random-state format: {exc}"
        )
    portable = PortableCalibratedHGB(PORTABLE)
    rng = np.random.default_rng(20260803)
    features = rng.normal(size=(64, portable.n_features))
    features[0, 0] = np.nan
    expected = reference.predict_proba(features)
    actual = portable.predict_proba(features)
    np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(actual.sum(axis=1), 1.0, rtol=0.0, atol=1e-12)


def test_portable_npz_contains_no_object_arrays() -> None:
    with np.load(PORTABLE, allow_pickle=False) as payload:
        assert payload.files
        assert all(payload[name].dtype.kind != "O" for name in payload.files)
        assert str(payload["format_version"].item()) == PORTABLE_HGB_FORMAT


def test_dependency_files_pin_supported_runtime_stack() -> None:
    assert sklearn.__version__ == "1.8.0"
    assert "scikit-learn==1.8.0" in (BACKEND / "requirements.lock.txt").read_text(
        encoding="utf-8"
    )
    assert "numpy==1.26.4" in (BACKEND / "requirements.lock.txt").read_text(
        encoding="utf-8"
    )
    assert "scikit-learn==1.8.0" in (BACKEND / "requirements.txt").read_text(
        encoding="utf-8"
    )
    assert '"scikit-learn==1.8.0"' in (BACKEND / "pyproject.toml").read_text(
        encoding="utf-8"
    )
