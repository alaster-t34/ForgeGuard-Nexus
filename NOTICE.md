# Third-party, prior-work, model, and dataset notice

ForgeGuard Nexus is a new Apache-2.0 implementation. Its architecture was informed by public industrial-agent, predictive-maintenance, anomaly-detection, and CMMS systems, including IBM AssetOpsBench, Anomalib, Atlas CMMS, BearLLM, and IndusAgent. No source code from those projects is copied into the ForgeGuard core.

## Prior project boundary

An earlier RV1126B/IIS3DWB/RKNN bearing application is treated as prior work and an optional edge/model provider. Its source, weights, datasets, and claimed results are not silently relabelled as new ForgeGuard contributions. Any later import must be listed in a provenance manifest with authorship, license, hash, and modification history.

## Public datasets

ForgeGuard redistributes only the project-generated `ForgeGuard OpenEval-RM` dataset under Apache-2.0. CWRU, Paderborn, XJTU-SY, MVTec AD, and MVTec AD 2 are manifest-only integrations: users download them from the official source and accept the source terms. They are excluded from version control and release packaging by default.

## Models and optional runtimes

The default selected vibration artifact is trained by the included benchmark code on OpenEval-RM. Optional Anomalib, OpenVINO, PyTorch, serial, MQTT, OPC UA, LLM, and external-search adapters remain governed by their own licenses and deployment terms. Model cards must record the weight source, training data, version, hash, runtime, evaluation scope, and commercial restrictions before use in a public release.

## Scientific boundary

Synthetic, public-dataset, and physical-rig results are reported separately. A synthetic benchmark result is not evidence of factory accuracy; a public-dataset result is not a plant safety case; and an Agent recommendation is not autonomous permission to operate industrial machinery.

## Jetson deployment profile

The Jetson AGX Orin integration scripts and platform discovery code are new ForgeGuard work. NVIDIA JetPack, CUDA, TensorRT, NGC container images, and related trademarks remain NVIDIA property and are governed by their respective licenses. No NVIDIA binaries are redistributed in this repository.
