# ForgeGuard 原生 Python 环境持久化说明

适用版本：ForgeGuard Nexus 5.0 v0.7.9

## 1. 本次修复解决什么问题

旧版本把 `.venv` 当作项目目录的一部分。删除旧项目、解压新版本或更换目录后，虚拟环境也随之丢失，导致 NumPy、SciPy、scikit-learn 等依赖重复下载和安装。

v0.7.8 将“代码包”和“Python 运行环境”彻底分离：

- 项目目录中的 `.venv` 只是一个链接或兼容入口；
- 真正的虚拟环境保存在用户级稳定目录；
- 新解压的完整软件包会自动找到旧环境；
- 状态文件丢失时先校验已有包并自动修复，不会直接重装；
- 只有依赖版本真的变化、环境损坏或用户主动要求时才同步/重建。

## 2. 默认持久目录

Windows：

```text
%LOCALAPPDATA%\ForgeGuardNexus\venv
```

Arch Linux、Debian、Ubuntu：

```text
${XDG_DATA_HOME:-$HOME/.local/share}/forgeguard-nexus/venv
```

同时保存一个跨项目指针：

```text
Windows：%LOCALAPPDATA%\ForgeGuardNexus\venv-path.txt
Linux：${XDG_DATA_HOME:-$HOME/.local/share}/forgeguard-nexus/venv-path.txt
```

因此，即使新版本解压到完全不同的目录，启动器仍能找到原来的环境。

## 3. 为什么不再因锁文件格式变化而重装

v0.7.8 不再直接对锁文件原始字节计算指纹，而是先解析为规范化的“包名 → 精确版本”映射，再计算语义指纹。

以下变化不会触发安装：

- 注释变化；
- 空行变化；
- Windows/Linux 换行符变化；
- 依赖行顺序变化；
- 项目版本号变化；
- 项目解压路径变化。

只有实际依赖集合或版本变化才会触发增量同步。

## 4. 状态自修复

持久环境内保存：

```text
.forgeguard-env.json
```

如果该文件被删除、损坏，或由旧版本生成，v0.7.8 会执行：

```text
检查 Python 版本和平台
→ 检查所有锁定依赖的实际版本
→ 尝试加载内置 scikit-learn 1.8.0 模型
→ 校验通过后重新写入状态文件
→ 直接复用环境
```

这条路径不会执行 `pip install`。

## 5. 旧项目 `.venv` 自动迁移

首次运行 v0.7.8 时，如果发现：

- 持久目录还不存在；
- 当前项目里存在旧版真实 `.venv`；

安装器会把旧 `.venv` 迁移到持久目录，再进行校验。校验通过时不会重新下载全部依赖。

之后项目根目录会创建：

```text
.venv
```

Windows 下通常是目录联接，Linux 下通常是符号链接，指向用户级持久环境，便于 VS Code/PyCharm 自动识别。

## 6. pip 缓存也持久化

默认缓存位置：

```text
Windows：%LOCALAPPDATA%\ForgeGuardNexus\pip-cache
Linux：${XDG_DATA_HOME:-$HOME/.local/share}/forgeguard-nexus/pip-cache
```

即使未来依赖确实更新，也会优先使用本地缓存，减少重复下载。

## 7. Windows 使用

首次安装或自动检查：

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\install-native.ps1
```

启动：

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\run-native.ps1
```

强制重新核对并增量同步，但不删除环境：

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\install-native.ps1 -Force
```

只有确认环境损坏时才完全重建：

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\install-native.ps1 -Recreate
```

自定义路径：

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\install-native.ps1 -VenvDir "D:\ForgeGuardRuntime\venv"
```

该自定义路径会写入用户级 `venv-path.txt`，后续新版本无需重复设置。


## 7.1 从 EXE 自动安装时的可视进度

双击 `ForgeGuard-Nexus.exe` 后，如果没有找到可复用环境，确认安装会启动：

```text
ForgeGuard-Native-Setup.exe
```

该窗口会显示：

```text
[1/4] 定位持久环境
[2/4] 检查 Python、已安装依赖和模型兼容性
[3/4] 增量同步锁定依赖
[4/4] 校验锁定依赖与便携式 NPZ 模型
```

输出同时保存到：

```text
runtime-data\native-installer.log
```

安装成功后窗口自动关闭并继续启动软件；安装失败时窗口不会立即消失，会显示错误并等待按 Enter 关闭。


## 7.2 v0.7.7 模型校验失败的处理

若日志出现 `PCG64 is not a known BitGenerator module`，说明旧版正在用 NumPy 1.26.4 反序列化由 NumPy 2.x 保存的 joblib 模型。v0.7.8 已移除生产启动阶段的 joblib 加载。安装 v0.7.8 后，原有持久环境会被直接复用；状态文件升级后只重新校验，不重新安装全部依赖。

## 8. Linux 使用

首次安装或自动检查：

```bash
bash deploy/linux/install-native.sh
```

启动：

```bash
bash deploy/linux/run-native.sh
```

强制增量同步：

```bash
bash deploy/linux/install-native.sh --force
```

完全重建：

```bash
bash deploy/linux/install-native.sh --recreate
```

自定义路径：

```bash
FORGEGUARD_VENV_DIR=/data/forgeguard/venv \
  bash deploy/linux/install-native.sh
```

## 9. 正常复用时应看到什么

```text
ForgeGuard native environment is already current.
Reused: <持久环境路径>
Dependency installation skipped.
```

看到 `Dependency installation skipped.` 就表示没有执行依赖安装。

## 10. 如何确认当前使用的路径

Linux：

```bash
cat ~/.local/share/forgeguard-nexus/venv-path.txt
readlink -f .venv
```

Windows PowerShell：

```powershell
Get-Content "$env:LOCALAPPDATA\ForgeGuardNexus\venv-path.txt"
Get-Item .venv | Format-List FullName,LinkType,Target
```

## 11. 什么时候仍然会安装

仅在以下情况执行依赖同步：

1. 设备上从未创建过持久环境；
2. 锁定依赖的包名或版本真的改变；
3. Python 不是 3.11/3.12；
4. 环境缺包或包版本错误；
5. 内置模型无法加载；
6. 用户显式使用 `--force` / `-Force`；
7. 用户显式使用 `--recreate` / `-Recreate`。

其中只有第 7 项会删除整个虚拟环境。

## 12. 版本约束

```text
CPython 3.11 或 3.12
scikit-learn 1.8.0
```

Docker/Jetson 容器部署不使用宿主机 `.venv`，其依赖由 Docker 镜像管理。
