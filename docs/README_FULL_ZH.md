# ForgeGuard Nexus 5.0

**版本：0.7.9**  

> **0.7.9 Windows 与 CSV 修正版**：Windows 原生安装现在会在 `py`、PATH、官方 Python 目录、PythonCore 注册表和 Conda 环境中查找 CPython，并优先使用 Python 3.12。PowerShell、Python 子进程、中文路径指针和安装控制台统一使用 UTF-8。CSV 上传限制调整为 128 MB、100 万数据行和 256 列；新增明确的编码、分隔符、字段及 OpenEval/XJTU/边缘回放限制，并修复边缘回放把时间戳混入振动信号的问题。

> **0.7.8 完整软件包**：修复 Windows 原生环境在模型校验阶段报 `PCG64 is not a known BitGenerator module` 的问题。生产启动不再反序列化 joblib/pickle，而是加载仅包含数值数组的便携式 NPZ 模型；已有 `%LOCALAPPDATA%\ForgeGuardNexus\venv` 可直接复用，不需要重新下载依赖。

> **模型运行时要求**：Docker 后端使用 Python 3.11；Windows/Linux 原生模式使用 Python 3.11 或 3.12。锁定环境仍包含 `scikit-learn==1.8.0` 用于基准评测和模型重训，但生产推理读取 `selected_vibration_model.portable.npz`，不会受训练时 NumPy 随机数对象的 pickle 兼容性影响。
>
> **0.7.2 智能体交互修复**：AI 智能体页面由静态状态看板升级为可操作工作台。可选择智能体、查看职责/输入输出/执行记录/工具权限，点击流程阶段、工具和模型，并跳转关联事件或询问 Copilot。
**定位：面向旋转机械与关键工业资产的跨平台边缘工业智能体平台**

ForgeGuard Nexus 将实时采集、历史 CSV、数据质量、故障识别、剩余寿命、人员安全、生产计划、库存、能耗、维修决策、人工审批、工单和维修后复测连接成一条可审计闭环。

它不是普通聊天机器人，也不是只显示“正常/故障”的分类网页。它的核心目标是：让工业异常从“被模型发现”继续走到“被人安全处置，并由维修后数据证明已经恢复”。

---

## AI 智能体页面如何操作

旧版智能体卡片只负责展示运行状态，因此点击没有任何反馈。0.7.8 完整包内已集成为可交互工作台：

1. 点击流程阶段或智能体卡片，右侧显示该智能体的职责和边界；
2. “执行记录”读取真实事件 trace 与 tool_calls，可点击跳转到关联事件；
3. “工具权限”解释只读、高风险和人工审批边界；
4. 工具与模型目录可以展开；
5. “询问此智能体”会带入当前智能体上下文；
6. 单个专业智能体不能脱离协调器直接运行生产动作，这是治理约束，不是功能缺失。


## 1. 软件到底能做什么

平台提供三种工作方式，它们用途不同，但使用同一套质量门控和分析基础。

### 1.1 实时检测

用于 Jetson、工业 PC、采集卡、串口设备或 HTTP 网关持续上传数据。平台边接收边分析，显示：

- 实时波形；
- 数据可信度；
- 故障判断与置信度；
- 异常概率；
- 最近数据帧；
- 自动告警状态。

### 1.2 CSV 文件分析

用于历史数据、公开数据集、台架导出数据、示波器或采集卡文件。平台会：

- 自动识别数值信号列；
- 按窗口切分；
- 对每个窗口执行质量检查与推理；
- 汇总主导故障、异常概率和拒识结果；
- 可选创建告警；
- 保存 JSON 分析报告。

### 1.3 工业场景库

用于演示和验证完整 Agent 闭环。0.7.8 内置 25 个场景，覆盖：

- 轴承与旋转机械；
- 齿轮箱与传动；
- 泵、风机和流体设备；
- 电机与电气；
- 能源与环境；
- 数据质量与治理；
- 生产与供应韧性。

场景库是**软件演示数据**，不能当作真实工厂实验结果。真实检测应进入“实时检测”或“CSV 文件分析”。

---

## 2. 一条完整业务闭环

