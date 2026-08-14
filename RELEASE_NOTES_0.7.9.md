# ForgeGuard Nexus 5.0 v0.7.9

## Windows Python 3.12 探测修复

旧安装脚本只执行 `py` 和 PATH 中的 `python`。当 Python 3.12 安装在官方用户目录、Conda 命名环境或注册表已登记但未加入 PATH 时，安装器会错误地提示没有兼容 Python。

v0.7.9 按以下来源探测 CPython 3.12/3.11，并优先选择 3.12：

1. `FORGEGUARD_PYTHON` 显式路径；
2. Windows `py -3.12` / `py -3.11`；
3. `%LOCALAPPDATA%\Programs\Python\Python312` 等官方安装目录；
4. PATH 中的 Python；
5. 当前 Conda、Conda 环境列表及常见 Anaconda/Miniconda/Miniforge 目录；
6. Windows PythonCore 注册表。

可在项目目录运行以下命令，只检测、不安装：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\windows\check-python.ps1
```

## 中文路径与控制台 UTF-8 修复

- PowerShell 5.1、Python 子进程和安装环境统一启用 UTF-8；
- `venv-path.txt` 和 `.venv-path.txt` 始终按 UTF-8 读取；
- Windows 控制台启动器显式切换输入/输出代码页为 UTF-8；
- 原生服务输出和错误日志固定为 UTF-8；
- UTF-16 CSV 在 BOM 存在时优先按 UTF-16 解码，避免被 GB18030 误判。

## CSV 限制审计与修复

- 历史 CSV 上传：128 MiB、1,000,000 数据行、256 列、单字段 1 MiB；
- 支持 UTF-8/UTF-8 BOM、GB18030、带 BOM 的 UTF-16；
- 支持逗号、分号、Tab 和竖线分隔；
- 自动优先识别 `acceleration_x` 等信号列；
- OpenEval 提交、XJTU-SY 适配器、OpenEval 索引生成和边缘 CSV 回放均增加明确边界；
- 边缘回放不再把时间戳、转速等其他数值列混入振动信号；
- Jetson OpenEval 回放改为标准单列纵向波形，并校验索引大小、行数、列数和必需字段；
- 新增 `GET /api/v1/analysis/csv/limits` 返回机器可读限制。

完整审计见 `docs/CSV_LIMITS_AUDIT_ZH.md`。

## 兼容性

- 仍支持双击 `ForgeGuard-Nexus.exe` / `ForgeGuard-Nexus-Desktop.exe`；
- 仍使用 `ForgeGuard-Nexus-Stop.exe` 停止服务；
- Docker、原生安装和浏览器访问方式不变；
- 依赖锁未变化，现有 `%LOCALAPPDATA%\ForgeGuardNexus\venv` 校验通过后可直接复用。
