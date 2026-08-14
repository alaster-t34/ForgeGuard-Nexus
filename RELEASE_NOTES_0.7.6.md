# ForgeGuard Nexus 5.0 v0.7.6

## 修复重点

本版本针对“每次更换或重新解压项目后 `.venv` 都要重新安装”的问题重构原生环境管理。

## 关键改动

1. 持久环境固定保存在用户目录，不再依附项目文件夹。
2. 新增用户级 `venv-path.txt`，新解压的软件包可自动找到旧环境。
3. 依赖指纹改为语义指纹，忽略注释、空行、行顺序和换行符差异。
4. 状态文件缺失或旧版 schema 时，先验证已有环境并自动补写，不直接运行 pip。
5. 首次升级可迁移项目内旧 `.venv` 到持久目录。
6. 项目根目录自动建立 `.venv` 联接/符号链接，IDE 仍可正常识别。
7. pip 缓存迁移到持久目录，减少未来真实依赖更新时的重复下载。
8. Windows EXE、PowerShell、Linux 启动脚本统一使用同一环境发现逻辑。

## 默认路径

```text
Windows：%LOCALAPPDATA%\ForgeGuardNexus\venv
Linux：${XDG_DATA_HOME:-$HOME/.local/share}/forgeguard-nexus/venv
```

## 不会触发安装的变化

- 软件版本升级但依赖不变；
- 项目目录更换；
- ZIP 重新解压；
- 锁文件注释、空行、顺序或换行符变化；
- `.forgeguard-env.json` 丢失但已安装包仍正确。

## 仍会触发同步的情况

- 实际依赖版本变化；
- 环境缺包或损坏；
- Python 版本不兼容；
- 用户主动使用 `--force` / `-Force`。

只有 `--recreate` / `-Recreate` 会删除并重建整个环境。
