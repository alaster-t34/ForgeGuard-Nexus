# GitHub 发布步骤

这个 ZIP 已经按“源码仓库”而不是“完整离线安装包”整理：大视频、运行时浏览器 Profile、数据库、日志、预编译 EXE 和超过 GitHub 单文件限制的大 CSV 不放入 Git history。

## 1. 创建空仓库

GitHub 上创建：

```text
ForgeGuard-Nexus
```

建议：

- Public；
- 不在网页端自动生成 README/License/.gitignore，避免第一次 push 冲突；
- Description 可用：`Evidence-driven industrial maintenance agents with human-governed execution and post-maintenance verification.`

## 2. 本地初始化

在解压后的仓库目录执行：

```bash
git init
git add .
git status
git commit -m "chore: publish ForgeGuard Nexus v0.7.9 GOAI edition"
git branch -M main
git remote add origin <YOUR_REPOSITORY_URL>
git push -u origin main
```

## 3. 发布前必须看一次 `git status`

确认没有出现：

```text
.env
runtime-data/
*.db
*.log
*.mp4
*.exe
train_merged.csv
test_merged.csv
browser profile / cache
```

## 4. 推荐 GitHub Release

建立 tag：

```text
v0.7.9-goai
```

Release 中放：

- Windows 完整包或 Windows 启动器二进制；
- Windows 完整 Demo 视频；
- Jetson Demo 视频；
- 需要提供给评委的离线交付包；
- 对应 SHA-256。

不要把这些大文件提交到 Git history。

## 5. 仓库首页最后检查

公开后从无登录/隐身窗口打开仓库，检查：

1. README 第一屏是否直接说明工业问题和闭环；
2. Quick Start 是否能复制；
3. `docs/goai/` 是否能快速找到；
4. PDF 是否能正常预览；
5. License 和安全边界是否清楚；
6. CI 是否通过；
7. Release/Demo 链接是否可访问。
