# ForgeGuard Nexus 5.0 v0.7.8

## 修复内容

v0.7.7 在 Windows 原生环境中可能在 `[4/4]` 模型校验阶段失败：

```text
ValueError: <class 'numpy.random._pcg64.PCG64'> is not a known BitGenerator module
```

日志表明依赖安装本身已经成功，失败发生在 `joblib.load()`。原模型由 NumPy 2.3.5 环境保存，而 Windows 原生运行环境固定为 NumPy 1.26.4。joblib/pickle 同时保存了模型中的 NumPy 随机状态对象，因此仅固定 `scikit-learn==1.8.0` 仍不足以保证反序列化兼容。

## 新的生产模型格式

v0.7.8 新增：

```text
backend/research/artifacts/selected_vibration_model.portable.npz
```

格式：

```text
forgeguard-portable-calibrated-hgb-v1
```

该文件只保存：

- HGB 树节点数值；
- 特征索引和阈值；
- 缺失值分支；
- 叶节点输出；
- 多分类基线；
- Sigmoid 校准参数；
- 类别索引和来源哈希。

加载时固定使用 `numpy.load(..., allow_pickle=False)`，不再反序列化 Python 对象、NumPy BitGenerator 或任意 pickle 内容。

## 兼容性策略

- 生产 API、Windows 启动器和原生环境校验器只加载便携式 NPZ 模型；
- `selected_vibration_model.joblib` 仅作为受信任的研究与重训来源保留；
- 原生依赖仍固定 NumPy 1.26.4、SciPy 1.13.1、scikit-learn 1.8.0 和 joblib 1.4.2；
- 不需要为了启动软件把用户环境升级到 NumPy 2.x；
- 环境状态架构升级为 4，旧环境只重新校验和补写状态，不重复安装依赖。

## 一致性验证

便携式模型与原 joblib 模型在 64 组随机特征（包含 NaN 缺失值分支）上的：

- 原始 decision function 最大绝对误差：`0.0`；
- 校准概率最大绝对误差：`1.11e-16`；
- 每行概率和：`1.0`；
- NPZ 内对象数组数量：`0`；
- NPY 子文件格式：`1.0`。

## 升级行为

已有环境：

```text
%LOCALAPPDATA%\ForgeGuardNexus\venv
```

在 v0.7.8 中会被直接复用。首次启动新代码包时，系统会执行一次便携式模型校验并更新 `.forgeguard-env.json`，不会重新运行 pip 安装。
