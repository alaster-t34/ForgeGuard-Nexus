# Model and Data Boundaries

## Bundled baseline

The release contains a calibrated feature-based vibration classifier selected by the included benchmark workflow. It provides a reproducible CPU baseline and a transparent fallback. Its bundled results apply only to the disclosed evaluation protocol.

## Neural-model path

The edge runtime defines production adapters for:

- TensorRT serialized engines built on the target NVIDIA GPU.
- ONNX Runtime sessions on Windows and Linux.
- NumPy fallback when no artifact or provider is available.

A model is promoted only after:

- Asset-level train/validation/test separation.
- Cross-machine, speed and load tests.
- Calibration and selective-rejection evaluation.
- Missing-modal, noise and sensor-fault tests.
- Latency, memory, thermal and power measurement on target hardware.
- Model, data, weight and license provenance review.

## Public datasets

CWRU, Paderborn, XJTU-SY and visual anomaly datasets are downloaded from their official sources by the user. This repository does not redistribute them. Each external benchmark is labeled separately from synthetic OpenEval-RM and from any physical rig data.

## Evidence terminology

- **Simulation**: generated scenario and physics-informed signals.
- **Replay**: historical or public real data streamed through the edge protocol.
- **Live**: directly captured sensor or camera data.
- **Physical verification**: documented test specimen, sensor, DAQ, safety and operating condition.

The UI and reports must preserve these distinctions.

## scikit-learn 模型兼容性

生产推理使用 `selected_vibration_model.portable.npz`，以 `allow_pickle=False` 加载纯数值树结构和校准参数。`selected_vibration_model.joblib` 仅保留为研究/重训来源，不由启动器或生产 API 加载。原生环境仍固定 `scikit-learn==1.8.0` 用于评测与重训，但不会再因训练端 NumPy 2.x 与运行端 NumPy 1.26.4 的随机状态 pickle 差异而启动失败。