```text
实时数据或 CSV
→ 数据质量检查
→ 异常识别与故障诊断
→ 健康度和 RUL 区间
→ 人员安全评估
→ 能源、碳和废弃物评估
→ 生产、库存、人员和供应约束查询
→ 多个维修方案比较
→ 授权人员审批
→ 创建并执行工单
→ 维修后重新采集
→ 验证恢复或自动重开事件
→ 审计与知识沉淀
```

系统不会因为模型给出了一个类别，就自动控制生产设备。高风险动作必须由授权人员批准；维修完成也不等于事件关闭，必须通过维修后复测。

---

## 3. 当前已经实现的功能

### 数据与边缘接入

- 实时检测会话创建、停止和状态查询；
- 内置连续信号演示；
- HTTP 实时帧接口；
- 串口连续采集客户端；
- CSV 准实时回放；
- CSV 单列、多列、有表头、无表头分析；
- UTF-8、GB18030、UTF-16；
- 逗号、分号、Tab 和竖线分隔；
- 最大 128 MiB、100 万数据行、256 列、单字段 1 MiB；
- 边缘断网缓存和证据保存接口。

### 分析与模型

- 信号削波、掉点、直流偏置、有效位数等质量门控；
- 可解释时域、频域和包络特征；
- 校准的 HGB 振动基线；
- ONNX Runtime 接口；
- Jetson TensorRT Engine 接口与 GPU 冒烟测试；
- 透明 CPU 回退；
- RUL 区间、健康度、恶化趋势和继续运行风险。

### Agents 与业务闭环

- 数据质量智能体；
- 感知智能体；
- 工业知识智能体；
- 故障诊断智能体；
- 寿命与风险智能体；
- 人员安全智能体；
- 能耗与环境智能体；
- 系统韧性智能体；
- 维修规划智能体；
- 审批治理智能体；
- 工单智能体；
- 维修后验证智能体；
- 协调智能体。

### 工业业务模块

- 资产健康；
- 告警事件；
- 多目标维修决策；
- 库存；
- 生产订单；
- 技术人员与技能；
- 工单执行；
- 能耗和环境影响；
- 边缘节点；
- 审计记录；
- 模型与工具注册；
- 工业 Copilot 接口。

### 前端操作

- 全局搜索；
- 最近工业事件“全部”入口；
- 常用功能快捷中心；
- 25 场景工业场景库；
- 桌面和移动响应式；
- JSON 运行摘要导出；
- 普通语言帮助与术语解释。

---

## 4. 界面使用说明

### 4.1 运行总览

用于了解整个系统状态：资产、健康设备、当前告警、工单、韧性、节能、边缘节点和 Agent 状态。

首屏“常用功能”可以直接进入：

- 实时检测；
- CSV 文件分析；
- 工业场景库；
- 告警事件中心；
- 维修决策竞技场；
- 导出运行摘要。

### 4.2 顶部全局搜索

点击右上角搜索框，或按：

```text
Ctrl + K
```

可搜索：

- 页面功能；
- 设备名称和编号；
- 告警内容和编号；
- 工单标题和编号；
- 实时检测与 CSV 分析帮助；
- 25 个工业场景。

键盘操作：

```text
↑ / ↓    切换结果
Enter    打开
Esc      关闭
```

0.7.8 保留顶层搜索层，并修复事件总览与专用页面导航，并给脚本与样式增加版本号缓存刷新，修复“看得到但点击没有反应”的问题。

### 4.3 最近工业事件的“全部”

运行总览右侧“最近工业事件”中的“全部”会进入完整的“告警事件”页面。若当前没有事件，会显示空状态，而不是点击无反应。

### 4.4 数据检测与分析

该页面有两个主模式。

#### 实时检测

1. 选择设备；
2. 选择“内置实时演示”或“外部传感器/网关”；
3. 设置采样率、转速和负载；
4. 点击“开始实时检测”；
5. 查看连续波形、质量、类别、置信度和异常概率；
6. 异常时可自动创建告警；
7. 点击“停止检测”。

外部实时帧接口：

```text
POST /api/v1/analysis/live/sessions/{session_id}/frames
```

请求示例：

