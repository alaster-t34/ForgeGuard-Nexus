# ForgeGuard Nexus 5.0 v0.7.5

## 主要修复

- 原生 `.venv` 改为用户级持久化环境，不再随每次解压的软件目录删除；
- Windows 默认路径：`%LOCALAPPDATA%\ForgeGuardNexus\venv`；
- Linux 默认路径：`${XDG_DATA_HOME:-~/.local/share}/forgeguard-nexus/venv`；
- 安装脚本对后端与边缘端锁文件计算联合 SHA-256 指纹；
- 指纹一致时直接跳过依赖安装；
- 依赖变化时在现有环境内增量同步，不无条件重建；
- 新增 `--force`/`-Force` 和 `--recreate`/`-Recreate`；
- Windows EXE 启动器可以发现并验证持久化环境；
- Linux/Windows 原生运行脚本可在环境缺失或过期时自动同步一次；
- 环境安装后验证所有固定依赖版本和内置 scikit-learn 模型；
- 原生 Python 明确限定为 3.11/3.12，避免 Python 3.13 与 NumPy 1.26.4 不兼容。

## 升级说明

从 0.7.4 或更早版本首次升级时，需要进行一次持久环境安装。之后只要依赖锁文件不变，即使删除旧代码目录并解压新版本，也不会重新安装依赖。
