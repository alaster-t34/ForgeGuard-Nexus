# GOAI 初赛提交检查清单

## 作品简介

- [ ] 使用 `docs/goai/submission/project-intro-500zh.txt` 作为基础版本。
- [ ] 再次确认提交平台按“字”还是“字符”计数，预留余量。
- [ ] 明确目标用户、工业痛点、完整闭环、创新点和开放复用价值。
- [ ] 不把合成 Benchmark 描述成真实工厂准确率。

## PPT / PDF

- [ ] 首页一句话能说明“从异常到受治理维修行动闭环”。
- [ ] 2-3 页内说明为什么单纯故障分类无法完成现场任务。
- [ ] 用一张图展示 Evidence → Diagnosis → Decision → Governance → Verification。
- [ ] 13 Agent 作为架构细节，不作为主卖点。
- [ ] 明确库存、生产、人员、FMEA、工单等 Tool Call。
- [ ] 放入当前 Benchmark 和 Fault Injection 证据，同时写清实验边界。
- [ ] 明确“不直接控制真实生产设备，高风险动作必须人工确认”。
- [ ] 提供 GitHub 仓库入口和 Demo 视频入口。

## Demo

- [ ] 90-150 秒 Hero Demo 已录制。
- [ ] 主路径包含输入、质量门、诊断/RUL、工具调用、方案比较、人工审批、工单和维修后验证。
- [ ] 至少演示一次削波/掉点/冲突证据等失败分支。
- [ ] 视频中的项目版本、PPT 和 GitHub README 一致。
- [ ] 视频中没有个人账号、API Key、浏览器 Cookie、企业敏感信息。

## GitHub

- [ ] 仓库名称建议 `ForgeGuard-Nexus`。
- [ ] 根目录 README 能在 60 秒内解释项目价值和验证路径。
- [ ] `LICENSE`、`NOTICE.md`、`SECURITY.md` 已存在。
- [ ] `.env`、数据库、日志、浏览器 Profile、原始企业数据未提交。
- [ ] 大视频和 Windows EXE 不进 Git history，改放 GitHub Releases/视频平台。
- [ ] `train_merged.csv` / `test_merged.csv` 不进 Git history。
- [ ] GitHub Actions 配置存在，并在公开前确认首轮 CI 状态。
- [ ] Release tag 建议 `v0.7.9-goai`。

## 最终一致性

- [ ] 作品简介、PPT、视频、README、版本号与 Benchmark 数字一致。
- [ ] 所有第三方模型/数据/平台均有来源和许可边界说明。
- [ ] 已有项目基础与本次新增贡献的边界能够解释。
- [ ] Demo 能从零开始复现，或至少有明确运行入口、依赖和示例数据。
- [ ] 提交后保存平台回执、最终 PDF、视频文件 hash 和 Git commit hash。
