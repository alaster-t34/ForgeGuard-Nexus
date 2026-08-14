# TensorRT model directory

TensorRT engines are target-specific and should be built on the target Jetson or NVIDIA GPU from a validated ONNX artifact.

Use `deploy/jetson-5/gpu-smoke.sh` to verify the native TensorRT toolchain. The smoke test does not claim that the bundled CPU baseline runs on TensorRT.

Do not commit proprietary or undisclosed model weights. Every promoted engine requires a model card, training-data provenance, calibration report and target-hardware benchmark.
