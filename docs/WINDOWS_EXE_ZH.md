# Windows 桌面版使用说明

## 1. 包含的文件

完整 Windows 包根目录提供：

```text
ForgeGuard-Nexus.exe
ForgeGuard-Nexus-Desktop.exe
ForgeGuard-Nexus-Stop.exe
ForgeGuard-Native-Setup.exe
```

前三个文件为 Windows x64 PE32+ 图形程序。`ForgeGuard-Native-Setup.exe` 是控制台安装程序，用于在没有可复用原生环境时显示真实安装进度。启动器源码位于 `windows-launcher/`，构建副本位于 `dist/windows/`。

## 2. 现在为什么看起来是“软件”而不是普通网页

0.7.8 默认不再调用系统默认浏览器打开普通标签页。

启动器会找到 Microsoft Edge 或 Google Chrome，并使用 App Mode 打开：

```text
--app=http://127.0.0.1:8000/?desktop=1
```

该模式具有以下特征：

- 独立窗口；
- 无地址栏；
- 无普通浏览器标签页；
- 最大化启动；
- 独立用户数据目录；
- 与日常浏览器历史和标签分离。

因此用户看到的是桌面软件窗口，而不是一个普通浏览器页面。

## 3. 它是否是完全内嵌浏览器内核的单文件 EXE

不是。

ForgeGuard 包含 Python 科学计算、数据库、模型、前端和跨平台服务。当前 EXE 负责：

1. 查找完整项目；
2. 启动 Docker Compose 或本地 Python；
3. 等待 `/api/v1/health` 通过；
4. 打开独立桌面窗口；
5. 记录运行日志。

显示引擎使用系统 Edge 或 Chrome。Windows 10/11 通常自带 Edge。这样能避免在发布包中再捆绑一套体积较大的浏览器内核，同时保持 Windows、Linux 和 Jetson 前端一致。

## 4. 使用步骤

1. 解压完整 Windows ZIP；
2. 不要把 EXE 单独复制到其他目录；
3. 推荐先启动 Docker Desktop；
4. 双击 `ForgeGuard-Nexus.exe`；
5. 等待服务完成构建和健康检查；
6. ForgeGuard 独立窗口自动打开。

若不使用 Docker，可先执行：

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\install-native.ps1
```

之后再次双击 EXE。

原生环境默认保存在：

```text
%LOCALAPPDATA%\ForgeGuardNexus\venv
```

它不随项目解压目录删除。升级新版本时，只要依赖锁没有变化，EXE 会直接复用，不会再次安装全部包。项目根目录会生成 `.venv-path.txt` 记录实际路径。

## 5. 普通浏览器模式

仅在调试或需要浏览器开发工具时使用：

```powershell
.\ForgeGuard-Nexus.exe web
```

## 6. 停止软件

关闭桌面窗口只关闭界面，不一定停止后台容器。

彻底停止服务：

```text
ForgeGuard-Nexus-Stop.exe
```

## 7. 启动顺序

启动器按以下顺序执行：

1. 若服务已运行，直接打开桌面窗口；
2. 检测到 Docker，则运行 `docker compose up -d --build api`；
3. 无 Docker 时，优先检查 `%LOCALAPPDATA%\ForgeGuardNexus\venv` 持久化环境；
4. 环境不存在或依赖版本已变化时，询问是否打开安装进度窗口；
5. `ForgeGuard-Native-Setup.exe` 显示环境创建、pip 下载、版本校验和便携式模型校验进度；
6. 安装成功后自动继续启动，失败时保留窗口并显示错误；
7. 最多等待 4 分钟健康检查；
6. 打开独立 App 窗口；
7. 未找到 Edge/Chrome 时才回退到默认浏览器，并给出提示。

## 8. 日志和排障

日志：

```text
runtime-data\windows-launcher.log
runtime-data\native-installer.log
```

### 为什么旧版点击“是”后只看到空白终端

旧版启动器启动 PowerShell 后，把标准输出和错误输出全部重定向到 `windows-launcher.log`，因此控制台虽然出现，安装过程却不可见。v0.7.8 改为独立控制台安装程序，并将输出同时写到窗口和 `native-installer.log`。首次安装期间应能看到 `[1/4]` 到 `[4/4]` 的阶段提示、pip 下载进度和最终校验结果。

常见问题：

- **提示找不到 compose.yaml**：EXE 被单独移动，放回完整项目根目录；
- **Docker 启动失败**：先打开 Docker Desktop，检查代理和磁盘空间；
- **安装窗口没有进度**：确认完整包根目录存在 `ForgeGuard-Native-Setup.exe`，并查看 `runtime-data\native-installer.log`；
- **窗口未出现**：检查 Edge/Chrome 是否存在，查看日志；
- **仍显示旧界面**：关闭软件窗口，删除 `runtime-data\desktop-profile` 后重新启动；
- **搜索仍无反应**：确认使用 0.7.8，执行 `Ctrl+Shift+R` 强制刷新缓存。

## 9. 当前验证边界

- EXE 已交叉编译并验证为 Windows x64 PE 文件；
- 启动逻辑和命令参数已静态检查；
- 当前构建环境不是 Windows，仍需在真实 Windows 10/11 x64 主机完成最终双击、Docker、App Mode 和停止流程验收；
- 当前不是签名 MSI 安装包，也没有声称通过 Windows SmartScreen 信誉认证。

## 8. 模型依赖要求

原生 Windows 模式必须使用 Python 3.11 或 3.12，并安装 `scikit-learn==1.8.0`。基准评测与重训固定使用 scikit-learn 1.8.0；生产推理使用便携式 NPZ 模型，不加载 joblib。0.7.8 的持久化环境会对锁文件生成指纹，只有依赖变化或环境损坏时才同步。推荐使用 Docker Desktop，Dockerfile已锁定 Python 3.11 和正确依赖。
