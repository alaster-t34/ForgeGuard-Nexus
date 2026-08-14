# Software Bill of Materials — ForgeGuard Nexus 5.0

Core runtime:

- Docker backend Python 3.11; native backend Python 3.11/3.12; edge client Python 3.10+.
- FastAPI and Uvicorn.
- Pydantic 2 and pydantic-settings.
- SQLAlchemy 2; SQLite default; psycopg optional for PostgreSQL.
- NumPy, SciPy, scikit-learn and joblib for the bundled vibration baseline and evaluation tools.
- HTTPX for local reasoning and search connectors.
- Static HTML/CSS/JavaScript frontend with no runtime Node.js dependency.

Optional edge runtime:

- ONNX Runtime.
- NVIDIA TensorRT and cuda-python on supported NVIDIA devices.
- PySerial for serial DAQ adapters.
- NVIDIA JetPack components retain NVIDIA license terms.

External data and models are not redistributed unless their terms explicitly permit it. Review dataset and model cards before publication.

## scikit-learn 模型兼容性

生产推理使用 `selected_vibration_model.portable.npz`，以 `allow_pickle=False` 加载纯数值树结构和校准参数。`selected_vibration_model.joblib` 仅保留为研究/重训来源，不由启动器或生产 API 加载。原生环境仍固定 `scikit-learn==1.8.0` 用于评测与重训，但不会再因训练端 NumPy 2.x 与运行端 NumPy 1.26.4 的随机状态 pickle 差异而启动失败。