```json
{
  "samples": [0.012, 0.018, -0.006, 0.021],
  "rpm": 1800,
  "load_percent": 70,
  "temperature_c": 42.5,
  "metadata": {
    "sensor": "drive-end radial",
    "unit": "g"
  }
}
```

`samples` 至少包含 64 个有限数值，实际使用建议每帧 2048 或 4096 点。

串口实时采集：

```bash
PYTHONPATH=edge-node python -m forgeguard_edge.cli stream-live-serial \
  --port /dev/ttyUSB0 \
  --server http://127.0.0.1:8000 \
  --asset-id FG-BRG-001 \
  --sample-rate 12000 \
  --window-size 2048 \
  --open-incident
```

CSV 准实时回放：

```bash
PYTHONPATH=edge-node python -m forgeguard_edge.cli stream-live-csv vibration.csv \
  --server http://127.0.0.1:8000 \
  --asset-id FG-BRG-001 \
  --sample-rate 12000 \
  --window-size 2048 \
  --hop-size 1024 \
  --interval 0.5 \
  --open-incident
```

#### CSV 文件分析

适用于历史振动、公开数据集、台架或现场离线采样。

推荐格式：

```csv
timestamp,acceleration_x
0.000000,0.0132
0.000083,0.0151
0.000167,-0.0067
```

操作：

1. 选择 CSV；
2. 选择设备；
3. 填写真实采样率、转速和负载；
4. 多列文件可填写信号列名或列号；留空时自动识别；
5. 设置窗口长度和步长；
6. 点击“开始分析”；
7. 查看有效窗口、质量统计、主导类别、异常概率与告警编号。

报告保存位置：

```text
runtime-data/analysis-reports/
```

### 4.5 工业场景库

导航栏进入“工业场景库”。可以按名称、设备、模态或业务约束搜索，并按类别筛选。

当前场景包括：

```text
轴承外圈剥落、轴承内圈故障、滚动体故障、润滑失效、轴系不对中、
转子不平衡、机械松动、轴弯曲、结构共振、齿轮齿面损伤、皮带打滑、
泵汽蚀、密封泄漏、风机叶片积灰、电机轴承过热、三相电流不平衡、
能源漂移、冷却效率下降、压缩空气泄漏、跨模态证据冲突、
传感器安装异常、采样丢包、备件供应受限、维修人员不足、生产负荷过载。
```

选择场景后点击“运行场景”，系统会执行完整 Agent 决策链。场景结果只用于软件演示与比赛流程验证。

### 4.6 告警事件

用于查看一次异常的完整证据：数据质量、故障判断、替代解释、RUL、安全限制、能耗影响和 Agent 轨迹。

### 4.7 维修决策

并列比较方案，不只比较成本，还比较：

- 人员安全；
- 生产韧性；
- 环境与能耗；
- 停机时间；
- 维修成本；
- 备件和人员可用性。

### 4.8 工单执行

只有授权人员审批后才创建工单。维修完成后必须运行维修后验证；未通过则自动重开事件。

---

## 5. Windows 桌面软件

完整 Windows 包根目录提供：

```text
ForgeGuard-Nexus.exe
ForgeGuard-Nexus-Desktop.exe
ForgeGuard-Nexus-Stop.exe
```

### 默认启动行为

双击 `ForgeGuard-Nexus.exe` 或 `ForgeGuard-Nexus-Desktop.exe` 后：

1. 启动 Docker Compose 或已安装的本地 Python 服务；
2. 等待后端健康检查通过；
3. 使用 Microsoft Edge 或 Google Chrome 的 **App Mode** 打开独立窗口；
4. 窗口没有地址栏和普通浏览器标签页，使用体验接近桌面软件；
5. 使用独立配置目录，不污染日常浏览器会话。

它不是把整个 Python、模型、数据库和浏览器内核压缩进单文件的伪绿色版。当前桌面窗口依赖系统已安装的 Edge 或 Chrome；Windows 10/11 通常自带 Edge。

需要普通浏览器模式时，在命令行运行：

```powershell
.\ForgeGuard-Nexus.exe web
```

停止服务：

```text
ForgeGuard-Nexus-Stop.exe
```

日志：

```text
runtime-data\windows-launcher.log
```

