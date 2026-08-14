# ForgeGuard Nexus 5.0 - GOAI 无界应用初赛说明

## 1. 参赛定位

- 赛道：无界应用 Boundless Agents
- 行业方向：AI + 工业制造
- 细分场景：旋转机械与关键工业资产的设备运维、维修决策和工单闭环
- 目标用户：设备工程师、可靠性工程师、维修主管、生产计划人员和授权安全审批人员

## 2. 核心问题

工业预测性维护常停留在“模型检测到异常”或“输出一个故障类别”。真正进入现场后，维修决策还必须同时处理：数据是否可信、故障严重度和剩余风险窗口、备件是否可用、生产是否允许停机、是否有合格人员、什么方案可被授权、维修完成后是否真的恢复。

ForgeGuard 的目标不是再做一个工业聊天机器人或单点分类器，而是把这些跨系统约束组织成可运行、可追溯、可验证的 Agent 任务闭环。

## 3. 一条可演示闭环

```text
设备信号 / CSV / Edge 输入
→ 数据质量门控与证据封装
→ 故障诊断
→ 健康度、RUL 与继续运行风险
→ FMEA / 库存 / 生产 / 人员工具调用
→ 多个维修方案比较
→ 授权人员人工审批
→ 创建和执行工单
→ 维修后重新采集数据
→ Verification Agent 比较前后证据
→ 通过则关闭；失败则重开事件
```

### 必演失败分支

输入削波、掉点、强干扰或证据冲突场景。系统应：

1. 标记数据质量下降或证据冲突；
2. 阻止确定性高风险维修结论；
3. 请求重新采集或人工复核；
4. 保留失败工具调用、状态转移和审计证据。

## 4. 为什么需要 Agent

ForgeGuard 把确定性安全不变量与 Agent 推理分开：

- Agent 负责理解上下文、识别证据缺口、调用受控工具、组织多源结果和形成候选行动；
- 状态机与治理层负责不可绕过的业务约束，例如审批、幂等、工具权限、验证闭环和失败处理；
- LLM 仅作为可选的语言理解/解释层，不拥有设备控制权限，核心闭环不依赖商业 LLM 或 API Key。

这使系统同时具备 Agent 的动态任务能力和工业流程需要的确定性治理。

## 5. 技术架构

```text
Sensors / CSV / Cameras / Enterprise APIs
                 │
        Hardware-neutral Edge Node
                 │ typed observations
                 ▼
          Evidence & Tool Gateway
 asset · FMEA · inventory · MES · workforce
                 │ audited calls
                 ▼
┌─────────────────────────────────────────────┐
│ Agent workflow                              │
│ data quality → perception → diagnosis       │
│ → reliability/RUL → safety/resilience       │
│ → maintenance planner → human governance    │
│ → work order → post-maintenance verification│
└─────────────────────────────────────────────┘
                 │
            Web UI + API + audit
```

当前实现包括 FastAPI 后端、依赖轻量的 Web 控制台、硬件无关 Edge Node、知识库、模型/工具注册、工业场景库、Docker 和 Windows/Linux/Jetson 部署路径。

## 6. 可验证工程证据

### 模型基准

`artifacts/benchmarks/latest.json` 基于项目自生成的 OpenEval-RM 0.1.0 合成回归数据。当前部署模型 `dsp-calibrated-hgb-v0.2`：

- Macro-F1：0.9342
- Balanced Accuracy：0.9375
- CPU p95 推理延迟：13.912 ms
- Abstention 后 Accepted Accuracy：0.9872
- Robustness mean Macro-F1：0.7166

这些结果只用于可复现实验、模型选择和鲁棒性工程，不宣称真实工厂准确率。

### 故障注入

`artifacts/fault-campaigns/latest.md` 提供可复现的信号/软件故障注入：

- clean injected-fault classification accuracy：1.000
- corrupted-signal safe-response rate：1.000
- workflow-fault containment rate：1.000

该实验用于证明异常输入和工具故障下的安全行为与回归稳定性，不替代物理台架或工厂安全验证。

## 7. 数据来源和合规边界

- OpenEval-RM：项目生成的物理规律驱动合成数据，Apache-2.0，可公开复现。
- CWRU、Paderborn、XJTU-SY 等外部数据：只提供适配/登记，不在仓库中二次分发，需从官方来源获取并遵守原始许可。
- 真实工厂/台架数据：默认不进入 Git；公开前必须确认授权、脱敏、用途和保留策略。
- 工业安全：系统只做决策支持，不直接控制真实生产设备；高风险动作由授权人员确认，并遵循企业安全流程。
- 低质量/冲突证据：进入拒识、重新采集或人工复核，而不是强行输出确定性结论。

## 8. 开放与复用

- Apache-2.0 核心代码；
- 模型、工具、Edge 接口采用适配器/契约方式；
- 提供 Docker、原生和 Jetson 路线；
- 提供测试、Benchmark、Fault Injection、QA、数据边界和第三方依赖说明；
- 真实商业系统可通过受控工具接口替换当前模拟/本地业务数据源。

## 9. 当前边界与后续迭代

当前项目已经具备完整 Demo 与工程闭环，但仍需区分“软件可运行”和“真实工厂有效性”。后续重点是：

1. 公开真实数据集上的跨域验证；
2. 物理台架上的传感器、安装方式、转速/负载和故障样件披露；
3. 真实 CMMS/MES/库存系统的授权适配；
4. 更系统的 Agent 任务成功率、失败恢复率和人机协同时间评估；
5. Jetson 实机性能、断网恢复和长期稳定性测试。

## 10. 评委最短验证路径

1. `docker compose -f compose.yaml up -d --build api`
2. 打开 `http://localhost:8000`
3. 运行“轴承外圈故障”工业场景
4. 查看事件 Evidence、Agent Trace 与 Tool Calls
5. 进入维修决策，比较方案并进行人工审批
6. 创建/执行工单
7. 回放维修后正常数据并执行 Verification
8. 再运行低质量/冲突场景，观察拒识和人工复核路径

完整演示节奏见 `DEMO_SCRIPT_2MIN_ZH.md`。
