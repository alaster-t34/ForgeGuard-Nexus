# Runtime dependency compatibility

## 生产推理模型

生产启动使用：

```text
backend/research/artifacts/selected_vibration_model.portable.npz
```

格式为 `forgeguard-portable-calibrated-hgb-v1`。文件只包含固定类型的 NumPy 数值数组，并使用 `allow_pickle=False` 加载。它不包含 Python 类实例、随机数生成器对象或任意可执行 pickle 内容。

`selected_vibration_model.joblib` 仅作为受信任的研究与可复现训练产物保留，不由生产启动器、原生环境校验器或 API 运行时加载。

## v0.7.7 失败原因

旧发布包在训练环境中使用 NumPy 2.3.5 保存 joblib 模型，但 Windows 原生锁定环境使用 NumPy 1.26.4。模型内部包含 NumPy 2.x 的 `PCG64` 随机状态对象，因此虽然 `scikit-learn==1.8.0` 已正确安装，反序列化仍会失败：

```text
ValueError: <class 'numpy.random._pcg64.PCG64'> is not a known BitGenerator module
```

v0.7.8 不通过强行升级用户 NumPy 来规避问题，而是将生产推理模型导出为稳定的数值结构，并对其与原 joblib 输出做逐概率一致性校验。

## 原生锁定环境

当前原生运行环境固定使用：

```text
Python 3.11 或 3.12
NumPy 1.26.4
SciPy 1.13.1
scikit-learn 1.8.0
joblib 1.4.2
```

scikit-learn 和 joblib 仍用于基准评测、模型训练、导出及研究工具；生产推理本身不依赖 joblib 反序列化。

## 持久化原生环境

Windows 和 Linux 的虚拟环境、环境指针与 pip 缓存保存在用户级稳定目录，不随项目文件夹删除。

- Windows：`%LOCALAPPDATA%\ForgeGuardNexus\venv`
- Linux：`${XDG_DATA_HOME:-~/.local/share}/forgeguard-nexus/venv`
- 用户级指针：`venv-path.txt`
- 自定义环境：`FORGEGUARD_VENV_DIR`

v0.7.8 将环境状态架构升级为 4。旧状态文件会触发一次**模型与依赖校验**，但只要已安装包版本正确，系统会直接补写状态文件，不执行 `pip install`。

依赖指纹基于规范化的包名和精确版本，不包含软件版本、项目路径、注释、空行、行顺序或换行符。
