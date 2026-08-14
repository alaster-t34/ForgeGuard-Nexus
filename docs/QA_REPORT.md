# ForgeGuard Nexus 5.0 / v0.7.8 QA 报告

## 修复目标

验证 Windows 日志中出现的 NumPy `PCG64` joblib 反序列化失败已从生产启动路径移除，同时确保便携式模型输出与原研究模型一致。

## 根因复现

已确认原研究模型的生成环境：

```text
Python 3.13.5
NumPy 2.3.5
SciPy 1.17.0
scikit-learn 1.8.0
joblib 1.5.3
```

旧 Windows 原生锁定环境：

```text
Python 3.12
NumPy 1.26.4
SciPy 1.13.1
scikit-learn 1.8.0
joblib 1.4.2
```

用户日志中依赖安装成功，随后 `joblib.load()` 在 NumPy BitGenerator 重建阶段失败。该问题不是 scikit-learn 1.8.0 未安装。

## 自动测试

| 检查 | 结果 |
|---|---:|
| 后端与边缘端测试 | 37 passed |
| 便携式 HGB 与 joblib decision function 对比 | 最大误差 0.0 |
| 便携式 HGB 与 joblib 概率对比 | 最大误差 1.11e-16 |
| 缺失值分支对比 | PASS |
| NPZ `allow_pickle=False` 加载 | PASS |
| NPZ 对象数组审计 | 0 |
| NPZ 子文件版本 | NPY 1.0 |
| 概率有限性与归一化 | PASS |
| 原生环境状态架构 | 4 |
| Python compileall | PASS |
| JavaScript 语法 | PASS |
| Linux/Jetson Shell 语法 | PASS |
| YAML/Compose 解析 | PASS |
| Windows x64 启动器交叉编译 | PASS |
| ZIP/TAR 完整性 | PASS |
| MANIFEST SHA-256 | PASS |

## 运行时路径验证

生产模型卡指向：

```text
backend/research/artifacts/selected_vibration_model.portable.npz
```

`SelectedVibrationAdapter` 识别为：

```text
portable-hgb
```

`scripts/native_env.py verify` 使用便携式模型执行零向量推理，并校验输出形状、有限值和概率和。该路径不导入或加载 joblib 模型。

## 保留边界

- 研究用 joblib 文件仍是 pickle 体系，只允许在可信、匹配的训练环境中使用；
- 当前测试环境不是 Windows，无法直接复现用户设备上的 PowerShell 和 EXE 双击过程；
- Windows 启动器完成了 Windows x64 交叉编译和代码路径检查；
- 用户现有 Python 3.12 虚拟环境应在新包中直接通过状态修复，无需重新安装依赖。
