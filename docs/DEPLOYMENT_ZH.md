# 跨平台部署手册

先阅读根目录 `README.md`。本手册只列部署步骤。

## Windows 10/11 x64

### 推荐：完整 Windows 包 + EXE

1. 解压完整 Windows ZIP；
2. 保持项目目录结构不变；
3. 安装并启动 Docker Desktop；
4. 双击根目录 `ForgeGuard-Nexus.exe`；
5. 浏览器访问 `http://localhost:8000`；
6. 停止时双击 `ForgeGuard-Nexus-Stop.exe`。

无 Docker 时可运行：

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\install-native.ps1
```

Windows 原生环境默认持久保存在：

```text
%LOCALAPPDATA%\ForgeGuardNexus\venv
```

再次安装或升级软件包时，锁文件未变化则直接复用，不再重新下载依赖。强制同步使用 `-Force`，彻底重建使用 `-Recreate`。

## Arch Linux

Docker：

```bash
bash start.sh
```

原生环境：

```bash
bash deploy/linux/install-native.sh
bash deploy/linux/run-native.sh
```

Linux 原生环境默认持久保存在：

```text
${XDG_DATA_HOME:-~/.local/share}/forgeguard-nexus/venv
```

代码目录升级不会删除该环境。依赖锁未变化时安装脚本会直接跳过 `pip install`。强制同步使用 `--force`，彻底重建使用 `--recreate`。

## Debian / Ubuntu

```bash
bash start.sh
```

或使用同一套原生 Linux 脚本。

## Jetson Orin

推荐环境为已经验证过的 JetPack 6.2.2 / L4T R36.5 / TensorRT 10.3：

```bash
bash deploy/jetson-5/preflight.sh
bash deploy/jetson-5/optimize.sh
bash deploy/jetson-5/run.sh
```

GPU 验证：

```bash
bash deploy/jetson-5/gpu-smoke.sh
```

Jetson 构建前建议至少保留 8 GB 空间，12 GB 以上更稳妥。不要安装桌面显卡版 NVIDIA 驱动替换 JetPack 驱动。

## 启动后

```text
主界面：http://localhost:8000
API 文档：http://localhost:8000/docs
```

## 数据入口

- 实时与外部设备：见 `docs/DATA_INPUT_ZH.md`；
- CSV 上传：主界面“数据检测与分析”；
- Windows EXE：见 `docs/WINDOWS_EXE_ZH.md`。

## scikit-learn 模型兼容性

生产推理使用 `selected_vibration_model.portable.npz`，以 `allow_pickle=False` 加载纯数值树结构和校准参数。`selected_vibration_model.joblib` 仅保留为研究/重训来源，不由启动器或生产 API 加载。原生环境仍固定 `scikit-learn==1.8.0` 用于评测与重训，但不会再因训练端 NumPy 2.x 与运行端 NumPy 1.26.4 的随机状态 pickle 差异而启动失败。
