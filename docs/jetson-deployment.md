# Jetson AGX Orin deployment profile

ForgeGuard treats Jetson AGX Orin as a first-party reference edge platform, not as a mandatory dependency.

## Responsibilities

The Jetson profile is responsible for local sensor/video ingestion, accelerated model inference, evidence quality checks, offline spooling, and safe synchronization with the ForgeGuard API. Business workflow, work orders, knowledge retrieval, and operator approval remain separable services.

## Supported modes

1. Simulation: no Jetson required.
2. Replay: public or historical signals stream through a real Jetson runtime.
3. Live: authorized sensors and cameras feed the Jetson gateway.

## Runtime policy

- deterministic signal-quality gates always remain active;
- GPU model failures fall back to a disclosed CPU or rule path;
- model output cannot directly control production equipment;
- high-risk work-order or return-to-service actions require human approval;
- Jetson platform versions are attached to every registered node and experiment campaign.

## Current implementation

ForgeGuard 0.3 adds:

- automatic Jetson/L4T/CUDA/TensorRT/Docker discovery;
- a strict Jetson preflight command;
- platform metadata in bench-node registration;
- a JetPack 7.2 post-flash bootstrap script;
- a Jetson-specific container profile;
- an NVIDIA GPU-container smoke test;
- explicit destructive-flash documentation and storage boundaries.

TensorRT model engines are intentionally not bundled yet. Engines must be built from disclosed source models on the target JetPack/TensorRT version, benchmarked, and recorded in the model registry before competition claims are made.
