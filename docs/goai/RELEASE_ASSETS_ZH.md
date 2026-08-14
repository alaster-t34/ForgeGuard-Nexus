# 不进入 Git history 的发布资产

本仓库 ZIP 有意排除了以下类别，以避免 GitHub 大文件限制、隐私泄露和无意义的仓库膨胀。

## 1. Demo 视频

原始完整包包含：

- Windows 演示视频：约 348 MB；
- Jetson 演示视频：约 39 MB。

建议：

- 2 分钟 Hero Demo：上传公开视频平台或 GitHub Release；
- 完整 Windows / Jetson Demo：作为补充验证材料放 GitHub Release 或视频平台；
- README/PPT 只放稳定链接，不把大视频 commit 到源码仓库。

## 2. Windows 可执行文件

原始完整包包含预编译 Windows x64 启动器/安装器。源码在 `windows-launcher/` 和 `deploy/windows/` 中。

建议把预编译 EXE 放到 GitHub Release，而不是 Git history。这样源码仓库保持可审计，Release 仍可提供“一键运行”体验。

## 3. 大型 CSV 展开文件

`train_merged.csv` 和 `test_merged.csv` 超大，且内容来自已经保留的 OpenEval-RM 紧凑数据/元数据，因此不进入 Git history。

仓库保留：

- `forgeguard_openeval_rm_v0_1.npz`；
- `index.csv`；
- `metadata.jsonl`；
- `manifest.json`；
- 波形索引和转换说明。

## 4. 运行时状态

以下内容永远不应公开提交：

- `runtime-data/`；
- 浏览器 Profile / Cache / History；
- SQLite 数据库；
- PID、日志和本地分析报告；
- `.env` 和任何真实 Token/API Key。

## 5. 原始台架/工厂证据

`artifacts/bench-evidence/` 默认排除，因为真实波形可能包含未授权或专有运行数据。若未来公开物理台架结果，应另建明确的公开数据包，写清采集条件、授权、许可、hash 和适用边界。
