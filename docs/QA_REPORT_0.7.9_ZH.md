# ForgeGuard Nexus v0.7.9 修正版验证报告

验证日期：2026-08-06

## 结论

v0.7.9 已在 Windows、中文项目路径和 CPython 3.12.9 下完成回归。原有双击启动、PowerShell 原生安装、Docker 启动、浏览器/API 访问和边缘 CSV 回放入口均保留。

## Python 与中文路径

- `deploy/windows/check-python.ps1` 在 0.71 秒内发现 `%LOCALAPPDATA%\Programs\Python\Python312\python.exe`；
- 检测结果：Python 3.12.9，来源为官方当前用户安装目录；
- 现有 `%LOCALAPPDATA%\ForgeGuardNexus\venv` 状态检查返回 `ready`；
- 项目位于包含中文字符的路径，PowerShell 检测、Python 子进程以及 GB18030 中文文件名和中文表头回放均通过。

## 自动测试

- 后端：38 项通过，1 项跳过；
- 边缘节点：8 项通过；
- 修改文件阻断级 Ruff 检查：通过；
- Python `compileall`：通过；
- 前端 JavaScript `node --check`：通过；
- Windows PowerShell 脚本语法解析：通过；
- Windows x64 Go 启动器：4 个 EXE 重建成功。

跳过项只比较旧的研究用 Joblib 模型与便携模型。该 Joblib 文件使用了与当前 NumPy 1.26 不兼容的随机状态序列化格式；正式运行不加载它，而是加载 `allow_pickle=False` 的便携 NPZ 模型。便携模型加载、安全格式和运行时选择测试仍通过。

全仓库 Ruff 仍能看到旧版本遗留的 326 条格式/现代化建议，因此没有把“清空全部历史风格告警”作为本修正版的发布条件；本次修改文件的语法错误、未定义名称等阻断项为 0。

## CSV 实测

- UTF-8 BOM、GB18030、带 BOM 的 UTF-16：通过；
- 中文文件名和中文信号列：通过；
- 257 列输入被正确拒绝；
- 边缘回放只读取选定信号列，不再混入时间戳；
- `train_merged.csv`：119.53 MiB、589,824 个数值样本，5.79 秒完成解析，自动选中 `acceleration_x`；
- 合并数据含 `sample_id` 时会明确警告：当前历史分析把信号列视为连续波形，应先筛选单个样本以避免跨样本窗口。

完整限制见 `CSV_LIMITS_AUDIT_ZH.md`。

## Windows 启动器

重建的文件：

- `ForgeGuard-Nexus.exe`；
- `ForgeGuard-Nexus-Desktop.exe`；
- `ForgeGuard-Nexus-Stop.exe`；
- `ForgeGuard-Native-Setup.exe`。

前三个入口保持同一启动器内容和原有文件名。安装器保持控制台入口，以便显示原生环境安装进度。
