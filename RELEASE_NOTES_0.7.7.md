# ForgeGuard Nexus 5.0 v0.7.7

发布日期：2026-08-03

## 修复：Windows 原生环境安装窗口空白

v0.7.6 的桌面启动器在用户确认“同步持久化环境”后，直接启动 PowerShell，同时把标准输出和错误输出全部重定向到 `runtime-data/windows-launcher.log`。因此控制台窗口能够出现，但创建虚拟环境、pip 下载和模型校验过程均不可见，表现为“终端页面什么都没有”。

v0.7.7 引入独立的 Windows 控制台安装程序：

```text
ForgeGuard-Native-Setup.exe
```

该程序会：

- 分配并绑定真实 Windows 控制台；
- 实时显示 Python 环境定位、依赖同步和模型校验进度；
- 将相同输出同时写入 `runtime-data/native-installer.log`；
- 安装成功后自动关闭并继续启动 ForgeGuard；
- 安装失败时保留窗口、显示错误并等待用户按 Enter；
- 不再把安装过程仅写入不可见日志。

## 安装阶段提示

Windows 原生安装脚本现在明确显示：

```text
[1/4] 定位可复用持久环境
[2/4] 检查 Python、已安装依赖和模型兼容性
[3/4] 增量同步锁定依赖
[4/4] 校验 scikit-learn 1.8.0 与内置模型
```

## 仍保留的环境策略

- Windows 持久环境：`%LOCALAPPDATA%\ForgeGuardNexus\venv`
- Linux 持久环境：`${XDG_DATA_HOME:-~/.local/share}/forgeguard-nexus/venv`
- Python：3.11 或 3.12
- scikit-learn：1.8.0
- 环境完整时跳过 pip 安装
- 依赖实际变化时原地增量同步
- 只有环境损坏或显式 `-Recreate` / `--recreate` 才重建

## 兼容性

该版本为完整软件包，不依赖旧版或热修复包。Windows 包根目录包含：

```text
ForgeGuard-Nexus.exe
ForgeGuard-Nexus-Desktop.exe
ForgeGuard-Nexus-Stop.exe
ForgeGuard-Native-Setup.exe
```
