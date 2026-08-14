from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(slots=True)
class InferenceResult:
    model_id: str
    runtime: str
    outputs: dict[str, np.ndarray]
    metadata: dict[str, Any]


class InferenceRuntime(ABC):
    name: str

    @abstractmethod
    def infer(self, inputs: dict[str, np.ndarray]) -> InferenceResult: ...

    @abstractmethod
    def ready(self) -> bool: ...


class NumpyFallbackRuntime(InferenceRuntime):
    name = "numpy-fallback"

    def __init__(self, model_id: str = "transparent-signal-fallback") -> None:
        self.model_id = model_id

    def ready(self) -> bool:
        return True

    def infer(self, inputs: dict[str, np.ndarray]) -> InferenceResult:
        signal = np.asarray(next(iter(inputs.values())), dtype=np.float32).reshape(-1)
        centered = signal - np.mean(signal)
        rms = float(np.sqrt(np.mean(centered**2)) + 1e-9)
        peak = float(np.max(np.abs(centered)))
        crest = peak / rms
        anomaly = float(np.clip(0.15 * rms + 0.08 * max(0.0, crest - 3.0), 0.0, 1.0))
        probabilities = np.asarray([[1.0 - anomaly, anomaly]], dtype=np.float32)
        return InferenceResult(
            model_id=self.model_id,
            runtime=self.name,
            outputs={"probabilities": probabilities},
            metadata={"rms": rms, "crest_factor": crest},
        )


class OnnxRuntimeAdapter(InferenceRuntime):
    name = "onnxruntime"

    def __init__(self, model_path: Path, providers: list[str] | None = None) -> None:
        import onnxruntime as ort

        self.model_path = Path(model_path)
        self.session = ort.InferenceSession(
            str(self.model_path),
            providers=providers or ort.get_available_providers(),
        )
        self.input_names = [item.name for item in self.session.get_inputs()]
        self.output_names = [item.name for item in self.session.get_outputs()]

    def ready(self) -> bool:
        return self.model_path.exists()

    def infer(self, inputs: dict[str, np.ndarray]) -> InferenceResult:
        feed = {
            name: np.ascontiguousarray(inputs[name])
            for name in self.input_names
        }
        outputs = self.session.run(self.output_names, feed)
        return InferenceResult(
            model_id=self.model_path.stem,
            runtime=self.name,
            outputs={name: np.asarray(value) for name, value in zip(self.output_names, outputs)},
            metadata={"providers": self.session.get_providers()},
        )


class TensorRTRuntimeAdapter(InferenceRuntime):
    """Native TensorRT engine runner using cuda-python.

    The adapter is loaded only on Jetson or CUDA systems where both TensorRT and
    cuda-python are available. Engine files must be built on the target GPU.
    """

    name = "tensorrt"

    def __init__(self, engine_path: Path) -> None:
        import tensorrt as trt
        from cuda import cudart

        self.trt = trt
        self.cudart = cudart
        self.engine_path = Path(engine_path)
        logger = trt.Logger(trt.Logger.WARNING)
        runtime = trt.Runtime(logger)
        engine_bytes = self.engine_path.read_bytes()
        self.engine = runtime.deserialize_cuda_engine(engine_bytes)
        if self.engine is None:
            raise RuntimeError(f"Unable to deserialize TensorRT engine: {engine_path}")
        self.context = self.engine.create_execution_context()
        if self.context is None:
            raise RuntimeError("Unable to create TensorRT execution context")
        status, stream = cudart.cudaStreamCreate()
        if status != cudart.cudaError_t.cudaSuccess:
            raise RuntimeError(f"cudaStreamCreate failed: {status}")
        self.stream = stream
        self.tensor_names = [self.engine.get_tensor_name(i) for i in range(self.engine.num_io_tensors)]

    def ready(self) -> bool:
        return self.engine_path.exists()

    def infer(self, inputs: dict[str, np.ndarray]) -> InferenceResult:
        trt = self.trt
        cudart = self.cudart
        device_ptrs: list[int] = []
        host_outputs: dict[str, np.ndarray] = {}
        try:
            for name in self.tensor_names:
                mode = self.engine.get_tensor_mode(name)
                if mode == trt.TensorIOMode.INPUT:
                    array = np.ascontiguousarray(inputs[name])
                    self.context.set_input_shape(name, array.shape)
                    status, device_ptr = cudart.cudaMalloc(array.nbytes)
                    if status != cudart.cudaError_t.cudaSuccess:
                        raise RuntimeError(f"cudaMalloc failed for input {name}: {status}")
                    device_ptrs.append(device_ptr)
                    status = cudart.cudaMemcpyAsync(
                        device_ptr,
                        array.ctypes.data,
                        array.nbytes,
                        cudart.cudaMemcpyKind.cudaMemcpyHostToDevice,
                        self.stream,
                    )[0]
                    if status != cudart.cudaError_t.cudaSuccess:
                        raise RuntimeError(f"cudaMemcpyAsync H2D failed for {name}: {status}")
                    self.context.set_tensor_address(name, device_ptr)

            for name in self.tensor_names:
                if self.engine.get_tensor_mode(name) != trt.TensorIOMode.OUTPUT:
                    continue
                shape = tuple(self.context.get_tensor_shape(name))
                dtype = trt.nptype(self.engine.get_tensor_dtype(name))
                host = np.empty(shape, dtype=dtype)
                status, device_ptr = cudart.cudaMalloc(host.nbytes)
                if status != cudart.cudaError_t.cudaSuccess:
                    raise RuntimeError(f"cudaMalloc failed for output {name}: {status}")
                device_ptrs.append(device_ptr)
                self.context.set_tensor_address(name, device_ptr)
                host_outputs[name] = host

            if not self.context.execute_async_v3(self.stream):
                raise RuntimeError("TensorRT execute_async_v3 returned false")

            for name, host in host_outputs.items():
                device_ptr = self.context.get_tensor_address(name)
                status = cudart.cudaMemcpyAsync(
                    host.ctypes.data,
                    device_ptr,
                    host.nbytes,
                    cudart.cudaMemcpyKind.cudaMemcpyDeviceToHost,
                    self.stream,
                )[0]
                if status != cudart.cudaError_t.cudaSuccess:
                    raise RuntimeError(f"cudaMemcpyAsync D2H failed for {name}: {status}")
            status = cudart.cudaStreamSynchronize(self.stream)[0]
            if status != cudart.cudaError_t.cudaSuccess:
                raise RuntimeError(f"cudaStreamSynchronize failed: {status}")
            return InferenceResult(
                model_id=self.engine_path.stem,
                runtime=self.name,
                outputs=host_outputs,
                metadata={"engine": str(self.engine_path)},
            )
        finally:
            for pointer in device_ptrs:
                cudart.cudaFree(pointer)


class RuntimeSelector:
    @staticmethod
    def select(
        *,
        tensorrt_engine: Path | None = None,
        onnx_model: Path | None = None,
        prefer_gpu: bool = True,
    ) -> InferenceRuntime:
        if prefer_gpu and tensorrt_engine and tensorrt_engine.exists():
            try:
                return TensorRTRuntimeAdapter(tensorrt_engine)
            except (ImportError, RuntimeError, OSError):
                pass
        if onnx_model and onnx_model.exists():
            try:
                return OnnxRuntimeAdapter(onnx_model)
            except (ImportError, RuntimeError, OSError):
                pass
        return NumpyFallbackRuntime()