Windows 使用时必须保留完整项目目录，不能把 EXE 单独拖走。

---

## 6. 快速启动

### Windows 10/11

推荐：

1. 解压 Windows 完整包；
2. 启动 Docker Desktop；
3. 双击 `ForgeGuard-Nexus.exe`；
4. 关闭软件窗口后，需要彻底停止服务时双击 `ForgeGuard-Nexus-Stop.exe`。

没有 Docker Desktop 时，可执行：

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\install-native.ps1
```

### Arch Linux / Debian / Ubuntu

Docker：

```bash
bash start.sh
```

停止：

```bash
bash stop.sh
```

原生 Python：

```bash
bash deploy/linux/install-native.sh
bash deploy/linux/run-native.sh
```

#### 原生虚拟环境持久化

从 0.7.8 起，`.venv` 不再以项目解压目录作为唯一存储位置。环境默认保存在用户目录，因此删除旧代码文件夹、解压新版本或更换项目目录时，不会重复下载未变化的依赖。

```text
Windows：%LOCALAPPDATA%\ForgeGuardNexus\venv
Linux / Arch / Debian：${XDG_DATA_HOME:-~/.local/share}/forgeguard-nexus/venv
```

环境管理器会把两个锁文件解析成规范化的“包名 → 精确版本”映射，再计算语义指纹：

- 项目路径、软件版本、注释、空行、换行符和依赖行顺序变化：直接复用；
- `.forgeguard-env.json` 丢失或来自旧版：先检查已有依赖并加载模型，校验通过后自动补写状态，不运行 `pip install`；
- 实际包版本变化：在原环境中增量同步，不删除整个环境；
- 只有 Python 不兼容、环境损坏或显式 `--recreate` / `-Recreate` 才重建；
- 项目根目录的 `.venv` 是指向持久环境的符号链接/目录联接，供 IDE 识别。

持久环境路径还会记录在用户级 `venv-path.txt` 中，因此重新解压到其他目录也能自动找到。pip 缓存同样保存在用户目录，真实依赖升级时可减少重复下载。

Windows 从 EXE 自动安装时会打开独立进度窗口，显示 `[1/4]` 至 `[4/4]` 阶段、pip 下载内容和模型校验。旧版空白终端是因为启动器把 PowerShell 输出仅重定向到日志；v0.7.8 已改为窗口与 `runtime-data\native-installer.log` 同时输出。

强制同步而不删除环境：

```bash
bash deploy/linux/install-native.sh --force
```

彻底重建：

```bash
bash deploy/linux/install-native.sh --recreate
```

自定义路径：

```bash
FORGEGUARD_VENV_DIR=/data/forgeguard-venv bash deploy/linux/install-native.sh
```

Windows 对应参数为 `-Force`、`-Recreate` 和 `-VenvDir`。

### Jetson AGX Orin

推荐环境：JetPack 6.2.x、L4T R36.5、CUDA 12.6、TensorRT 10.3。

```bash
bash deploy/jetson-5/preflight.sh
bash deploy/jetson-5/optimize.sh
bash deploy/jetson-5/run.sh
```

GPU 冒烟验证：

```bash
bash deploy/jetson-5/gpu-smoke.sh
```

该测试证明 TensorRT 环境可构建并执行 Engine，不代表默认 HGB 故障模型已经在 GPU 上运行。

### 访问地址

```text
http://localhost:8000
```

API 文档：

```text
http://localhost:8000/docs
```

---

## 7. 中国大陆网络

Python 包镜像：

```bash
export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
bash start.sh
```

Docker Hub 代理必须配置给 Docker daemon 或 Docker Desktop。浏览器能够访问外网，不代表 Docker 后台能够访问。

---

## 8. 数据、模型和声明边界

必须区分五类证据：

1. 软件模拟数据；
2. 公开数据集；
3. 历史现场数据；
4. 真实台架数据；
5. 真实现场连续数据。

当前默认包含：

- 可复现的 HGB 振动基线；
- OpenEval-RM 演示/评测数据；
- ONNX/TensorRT 运行时接口；
- Jetson 原生 TensorRT 验证脚本。

不得声称：

- 场景库等同真实工厂实验；
- TensorRT 环境验证等同神经故障模型已经部署；
- RUL 是寿命保证；
- 系统已经通过工厂安全认证；
- 平台可绕过人工授权直接控制 PLC、机器人或产线。

---

## 9. 目录结构

```text
backend/                 API、数据库、Agents、模型、工单和分析服务
edge-node/               现场数据采集、回放、缓存和上传程序
frontend/                工业控制台
models/                  ONNX / TensorRT 模型目录
data/                    公开或本地数据
runtime-data/            SQLite、CSV 报告、缓存和日志
artifacts/               证据包、截图和评测结果
deploy/                  Windows、Linux、Jetson 部署脚本
dist/windows/            Windows EXE 启动器
windows-launcher/        Windows 启动器源码
```

---

## 10. 环境与部署文档

- 原生 `.venv` 持久化：`docs/NATIVE_ENVIRONMENT_ZH.md`
- 跨平台部署：`docs/DEPLOYMENT_ZH.md`
- Windows 桌面版：`docs/WINDOWS_EXE_ZH.md`
- 模型与数据边界：`docs/MODEL_AND_DATA_BOUNDARIES.md`

## 11. 开发与测试

```bash
PYTHONPATH=backend pytest -q backend/tests
PYTHONPATH=edge-node pytest -q edge-node/tests
python3 -m compileall -q backend/app edge-node/forgeguard_edge
node --check frontend/app.js
docker compose -f compose.yaml config
```

---

## 12. 常见问题

### 搜索框仍然点击无反应

确认使用的是 0.7.8，并强制刷新旧缓存：

```text
Ctrl + Shift + R
```

0.7.8 的 HTML 使用 `/ui/app.js?v=0.7.8` 和 `/ui/styles.css?v=0.7.8`，避免浏览器继续使用旧脚本。

### “最近工业事件”的“全部”没有内容

按钮应进入“告警事件”。若尚未运行场景或实时检测没有创建告警，页面会显示“暂无事件”。

### CSV 报列不存在

填写准确表头，或填写从 0 开始的列序号。留空时系统自动选择数值覆盖率最高的一列。

### 实时检测没有波形

- 内置演示：确认任务为“运行中”；
- 外部设备：确认持续向 `/frames` POST；
- 检查采样率和每帧样本数量；
- 检查数据质量门控是否拒绝了输入。

### 为什么升级后不再重新安装 `.venv`

0.7.8 将原生运行环境和环境指针都移到用户级目录。启动器会先读取用户级 `venv-path.txt`，再使用 `status --repair` 检查现有环境。即使重新解压项目或状态文件丢失，只要已安装包版本正确，就会自动修复状态并直接复用，不执行 `pip install`。

查看当前环境路径：

```text
项目根目录 .venv-path.txt
```

Linux 默认位置：

```text
~/.local/share/forgeguard-nexus/venv
```

Windows 默认位置：

```text
%LOCALAPPDATA%\ForgeGuardNexus\venv
```

### Windows 为什么仍依赖 Edge/Chrome

当前 EXE 已经打开无地址栏、无标签页的独立软件窗口，但显示引擎使用系统 Edge/Chrome App Mode。这样比捆绑一套额外浏览器内核更轻、更易维护，也能保持跨平台前端一致。后续若需要企业 MSI 和内嵌 WebView2，可在 Windows CI 中单独发布签名安装器。

### Jetson 空间不足

```bash
df -h /
sudo docker system df
sudo docker container prune -f
sudo docker image prune -a -f
```

只清理未使用镜像，不要删除当前项目和需要保留的数据。

---

## 13. 安全原则

- 不直接控制生产设备；
- 高风险动作必须由授权人员批准；
- 数据质量不足时拒绝确定性结论；
- 维修完成后必须复测；
- 模型、证据、审批和工具调用可追踪；
- 现场部署前仍需企业 EHS、网络安全和设备安全验收。

## 14. 许可证

ForgeGuard 源码使用 Apache-2.0。第三方模型和数据集保持各自许可证。发布前检查：

- `NOTICE.md`
- `docs/SOFTWARE_BOM.md`
- `docs/MODEL_AND_DATA_BOUNDARIES.md`
