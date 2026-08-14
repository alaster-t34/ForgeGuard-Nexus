# Research-informed model strategy

ForgeGuard uses a model portfolio rather than one fixed "best" model. Industrial performance depends on defect type, data volume, camera geometry, operating domain, latency, hardware, and licensing.

## Visual path

- **Known, labeled defect classes:** retain a supervised detector/segmenter when it is calibrated on the real acquisition domain.
- **Unknown or low-shot anomalies:** benchmark current Anomalib models such as EfficientAD, PatchCore, AnomalyDINO, Dinomaly, and AnomalyVFM.
- **Ambiguous open-vocabulary defects:** adopt the IndusAgent pattern: dynamic crop, high-frequency enhancement, normal-prior retrieval, and tool-use gating.
- **Safety rule:** an MLLM explanation cannot override a poor-quality image or a calibrated anomaly detector without independent evidence.

## Vibration path

- Preserve interpretable DSP features, envelope analysis, order tracking, and defect-frequency checks.
- Evaluate BearLLM-style unified representations with a fault-free reference for cross-condition reasoning.
- Evaluate newer frequency-aware foundation-model candidates, but only after leakage-free cross-machine tests.
- Use supervised models only inside their declared training domain.

## RUL path

- Keep FP-FLNet as a disclosed baseline where its evaluation protocol is valid.
- Add foundation-model and transformer adapters only after fixed splits, no test-label tuning, uncertainty calibration, and per-asset reporting.
- Expose quantiles and failure conditions rather than a single exact lifetime.

## Agent/reasoning path

- Business state transitions and safety gates are deterministic and typed.
- An optional OpenAI-compatible LLM may generate plans, explanations, and search queries.
- Tool access is least-privilege, read-only by default, and fully audited.
- External search is routed through SearXNG or a controlled provider; agents never receive arbitrary shell or secret access.
