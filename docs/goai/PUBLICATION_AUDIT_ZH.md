# GitHub 公开发布审计

本文件记录本次 GOAI/GitHub 发布包整理时完成的检查。它只说明源码包的公开发布卫生和可运行性检查，不替代正式安全审计或生产验证。

## 已移出 Git history 的内容

- 运行时浏览器 Profile、Cache、History；
- SQLite 数据库、PID、日志、运行时分析报告；
- Windows 预编译 EXE；
- Windows/Jetson 大体积 Demo 视频；
- `artifacts/bench-evidence/` 原始证据目录；
- OpenEval-RM 的 `train_merged.csv` / `test_merged.csv` 大型展开文件；
- Ruff/Pytest/Python 缓存。

## 已保留的公开可验证内容

- FastAPI 后端、Agent workflow、工具接口和前端；
- Edge Node、Windows/Linux/Jetson 部署脚本；
- OpenEval-RM 紧凑 NPZ、索引、元数据、manifest 和转换说明；
- 选定模型、模型卡和 Benchmark 报告；
- Fault Injection 报告；
- GOAI PPT/PDF、项目简介、2 分钟 Demo 脚本和提交清单；
- Apache-2.0、NOTICE、安全/数据/第三方依赖说明。

## 隐私/凭据检查

源码文本已检查常见 API Key/Token/Password 模式；未发现真实凭据。公开包同时清理了本地绝对用户路径和“用户内部项目”式措辞。`.env`、私钥、数据库和运行时目录由 `.gitignore` 默认阻止。

## 代码验证

整理后执行：

- Python `compileall`：通过；
- Frontend `node --check frontend/app.js`：通过；
- Shell `bash -n`：通过；
- Backend + Edge pytest：**47 项通过**；
- `scripts/verify_v079.py`：核心 CSV/Edge 校验通过；大型 `train_merged.csv` 因公共仓库主动排除而按设计跳过。

验证容器使用 Python 3.13.5；项目正式声明的生产运行范围仍是 Python 3.11/3.12，Docker 使用 Python 3.11。

## 发布前还需要人工完成

1. 创建 GitHub 仓库并 push；
2. 首次 GitHub Actions CI 通过后再把 CI 状态截图/链接放入比赛材料；
3. 将 Hero Demo、完整 Windows/Jetson Demo 和预编译 EXE 放 GitHub Release 或稳定视频平台；
4. 把最终仓库 URL 和 Demo URL 写入 PPT/提交表；
5. 从无登录浏览器验证所有公开链接可访问。
