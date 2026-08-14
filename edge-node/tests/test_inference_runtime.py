import numpy as np

from forgeguard_edge.inference_runtime import NumpyFallbackRuntime, RuntimeSelector


def test_numpy_fallback_runtime_is_deterministic():
    signal = np.sin(np.linspace(0, 20, 2048, dtype=np.float32))[None, :]
    runtime = NumpyFallbackRuntime()
    a = runtime.infer({"signal": signal})
    b = runtime.infer({"signal": signal})
    assert runtime.ready()
    assert a.runtime == "numpy-fallback"
    assert np.array_equal(a.outputs["probabilities"], b.outputs["probabilities"])
    assert a.outputs["probabilities"].shape == (1, 2)


def test_selector_falls_back_without_artifacts(tmp_path):
    runtime = RuntimeSelector.select(
        tensorrt_engine=tmp_path / "missing.engine",
        onnx_model=tmp_path / "missing.onnx",
    )
    assert isinstance(runtime, NumpyFallbackRuntime)
