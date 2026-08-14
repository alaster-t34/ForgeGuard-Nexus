const API = "/api/v1";

const state = {
  view: "command",
  loading: true,
  busy: false,
  error: null,
  summary: null,
  trend: null,
  sustainability: null,
  assets: [],
  incidents: [],
  inventory: [],
  production: [],
  technicians: [],
  agents: [],
  edgeNodes: [],
  audit: [],
  models: [],
  tools: [],
  scenarios: [],
  platform: null,
  selectedAssetId: "FG-BRG-001",
  selectedIncidentId: null,
  scenario: "outer_race_spall",
  scenarioCategory: "全部",
  scenarioFilter: "",
  dataMode: "live",
  liveSessions: [],
  liveSession: null,
  liveFaultMode: "normal",
  liveSensorFault: "none",
  liveTickBusy: false,
  csvReports: [],
  csvReport: null,
  searchOpen: false,
  searchQuery: "",
  searchIndex: 0,
  helpOpen: false,
  assistantOpen: false,
  assistantBusy: false,
  assistantDraft: "",
  selectedAgentId: "evidence_quality",
  agentTab: "overview",
  agentFilter: "",
  agentStatusFilter: "all",
  selectedToolName: null,
  selectedModelId: null,
  assistantMessages: [
    { role: "assistant", text: "选择资产或事件后，我可以解释数据质量、诊断依据、RUL、安全约束、可持续影响与维修方案。" },
  ],
};

const CSV_MAX_BYTES = 128 * 1024 * 1024;

let liveTimer = null;

const navItems = [
  ["command", "command", "运行总览", "全厂状态"],
  ["data", "data", "数据检测与分析", "实时与 CSV"],
  ["scenarios", "spark", "工业场景库", "故障与韧性场景"],
  ["asset", "assets", "设备健康", "设备台账"],
  ["incident", "incidents", "告警事件", "证据与风险"],
  ["decision", "decision", "维修决策", "方案与审批"],
  ["work", "work", "工单执行", "现场作业"],
  ["sustainability", "leaf", "能耗与环境", "能耗与碳"],
  ["edge", "node", "边缘设备", "现场节点"],
  ["agents", "agents", "AI 智能体", "协同决策"],
  ["governance", "shield", "系统审计", "追溯记录"],
];

const scenarioFallback = {
  outer_race_spall: { id: "outer_race_spall", name: "轴承外圈剥落", category: "轴承与旋转机械", description: "周期性冲击与局部表面缺陷。", severity: "high", modalities: ["振动", "视觉", "温度"] },
};

const agentFlowOrder = [
  "coordinator", "evidence_quality", "perception", "knowledge", "diagnosis", "reliability",
  "safety", "sustainability", "resilience", "planner", "governance", "work_order", "verification",
];

const agentProfiles = {
  coordinator: {
    label: "流程协调智能体", stage: "编排", icon: "agents",
    mission: "维护受治理状态机，协调各专业智能体按证据顺序工作，并保证流程只能沿合法状态迁移。",
    responsibilities: ["拆解设备事件任务", "按顺序调用专业智能体", "记录状态迁移与异常", "阻止越权或缺证据执行"],
    inputs: ["设备事件", "用户请求", "流程状态"], outputs: ["执行计划", "状态迁移", "审计轨迹"],
    tools: ["asset.query", "research.search"],
  },
  evidence_quality: {
    label: "数据质量智能体", stage: "质量门控", icon: "data",
    mission: "在诊断前验证采样、传感器与模态数据是否可信；质量不足时拒绝自动结论并提出补采要求。",
    responsibilities: ["削波、掉点与偏置检测", "有效位数与信噪比评估", "多模态时间对齐检查", "生成补采建议"],
    inputs: ["振动", "温度", "电流", "图像", "采样元数据"], outputs: ["质量评分", "拒识原因", "补采要求"],
    tools: ["asset.query"],
  },
  perception: {
    label: "多模态感知智能体", stage: "感知", icon: "radio",
    mission: "将振动、视觉、温度与电流等原始信号转化为可供诊断使用的结构化观测。",
    responsibilities: ["信号特征提取", "视觉异常定位", "模态置信度计算", "时间窗口对齐"],
    inputs: ["时序信号", "图像", "运行工况"], outputs: ["特征向量", "异常区域", "模态观测"],
    tools: ["asset.query"],
  },
  knowledge: {
    label: "工业知识智能体", stage: "知识增强", icon: "file",
    mission: "检索设备手册、FMEA、安全规范与历史案例，为诊断和维护方案提供可追溯依据。",
    responsibilities: ["检索故障模式", "匹配设备手册", "引用安全规范", "召回相似历史案例"],
    inputs: ["故障线索", "设备型号", "运行工况"], outputs: ["知识证据", "引用来源", "适用边界"],
    tools: ["knowledge.failure_modes", "research.search"],
  },
  diagnosis: {
    label: "故障诊断智能体", stage: "诊断", icon: "incidents",
    mission: "综合模型输出、知识证据与反证，形成主故障假设、备选解释和不确定性说明。",
    responsibilities: ["生成故障假设", "关联支持证据", "记录矛盾证据", "判断是否需要补采"],
    inputs: ["质量合格观测", "模型概率", "知识证据"], outputs: ["主诊断", "备选诊断", "证据链"],
    tools: ["knowledge.failure_modes", "research.search"],
  },
  reliability: {
    label: "寿命与风险智能体", stage: "可靠性", icon: "clock",
    mission: "评估健康度、RUL 分位区间、恶化速度与继续运行风险，避免只给出单一寿命数字。",
    responsibilities: ["健康指数计算", "RUL P10/P50/P90", "风险分级", "限制因素分析"],
    inputs: ["诊断结果", "趋势数据", "负载与转速"], outputs: ["健康度", "寿命区间", "继续运行风险"],
    tools: ["asset.query"],
  },
  safety: {
    label: "人员安全智能体", stage: "人本安全", icon: "shield",
    mission: "识别维修过程中的机械、电气、热和重物风险，约束人员资质、PPE、LOTO 与最少作业人数。",
    responsibilities: ["危险源识别", "PPE 与 LOTO 要求", "人员资质匹配", "审批门槛判定"],
    inputs: ["设备结构", "维修动作", "人员技能"], outputs: ["安全评分", "控制措施", "授权要求"],
    tools: ["workforce.query", "asset.query"],
  },
  sustainability: {
    label: "能耗与环境智能体", stage: "可持续", icon: "leaf",
    mission: "量化异常能耗、CO₂e、废品与部件循环利用影响，使环境价值进入维修方案评分。",
    responsibilities: ["异常能耗估算", "碳排影响计算", "废弃物风险评估", "循环维修收益评估"],
    inputs: ["能耗基线", "故障工况", "维修方案"], outputs: ["能耗影响", "CO₂e", "废弃物影响"],
    tools: ["asset.query", "production.context"],
  },
  resilience: {
    label: "生产韧性智能体", stage: "韧性", icon: "node",
    mission: "联合生产缓冲、备件、人员与离线能力，评估故障对连续生产和恢复时间的影响。",
    responsibilities: ["生产缓冲评估", "备件风险评估", "人员就绪度评估", "降级与恢复方案"],
    inputs: ["排产", "库存", "人员", "设备风险"], outputs: ["韧性评分", "恢复时间", "兜底方案"],
    tools: ["production.context", "inventory.query", "workforce.query"],
  },
  planner: {
    label: "维修规划智能体", stage: "决策规划", icon: "decision",
    mission: "在人员安全、韧性、可持续、停机和成本之间进行多目标比较，生成可执行备选方案。",
    responsibilities: ["生成维修选项", "多目标评分", "禁忌条件检查", "推荐方案排序"],
    inputs: ["诊断", "RUL", "安全", "韧性", "环境"], outputs: ["维修选项", "评分明细", "推荐理由"],
    tools: ["inventory.query", "production.context", "workforce.query"],
  },
  governance: {
    label: "审批治理智能体", stage: "人机共治", icon: "shield",
    mission: "执行权限、证据与审批策略；高风险动作必须由授权人员明确批准。",
    responsibilities: ["审批状态检查", "高风险工具阻断", "权限与角色校验", "审计记录生成"],
    inputs: ["推荐方案", "用户身份", "审批意见"], outputs: ["批准/拒绝/补证", "治理记录"],
    tools: ["work_order.issue"],
  },
  work_order: {
    label: "工单执行智能体", stage: "执行", icon: "work",
    mission: "将已批准方案转换为工单、安全清单与移动执行步骤，但不直接控制生产设备。",
    responsibilities: ["生成工单", "拆解作业步骤", "绑定安全控制", "收集现场完成证据"],
    inputs: ["已批准方案", "人员与备件", "安全要求"], outputs: ["工单", "移动步骤", "执行证据"],
    tools: ["work_order.issue"],
  },
  verification: {
    label: "维修后验证智能体", stage: "闭环验证", icon: "check",
    mission: "比较维修前后证据，确认振动、温度、能耗与视觉异常是否恢复；不通过则自动重开事件。",
    responsibilities: ["前后指标对比", "恢复门槛判定", "工单关闭或重开", "生成验证证据包"],
    inputs: ["维修前证据", "维修后数据", "验收门槛"], outputs: ["验证结论", "恢复幅度", "关闭/重开决定"],
    tools: ["asset.query"],
  },
};


const iconPaths = {
  command: '<path d="M4 6h16M4 12h10M4 18h7"/><circle cx="18" cy="12" r="3"/><path d="M18 9V5m0 14v-4"/>',
  assets: '<path d="M4 20h16M6 20V9l6-5 6 5v11M9 20v-5h6v5"/>',
  incidents: '<path d="M12 3 2.8 20h18.4z"/><path d="M12 9v4m0 3h.01"/>',
  decision: '<path d="M5 5h5v5H5zM14 14h5v5h-5zM14 5h5v5h-5zM5 14h5v5H5z"/><path d="m10 7 4 0M7 10v4m10-4v4m-7 3h4"/>',
  work: '<path d="M9 5h6M10 3h4v4h-4z"/><rect x="5" y="5" width="14" height="16" rx="2"/><path d="m9 13 2 2 4-5"/>',
  leaf: '<path d="M20 4C11 4 5 9 5 16c0 2 1 4 3 5 0-7 4-10 10-13-4 4-6 8-6 13 6-1 9-7 8-17Z"/>',
  node: '<rect x="3" y="4" width="8" height="6" rx="1"/><rect x="13" y="14" width="8" height="6" rx="1"/><path d="M7 10v4h10v-4M7 17h6"/>',
  agents: '<circle cx="8" cy="8" r="3"/><circle cx="17" cy="7" r="2.5"/><circle cx="16" cy="17" r="3"/><path d="m10.5 9.5 3.8-1M9.8 10.5l4.2 4.2M17 9.5v4.5"/>',
  shield: '<path d="M12 3 4.5 6v5.2c0 4.5 3 7.6 7.5 9.8 4.5-2.2 7.5-5.3 7.5-9.8V6z"/><path d="m8.5 12 2.3 2.3 4.8-5"/>',
  search: '<circle cx="11" cy="11" r="6"/><path d="m16 16 4.5 4.5"/>',
  data: '<path d="M4 18V6m5 12V9m5 9V4m5 14v-7"/><path d="M2 21h20"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9.7 9a2.5 2.5 0 1 1 4.6 1.4c-.8 1.1-2.3 1.4-2.3 3.1M12 17h.01"/>',
  upload: '<path d="M12 16V4m0 0-4 4m4-4 4 4"/><path d="M4 15v5h16v-5"/>',
  radio: '<circle cx="12" cy="12" r="2"/><path d="M7.8 7.8a6 6 0 0 0 0 8.4M16.2 7.8a6 6 0 0 1 0 8.4M4.5 4.5a10.6 10.6 0 0 0 0 15M19.5 4.5a10.6 10.6 0 0 1 0 15"/>',
  file: '<path d="M6 2h8l4 4v16H6z"/><path d="M14 2v5h5M9 12h6M9 16h6"/>',
  play: '<path d="m9 7 8 5-8 5z"/>',
  arrow: '<path d="m9 6 6 6-6 6"/>',
  check: '<path d="m5 12 4 4 10-10"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
  bolt: '<path d="M13 2 4 14h7l-1 8 9-13h-7z"/>',
  server: '<rect x="4" y="3" width="16" height="7" rx="2"/><rect x="4" y="14" width="16" height="7" rx="2"/><path d="M8 7h.01M8 18h.01M12 7h5M12 18h5"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1-5 4-7 8-7s7 2 8 7"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  chat: '<path d="M4 5h16v11H8l-4 4z"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  box: '<path d="m4 7 8-4 8 4-8 4zM4 7v10l8 4 8-4V7M12 11v10"/>',
  spark: '<path d="m12 2 1.8 5.2L19 9l-5.2 1.8L12 16l-1.8-5.2L5 9l5.2-1.8zM19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>',
};

function icon(name, className = "") {
  return `<svg class="icon ${className}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${iconPaths[name] ?? ""}</svg>`;
}

function e(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function clamp(value, min = 0, max = 100) {
  return Math.min(max, Math.max(min, Number(value) || 0));
}

function enumValue(value) {
  if (typeof value === "string") return value;
  return value?.value ?? String(value ?? "");
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function formatHours(hours) {
  if (hours == null) return "—";
  return Number(hours) >= 48 ? `${Math.round(Number(hours) / 24)} d` : `${Number(hours).toFixed(1)} h`;
}

function formatMoney(value) {
  return new Intl.NumberFormat("zh-CN", { style: "currency", currency: "CNY", maximumFractionDigits: 0 }).format(Number(value) || 0);
}

function riskLabel(value) {
  return { low: "低", medium: "中", high: "高", critical: "严重" }[enumValue(value)] ?? enumValue(value);
}

function statusLabel(value) {
  return {
    healthy: "健康", watch: "关注", warning: "预警", critical: "严重", maintenance: "维护中", degraded: "降级", offline: "离线",
    new: "新建", analyzing: "分析中", awaiting_approval: "等待审批", approved: "已批准", in_progress: "执行中", verifying: "验证中", resolved: "已闭环", reopened: "已重开", escalated: "已升级",
    idle: "空闲", running: "运行中", waiting: "等待", online: "在线", stale: "过期",
  }[enumValue(value)] ?? enumValue(value).replaceAll("_", " ");
}

async function request(path, init = {}) {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body));
  }
  return response.json();
}

const api = {
  dashboard: () => request("/dashboard/summary"),
  trend: () => request("/dashboard/trend"),
  sustainability: () => request("/sustainability/summary"),
  assets: () => request("/assets"),
  incidents: () => request("/incidents"),
  inventory: () => request("/inventory"),
  production: () => request("/production/orders"),
  technicians: () => request("/people/technicians"),
  agents: () => request("/agents/status"),
  edgeNodes: () => request("/edge/nodes"),
  audit: () => request("/audit/events?limit=80"),
  models: () => request("/models"),
  tools: () => request("/tools"),
  platform: () => request("/system/status"),
  scenarios: () => request("/demo/scenarios"),
  liveSessions: () => request("/analysis/live/sessions"),
  startLive: payload => request("/analysis/live/sessions", { method: "POST", body: JSON.stringify(payload) }),
  stopLive: sessionId => request(`/analysis/live/sessions/${sessionId}`, { method: "DELETE" }),
  simulateLive: (sessionId, payload) => request(`/analysis/live/sessions/${sessionId}/simulate`, { method: "POST", body: JSON.stringify(payload) }),
  csvReports: () => request("/analysis/csv/reports?limit=12"),
  analyzeCsv: async formData => {
    const response = await fetch(`${API}/analysis/csv`, { method: "POST", body: formData });
    if (!response.ok) {
      const body = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body));
    }
    return response.json();
  },
  runDemo: scenario => request("/demo/run", { method: "POST", body: JSON.stringify({ scenario, asset_id: state.selectedAssetId }) }),
  approve: (incidentId, optionId, decision = "approve") => request(`/incidents/${incidentId}/approve`, {
    method: "POST",
    body: JSON.stringify({
      option_id: optionId,
      approved_by: "Competition Safety Officer",
      role: "Authorized maintenance approver",
      decision,
      comment: decision === "approve" ? "Evidence, safety controls and production impact reviewed." : "Additional evidence requested.",
    }),
  }),
  complete: (incidentId, scenario) => request(`/demo/${incidentId}/complete?scenario=${encodeURIComponent(scenario)}`, { method: "POST", body: "{}" }),
  reset: () => request("/demo/reset", { method: "POST", body: "{}" }),
  assistant: payload => request("/assistant/query", { method: "POST", body: JSON.stringify(payload) }),
};

async function loadAll() {
  state.loading = true;
  render();
  try {
    const results = await Promise.allSettled([
      api.dashboard(), api.trend(), api.sustainability(), api.assets(), api.incidents(), api.inventory(),
      api.production(), api.technicians(), api.agents(), api.edgeNodes(), api.audit(), api.models(), api.tools(), api.platform(),
      api.scenarios(), api.liveSessions(), api.csvReports(),
    ]);
    const keys = ["summary", "trend", "sustainability", "assets", "incidents", "inventory", "production", "technicians", "agents", "edgeNodes", "audit", "models", "tools", "platform", "scenarios", "liveSessions", "csvReports"];
    results.forEach((result, index) => {
      if (result.status === "fulfilled") state[keys[index]] = result.value;
    });
    if (!state.selectedIncidentId && state.incidents.length) state.selectedIncidentId = state.incidents[0].id;
    if (!state.liveSession && state.liveSessions.length) state.liveSession = state.liveSessions[0];
    if (!state.csvReport && state.csvReports.length) state.csvReport = state.csvReports[0];
    state.error = results.some(item => item.status === "rejected") ? "部分服务尚未返回，界面已进入降级模式。" : null;
  } catch (error) {
    state.error = error.message;
  } finally {
    state.loading = false;
    render();
  }
}

function selectedAsset() {
  return state.assets.find(item => item.id === state.selectedAssetId) ?? state.assets[0] ?? null;
}

function selectedIncident() {
  return state.incidents.find(item => item.id === state.selectedIncidentId) ?? state.incidents[0] ?? null;
}

function scenarioCatalog() {
  return state.scenarios.length ? state.scenarios : Object.values(scenarioFallback);
}

function selectedScenario() {
  return scenarioCatalog().find(item => item.id === state.scenario) ?? scenarioCatalog()[0] ?? scenarioFallback.outer_race_spall;
}

function localizedSummary(value) {
  const text = String(value ?? "");
  const translations = {
    "Energy consumption increased without a matching production-load increase.": "生产负载没有增加，但设备能耗持续上升。",
    "Bearing temperature and broadband vibration trend upward after shift change.": "换班后轴承温度和宽频振动持续上升。",
    "Line 2 spindle bearing shows periodic impacts and a visible surface defect.": "2号线主轴轴承出现周期性冲击和可见表面缺陷。",
  };
  return translations[text] ?? text;
}

function downloadJson(fileName, data) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

function ring(value, label, size = "normal") {
  const v = clamp(value);
  const r = 43;
  const circumference = 2 * Math.PI * r;
  return `<div class="metric-ring metric-ring--${size}">
    <svg viewBox="0 0 100 100" aria-hidden="true">
      <circle class="metric-ring__track" cx="50" cy="50" r="${r}" />
      <circle class="metric-ring__value" cx="50" cy="50" r="${r}" stroke-dasharray="${circumference}" stroke-dashoffset="${circumference * (1 - v / 100)}" />
    </svg>
    <div><strong>${Math.round(v)}</strong><span>${e(label)}</span></div>
  </div>`;
}

function miniLine(values, className = "") {
  const width = 420, height = 120;
  const min = Math.min(...values), max = Math.max(...values);
  const range = max - min || 1;
  const points = values.map((value, index) => `${(index / (values.length - 1)) * width},${height - 12 - ((value - min) / range) * (height - 24)}`).join(" ");
  const area = `0,${height} ${points} ${width},${height}`;
  return `<svg class="sparkline ${className}" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">
    <defs><linearGradient id="lineFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="currentColor" stop-opacity=".24"/><stop offset="1" stop-color="currentColor" stop-opacity="0"/></linearGradient></defs>
    <polyline class="sparkline__area" points="${area}" />
    <polyline class="sparkline__line" points="${points}" />
  </svg>`;
}

function chart(values, labels, second = null) {
  const width = 720, height = 220, pad = 24;
  const all = second ? values.concat(second) : values;
  const min = Math.min(...all), max = Math.max(...all), range = max - min || 1;
  const path = data => data.map((value, index) => {
    const x = pad + (index / (data.length - 1)) * (width - pad * 2);
    const y = height - pad - ((value - min) / range) * (height - pad * 2);
    return `${index ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`;
  }).join(" ");
  return `<svg class="trend-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="趋势图">
    ${[0,1,2,3,4].map(i => `<line x1="${pad}" y1="${pad + i * (height - pad * 2) / 4}" x2="${width - pad}" y2="${pad + i * (height - pad * 2) / 4}" />`).join("")}
    <path class="trend-chart__primary" d="${path(values)}" />
    ${second ? `<path class="trend-chart__secondary" d="${path(second)}" />` : ""}
    ${labels.map((label, index) => index % 2 === 0 ? `<text x="${pad + (index / (labels.length - 1)) * (width - pad * 2)}" y="${height - 4}" text-anchor="middle">${e(label)}</text>` : "").join("")}
  </svg>`;
}

function statusPill(value, label = null) {
  const normalized = enumValue(value);
  return `<span class="status-pill status-pill--${e(normalized)}"><i></i>${e(label ?? statusLabel(normalized))}</span>`;
}

function kpi(title, value, unit, delta, tone = "teal") {
  return `<article class="kpi kpi--${tone}">
    <div class="kpi__top"><span>${e(title)}</span><i></i></div>
    <div class="kpi__value"><strong>${e(value)}</strong><small>${e(unit)}</small></div>
    <p>${e(delta)}</p>
  </article>`;
}

function factoryMap() {
  const assets = state.assets;
  const nodes = [
    [21, 28], [48, 22], [74, 34], [32, 64], [67, 70],
  ];
  return `<div class="factory-map">
    <div class="factory-map__header"><div><span>工厂运行场景</span><strong>北部工厂 · 装配与公用工程</strong></div><button data-nav="assets">查看资产拓扑 ${icon("arrow")}</button></div>
    <svg viewBox="0 0 820 360" preserveAspectRatio="xMidYMid meet" role="img" aria-label="工厂资产拓扑">
      <defs>
        <linearGradient id="floor" x1="0" x2="1"><stop offset="0" stop-color="#0b2030"/><stop offset="1" stop-color="#091722"/></linearGradient>
        <filter id="glow"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      </defs>
      <path class="map-floor" d="M65 290 285 170 760 230 535 345z" fill="url(#floor)" />
      ${[0,1,2,3,4,5].map(i => `<path class="map-grid" d="M${105+i*78} 270 ${325+i*72} 185"/>`).join("")}
      ${[0,1,2,3,4].map(i => `<path class="map-grid" d="M${140+i*100} ${250+i*12} ${620+i*25} ${320-i*8}"/>`).join("")}
      <g class="map-line"><rect x="160" y="152" width="170" height="72" rx="8"/><rect x="372" y="176" width="142" height="62" rx="8"/><rect x="558" y="205" width="132" height="58" rx="8"/></g>
      ${assets.slice(0,5).map((asset, index) => {
        const [x,y] = nodes[index];
        const critical = ["warning","critical","degraded"].includes(enumValue(asset.status));
        return `<g class="map-asset ${critical ? "map-asset--risk" : ""}" transform="translate(${x*8.2-5} ${y*3.4-3})" data-asset="${e(asset.id)}">
          <circle r="16"/><circle class="map-asset__pulse" r="24"/>
          <path d="M-7 3h14M-5-3h10"/>
          <text x="24" y="-2">${e(asset.id)}</text><text class="map-asset__health" x="24" y="12">${Math.round(asset.health_score)} / 100</text>
        </g>`;
      }).join("")}
    </svg>
    <div class="factory-map__legend"><span><i class="ok"></i>健康资产</span><span><i class="risk"></i>风险资产</span><span><i class="edge"></i>边缘节点在线</span></div>
  </div>`;
}

function shell(content) {
  const summary = state.summary ?? {};
  const platform = state.platform ?? {};
  const activeIncident = selectedIncident();
  return `<div class="app-shell">
    <aside class="sidebar">
      <div class="brand"><div class="brand__mark"><span></span></div><div><strong>ForgeGuard</strong><small>NEXUS 5.0</small></div></div>
      <nav>${navItems.map(([view, iconName, zh, en]) => `<button class="nav-item ${state.view === view ? "active" : ""}" data-nav="${view}">${icon(iconName)}<span><b>${zh}</b><small>${en}</small></span>${state.view === view ? '<i class="nav-item__rail"></i>' : ""}</button>`).join("")}</nav>
      <div class="sidebar__edge">
        <div class="sidebar__edge-title"><span></span><b>边缘运行状态</b><small>${summary.edge_nodes_online ?? state.edgeNodes.length} 个节点在线</small></div>
        <div class="sidebar__edge-row"><i class="dot dot--green"></i><span>${e(platform.platform ?? "Portable runtime")}</span></div>
        <div class="sidebar__edge-row"><i class="dot dot--cyan"></i><span>${e(platform.runtime ?? "CPU + TensorRT")}</span></div>
      </div>
      <div class="operator"><div class="operator__avatar">审</div><div><strong>授权审批员</strong><small>高风险操作由人确认</small></div><button data-help aria-label="使用说明">${icon("help")}</button></div>
    </aside>
    <main>
      <header class="topbar">
        <div><button class="mobile-menu" aria-label="打开导航">${icon("menu")}</button><p>设备健康 · 安全维修 · 人工审批 · 维修后验证</p><h1>${e(navItems.find(item => item[0] === state.view)?.[2] ?? "工业智能平台")}</h1></div>
        <div class="topbar__actions">
          <button type="button" class="search-box" data-open-search onclick="window.ForgeGuardUI.openSearch()">${icon("search")}<span>搜索设备、告警、工单或功能</span><kbd>Ctrl K</kbd></button>
          <div class="live"><i></i>服务在线</div>
          <button class="icon-button" data-help aria-label="打开使用说明">${icon("help")}</button>
          <button class="icon-button" data-assistant aria-label="打开智能助手">${icon("chat")}</button>
        </div>
      </header>
      ${state.error ? `<div class="degraded-banner">${icon("incidents")}<span>${e(state.error)}</span></div>` : ""}
      <section class="page">${content}</section>
      <footer><span>ForgeGuard Nexus 5.0 · 工业设备健康与维修闭环平台</span><span>先验证数据，再给结论；人批准，维修后复测</span></footer>
    </main>
  </div>`;
}


function searchableItems() {
  const pageItems = navItems.map(([view, iconName, zh, en]) => ({ type: "page", id: view, title: zh, subtitle: en, iconName }));
  const assetItems = state.assets.map(item => ({ type: "asset", id: item.id, title: item.name, subtitle: `${item.id} · ${item.location}`, iconName: "assets" }));
  const incidentItems = state.incidents.map(item => ({ type: "incident", id: item.id, title: localizedSummary(item.summary), subtitle: `${item.id} · ${statusLabel(item.status)}`, iconName: "incidents" }));
  const workItems = state.incidents.filter(item => item.work_order).map(item => ({ type: "work", id: item.id, title: item.work_order.title, subtitle: `${item.work_order.id} · ${item.asset_id}`, iconName: "work" }));
  const scenarioItems = scenarioCatalog().map(item => ({ type: "scenario", id: item.id, title: item.name, subtitle: `${item.category} · ${item.description}`, iconName: "spark" }));
  const helpItems = [
    { type: "help", id: "realtime", title: "如何进行实时检测", subtitle: "传感器持续上传或使用内置实时演示", iconName: "radio" },
    { type: "help", id: "csv", title: "如何分析 CSV 文件", subtitle: "上传历史振动数据并生成窗口级报告", iconName: "file" },
    { type: "help", id: "approval", title: "为什么需要人工审批", subtitle: "AI 不直接控制设备或绕过安全负责人", iconName: "shield" },
  ];
  return [...pageItems, ...scenarioItems, ...assetItems, ...incidentItems, ...workItems, ...helpItems];
}

function searchModal() {
  if (!state.searchOpen) return "";
  const query = state.searchQuery.trim().toLowerCase();
  const items = searchableItems().filter(item => !query || `${item.title} ${item.subtitle} ${item.id}`.toLowerCase().includes(query)).slice(0, 18);
  if (state.searchIndex >= items.length) state.searchIndex = 0;
  return `<div class="modal-backdrop" data-close-search><section class="search-modal" role="dialog" aria-label="全局搜索" onclick="event.stopPropagation()">
    <div class="search-modal__input">${icon("search")}<input data-search-input autofocus value="${e(state.searchQuery)}" placeholder="输入设备名称、编号、告警、工单或功能…" /><kbd>Esc</kbd></div>
    <div class="search-results">${items.length ? items.map((item, index) => `<button class="${index === state.searchIndex ? "active" : ""}" data-search-index="${index}" data-search-type="${e(item.type)}" data-search-id="${e(item.id)}"><span>${icon(item.iconName)}</span><div><strong>${e(item.title)}</strong><small>${e(item.subtitle)}</small></div>${icon("arrow")}</button>`).join("") : '<div class="search-empty">没有匹配结果。可搜索“CSV”“实时检测”“FG-BRG-001”或告警编号。</div>'}</div>
    <footer><span>↑↓ 浏览</span><span>Enter 打开</span><span>Esc 关闭</span></footer>
  </section></div>`;
}

function helpModal() {
  if (!state.helpOpen) return "";
  return `<div class="modal-backdrop" data-close-help><section class="help-modal" role="dialog" aria-label="使用说明" onclick="event.stopPropagation()">
    <header><div><span>${icon("help")}</span><div><strong>ForgeGuard 使用说明</strong><small>用普通语言说明每个模块做什么</small></div></div><button data-close-help>${icon("close")}</button></header>
    <div class="help-grid">
      <article><b>1. 数据检测与分析</b><p>实时检测持续接收传感器数据；CSV 分析用于已有文件。两者共用同一质量检查和故障模型。</p><button data-help-nav="data">打开数据分析</button></article>
      <article><b>2. 告警事件</b><p>异常不是直接结论。系统会保存证据、显示不确定性，并列出还缺少哪些信息。</p><button data-help-nav="incident">查看告警</button></article>
      <article><b>3. 维修决策</b><p>比较立即停机、延后维修、降低负载或重新采样等方案，同时考虑安全、库存、人员、生产和环境影响。</p><button data-help-nav="decision">查看维修方案</button></article>
      <article><b>4. 工单与复测</b><p>批准后才创建工单。维修完成后必须重新采样，确认设备恢复才能关闭事件。</p><button data-help-nav="work">查看工单</button></article>
    </div>
    <div class="term-guide"><h3>界面术语</h3><dl><div><dt>数据质量门控</dt><dd>先判断采集数据能不能相信，不能相信就拒绝诊断。</dd></div><div><dt>RUL</dt><dd>预计剩余可用时间，显示为区间，不是寿命保证。</dd></div><div><dt>AI 智能体</dt><dd>分别负责质量、诊断、寿命、安全、环境和维修规划的程序模块。</dd></div><div><dt>边缘设备</dt><dd>部署在现场的 Jetson、工业 PC 或采集网关。</dd></div></dl></div>
    <p class="help-boundary">本软件是工业决策支持系统，不直接控制生产设备，也不替代持证维修人员和安全负责人。</p>
  </section></div>`;
}

function assistantDrawer(incident) {
  if (!state.assistantOpen) return "";
  return `<div class="assistant-backdrop" data-close-assistant><aside class="assistant" role="dialog" aria-label="工业智能助手" onclick="event.stopPropagation()">
    <header><div><span>${icon("spark")}</span><div><strong>ForgeGuard Copilot</strong><small>本地优先 · 治理约束</small></div></div><button data-close-assistant>${icon("close")}</button></header>
    <div class="assistant__context"><span>当前上下文</span><b>${incident ? e(incident.id) : e(selectedAsset()?.name ?? "全厂运行")}</b></div>
    <div class="assistant__messages">${state.assistantMessages.map(message => `<article class="message message--${message.role}"><span>${message.role === "assistant" ? "AI" : "YOU"}</span><p>${e(message.text)}</p></article>`).join("")}${state.assistantBusy ? '<article class="message message--assistant"><span>AI</span><p class="typing">正在读取证据链<span></span><span></span><span></span></p></article>' : ""}</div>
    <form class="assistant__form"><textarea name="query" rows="2" placeholder="询问：为什么推荐停机？人员安全约束是什么？">${e(state.assistantDraft)}</textarea><button ${state.assistantBusy ? "disabled" : ""}>发送 ${icon("arrow")}</button></form>
    <p class="assistant__notice">不直接控制设备；生产和维修动作必须由授权人员批准。</p>
  </aside></div>`;
}

function commandView() {
  const s = state.summary ?? {};
  const t = state.trend ?? { labels: [], fleet_health: [], energy_mwh: [] };
  const alerts = state.incidents.filter(item => enumValue(item.status) !== "resolved").slice(0, 4);
  const scenario = selectedScenario();
  return `<div class="command-view">
    <div class="intro-row"><div><h2>从设备信号到可验证恢复的闭环决策</h2><p>多模态感知、工业知识增强、多 Agent 协同与人机共治，统一人员安全、生产韧性和环境影响。</p></div><div class="intro-actions"><button type="button" class="scenario-picker" data-nav="scenarios"><span><small>当前演示场景</small><b>${e(scenario.name)}</b></span>${icon("arrow")}</button><button class="primary-action" data-run-demo ${state.busy ? "disabled" : ""}>${icon("play")}运行 Agent 闭环</button></div></div>
    <div class="kpi-grid">
      ${kpi("资产总数", s.total_assets ?? state.assets.length, "台", "跨设备统一健康管理", "blue")}
      ${kpi("健康资产", s.healthy_assets ?? 0, "台", `舰队健康度 ${s.fleet_health_score ?? 0}%`, "green")}
      ${kpi("当前事件", s.open_incidents ?? 0, "项", `${s.pending_approvals ?? 0} 项等待人工审批`, "red")}
      ${kpi("工单执行", s.active_work_orders ?? 0, "项", "维修完成后必须复测", "amber")}
      ${kpi("韧性指数", s.resilience_index ?? 86, "/100", `${s.edge_nodes_online ?? 0} 个边缘节点在线`, "cyan")}
      ${kpi("节能收益", s.energy_saved_kwh ?? 0, "kWh", `避免废弃 ${s.avoided_waste_kg ?? 0} kg`, "violet")}
    </div>
    <section class="function-center" aria-label="常用功能">
      <header><div><span>常用功能</span><h3>检测、分析、决策与执行</h3></div><button type="button" data-nav="scenarios">查看 ${scenarioCatalog().length} 个工业场景 ${icon("arrow")}</button></header>
      <div class="function-center__grid">
        <button data-quick-mode="live">${icon("radio")}<span><b>实时检测</b><small>传感器、网关或实时演示</small></span></button>
        <button data-quick-mode="csv">${icon("file")}<span><b>CSV 文件分析</b><small>历史数据与台架导出</small></span></button>
        <button data-nav="scenarios">${icon("spark")}<span><b>工业场景库</b><small>故障、能源、供应与治理</small></span></button>
        <button data-nav="incident">${icon("incidents")}<span><b>告警事件中心</b><small>证据、风险和处置状态</small></span></button>
        <button data-nav="decision">${icon("decision")}<span><b>维修决策竞技场</b><small>安全、韧性与环境联合评分</small></span></button>
        <button data-export="summary">${icon("file")}<span><b>导出运行摘要</b><small>下载可审计 JSON 报告</small></span></button>
      </div>
    </section>
    <div class="command-grid">
      ${factoryMap()}
      <div class="side-stack">
        <article class="panel risk-panel"><header><div><span>实时风险</span><h3>最近工业事件</h3></div><button type="button" data-open-incidents aria-label="打开全部工业事件">全部 ${icon("arrow")}</button></header><div class="risk-list">${alerts.length ? alerts.map(item => `<button data-incident="${e(item.id)}" data-nav="incident"><i class="risk-dot risk-dot--${e(enumValue(item.risk))}"></i><div><strong>${e(localizedSummary(item.summary))}</strong><small>${e(item.asset_id)} · ${formatDate(item.updated_at)}</small></div>${statusPill(item.risk, riskLabel(item.risk))}</button>`).join("") : '<div class="empty-mini">暂无未闭环事件</div>'}</div></article>
        <article class="panel agent-live"><header><div><span>AI 智能体协同</span><h3>多 Agent 运行状态</h3></div><button data-nav="agents">查看 ${icon("arrow")}</button></header><div class="agent-live__grid">${state.agents.slice(0,6).map(agent => `<div><span class="agent-symbol">${icon(agent.agent === "sustainability" ? "leaf" : agent.agent === "safety" ? "shield" : "agents")}</span><div><strong>${e(agentLabel(agent.agent))}</strong><small>${agent.average_latency_ms} ms · ${(agent.success_rate*100).toFixed(0)}%</small></div>${statusPill(agent.status)}</div>`).join("")}</div></article>
      </div>
    </div>
    <div class="lower-grid">
      <article class="panel trend-panel"><header><div><span>全厂趋势</span><h3>健康与能耗趋势</h3></div><div class="legend"><span><i class="legend__health"></i>健康度</span><span><i class="legend__energy"></i>能耗</span></div></header>${t.labels.length ? chart(t.fleet_health, t.labels, t.energy_mwh.map(value => value * 50)) : ""}</article>
      <article class="panel human-value"><header><div><span>Industry 5.0</span><h3>三维价值指标</h3></div></header><div class="value-rings">${ring(s.human_safety_index ?? 91, "人员安全", "small")}${ring(s.resilience_index ?? 86, "系统韧性", "small")}${ring(s.sustainability_index ?? 84, "可持续", "small")}</div><p>任何高风险工具调用均需人工审批；边缘断网时继续执行质量门控和本地安全策略。</p></article>
    </div>
  </div>`;
}

function scenarioView() {
  const catalog = scenarioCatalog();
  const categories = ["全部", ...new Set(catalog.map(item => item.category))];
  const query = state.scenarioFilter.trim().toLowerCase();
  const filtered = catalog.filter(item => (state.scenarioCategory === "全部" || item.category === state.scenarioCategory) && (!query || `${item.name} ${item.description} ${item.category} ${(item.modalities ?? []).join(" ")}`.toLowerCase().includes(query)));
  const active = selectedScenario();
  return `<div class="scenario-view">
    <div class="scenario-hero"><div><span>工业场景库</span><h2>覆盖设备故障、数据质量、能源与生产韧性</h2><p>场景库用于演示和验证完整 Agent 闭环。它不会冒充真实工厂数据；真实检测请使用“实时检测”或“CSV 文件分析”。</p></div><div class="scenario-hero__active"><small>已选择</small><strong>${e(active.name)}</strong><span>${e(active.category)}</span><button class="primary-action" data-run-demo>${icon("play")}运行此场景</button></div></div>
    <div class="scenario-toolbar"><label>${icon("search")}<input data-scenario-filter value="${e(state.scenarioFilter)}" placeholder="搜索故障、设备、模态或业务约束" /></label><div>${categories.map(category => `<button class="${state.scenarioCategory === category ? "active" : ""}" data-scenario-category="${e(category)}">${e(category)}</button>`).join("")}</div></div>
    <div class="scenario-grid">${filtered.map(item => `<article class="scenario-card ${item.id === state.scenario ? "active" : ""}"><header><span>${e(item.category)}</span>${statusPill(item.severity, riskLabel(item.severity))}</header><h3>${e(item.name)}</h3><p>${e(item.description)}</p><div class="scenario-modalities">${(item.modalities ?? []).map(modality => `<span>${e(modality)}</span>`).join("")}</div><footer><small>${e(item.maintenance_summary ?? "进入受治理维修决策")}</small><div><button data-select-scenario="${e(item.id)}">选择</button><button class="run" data-run-scenario="${e(item.id)}">${icon("play")}运行</button></div></footer></article>`).join("") || '<div class="empty-state"><h3>没有匹配场景</h3><p>清除搜索条件或选择其他分类。</p></div>'}</div>
  </div>`;
}


function faultLabel(value) {
  return {
    normal: "正常",
    imbalance: "不平衡",
    misalignment: "不对中",
    outer_race: "外圈故障",
    inner_race: "内圈故障",
    ball: "滚动体故障",
    lubrication: "润滑异常",
    looseness: "机械松动",
    rejected_by_quality_gate: "数据质量不合格",
    unknown: "待确认",
  }[String(value ?? "")] ?? String(value ?? "待确认").replaceAll("_", " ");
}


function agentLabel(value) {
  return {
    coordinator: "流程协调智能体",
    evidence_quality: "数据质量智能体",
    perception: "多模态感知智能体",
    knowledge: "工业知识智能体",
    diagnosis: "故障诊断智能体",
    reliability: "寿命与风险智能体",
    safety: "人员安全智能体",
    sustainability: "能耗与环境智能体",
    resilience: "生产韧性智能体",
    planner: "维修规划智能体",
    maintenance_planner: "维修规划智能体",
    governance: "审批治理智能体",
    work_order: "工单执行智能体",
    verification: "维修后验证智能体",
  }[String(value ?? "")] ?? String(value ?? "智能体").replaceAll("_", " ");
}

function evidenceTitleLabel(value) {
  return {
    "Asset master data": "资产主数据",
    "Evidence quality gate": "数据质量门控结果",
    "Vibration RMS": "振动均方根（RMS）",
    "Kurtosis": "振动峭度",
    "Bearing temperature": "轴承温度",
    "Fused anomaly probability": "多模态融合异常概率",
    "Visual anomaly observation": "视觉异常观测",
    "Retrieved FMEA, manuals and safety guidance": "FMEA、设备手册与安全规范检索",
    "Production schedule and buffer": "生产计划与下游缓冲",
    "Spare-parts availability": "备件可用性",
    "Qualified workforce availability": "合格维修人员可用性",
    "Human safety assessment": "人员安全评估",
    "Energy, carbon and waste assessment": "能源、碳排与废弃物评估",
  }[String(value ?? "")] ?? String(value ?? "结构化证据").replaceAll("_", " ");
}

function evidenceSourceLabel(value) {
  return {
    "asset.query": "资产主数据服务",
    "evidence-quality-agent": "数据质量智能体",
    "sensor-gateway": "传感器网关",
    "signal-feature-service": "信号特征服务",
    "multimodal-fusion-v1": "多模态融合模型",
    "scenario-library": "工业场景库（模拟）",
    "knowledge.failure_modes": "工业知识库",
    "production.context": "生产计划服务",
    "inventory.query": "库存服务",
    "workforce.query": "人员与技能服务",
    "human-safety-agent": "人员安全智能体",
    "sustainability-agent": "能耗与环境智能体",
  }[String(value ?? "")] ?? String(value ?? "系统证据源").replaceAll("_", " ");
}

function traceActionLabel(value) {
  return {
    validate_sensor_integrity_and_cross_modal_consistency: "验证传感器完整性与跨模态一致性",
    fuse_multimodal_observations: "融合多模态观测并形成证据",
    generate_evidence_grounded_diagnosis: "生成基于证据的故障诊断",
    estimate_health_and_remaining_useful_life: "评估健康状态与剩余可用寿命",
    assess_human_safety_and_authorization: "评估人员安全、隔离与授权条件",
    estimate_energy_waste_and_lifecycle_impact: "评估异常能耗、废弃物与生命周期影响",
    evaluate_operational_resilience: "评估生产恢复能力与资源韧性",
    compare_multi_objective_maintenance_strategies: "比较多目标维修策略",
    authorize_high_risk_action: "审核高风险动作并记录人工授权",
    create_governed_work_order: "创建受治理维修工单",
    verify_post_maintenance_recovery: "验证维修后设备是否真正恢复",
  }[String(value ?? "")] ?? String(value ?? "智能体任务").replaceAll("_", " ");
}

function traceRationaleLabel(value) {
  return {
    "Reject unsafe automation when acquisition quality or modal agreement is insufficient.": "采集质量不足或多模态证据不一致时，阻止自动化结论并要求补采。",
    "Normalize telemetry and visual observations into traceable evidence.": "将遥测与视觉观测标准化为可追溯证据。",
    "Compare multimodal evidence against industrial failure modes, operating context and contradictions.": "将多模态证据与工业故障模式、运行工况和矛盾证据进行比较。",
    "Estimate a conservative RUL interval and continuation risk from calibrated health evidence.": "基于校准后的健康证据给出保守 RUL 区间和继续运行风险。",
    "Protect workers by identifying exposure, isolation, competence and approval constraints.": "识别人员暴露、能源隔离、技能资质和审批约束，保护现场人员。",
    "Quantify the environmental cost of abnormal operation and maintenance alternatives.": "量化异常运行及不同维修方案的能耗、碳排和废弃物影响。",
    "Assess recovery time, spare-part exposure, workforce readiness and offline fallback.": "评估恢复时间、备件风险、人员准备度和离线降级能力。",
    "Balance human safety, operational resilience, sustainability, downtime, cost and evidence quality.": "综合人员安全、生产韧性、可持续性、停机、成本和证据质量进行决策。",
  }[String(value ?? "")] ?? String(value ?? "");
}

function sensorFaultLabel(value) {
  return {
    none: "无传感器故障",
    low_snr: "信噪比过低",
    dropout: "采样掉点",
    drift: "基线漂移",
    clipping: "信号削波",
    quantization: "量化精度不足",
    impulse_interference: "脉冲干扰",
  }[String(value ?? "")] ?? String(value ?? "").replaceAll("_", " ");
}

function dataView() {
  return `<div class="data-view">
    <div class="plain-page-head"><div><span>两种分析方式，共用同一套质量门控与模型</span><h2>数据检测与分析</h2><p>“实时检测”用于传感器持续上传；“CSV 分析”用于历史文件、公开数据集和台架导出数据。两种方式都可生成告警事件。</p></div><button class="secondary-action" data-help>${icon("help")}查看使用说明</button></div>
    <div class="mode-tabs" role="tablist">
      <button class="${state.dataMode === "live" ? "active" : ""}" data-data-mode="live">${icon("radio")}实时检测<small>传感器 / 网关 / 演示信号</small></button>
      <button class="${state.dataMode === "csv" ? "active" : ""}" data-data-mode="csv">${icon("file")}CSV 文件分析<small>历史数据 / 公开数据 / 台架导出</small></button>
    </div>
    ${state.dataMode === "live" ? liveAnalysisView() : csvAnalysisView()}
  </div>`;
}

function liveAnalysisView() {
  const session = state.liveSession;
  if (!session || session.status === "stopped") {
    return `<div class="data-layout">
      <form class="panel setup-form" data-live-start>
        <header><div><span>Step 1</span><h3>创建实时检测任务</h3></div>${statusPill("online", "准备就绪")}</header>
        <div class="form-grid">
          <label><span>监测设备</span><select name="asset_id">${state.assets.map(item => `<option value="${e(item.id)}">${e(item.name)} · ${e(item.id)}</option>`).join("")}</select></label>
          <label><span>数据来源</span><select name="source"><option value="simulator">内置实时演示（无需硬件）</option><option value="external">外部传感器 / 网关</option></select></label>
          <label><span>采样率 Hz</span><input name="sample_rate_hz" type="number" value="12000" min="64" /></label>
          <label><span>转速 RPM</span><input name="rpm" type="number" value="1800" min="0" /></label>
          <label><span>负载 %</span><input name="load_percent" type="number" value="70" min="0" max="200" /></label>
          <label class="check-field"><input name="open_incident" type="checkbox" checked /><span>检测到异常时自动生成告警事件</span></label>
        </div>
        <button class="primary-action" ${state.busy ? "disabled" : ""}>${icon("play")}开始实时检测</button>
      </form>
      <article class="panel explain-panel"><header><div><span>工作流程</span><h3>实时检测会做什么</h3></div></header><ol><li><b>接收连续数据帧</b><span>支持 HTTP 接口、串口适配器、边缘网关和内置演示信号。</span></li><li><b>先检查数据质量</b><span>削波、掉点、偏置、量化和转速不一致会先被识别。</span></li><li><b>再进行故障识别</b><span>低质量数据不会被强行判成设备故障。</span></li><li><b>异常进入闭环</b><span>可自动创建告警，并继续进行寿命、安全、维修和复测分析。</span></li></ol></article>
    </div>`;
  }
  const analysis = session.last_analysis;
  const model = analysis?.model_result ?? {};
  const quality = analysis?.quality ?? {};
  const history = session.history ?? [];
  return `<div class="live-console">
    <div class="live-console__top">
      <div><span class="live-indicator"><i></i>实时任务运行中</span><h2>${e(session.name)}</h2><p>${e(session.asset_id)} · ${e(session.node_id)} · ${Number(session.sample_rate_hz).toLocaleString()} Hz</p></div>
      <div class="live-actions">${session.source === "simulator" ? `<select data-live-fault>${["normal","imbalance","misalignment","outer_race","inner_race","ball","lubrication","looseness"].map(item => `<option value="${item}" ${state.liveFaultMode === item ? "selected" : ""}>${faultLabel(item)}</option>`).join("")}</select><select data-live-sensor-fault>${["none","low_snr","dropout","drift","clipping","quantization","impulse_interference"].map(item => `<option value="${item}" ${state.liveSensorFault === item ? "selected" : ""}>${sensorFaultLabel(item)}</option>`).join("")}</select>` : ""}<button class="danger-action" data-live-stop>停止检测</button></div>
    </div>
    <div class="live-kpis">
      ${kpi("已处理数据帧", session.total_frames, "帧", `${session.accepted_frames} 帧通过质量检查`, "blue")}
      ${kpi("数据质量", Math.round((quality.score ?? 0) * 100), "%", quality.warnings?.length ? `${quality.warnings.length} 项质量提醒` : "数据质量正常", quality.score >= .45 ? "green" : "red")}
      ${kpi("当前判断", faultLabel(model.class_name ?? "unknown"), "", `置信度 ${Math.round((model.confidence ?? 0) * 100)}%`, model.class_name && model.class_name !== "normal" ? "red" : "green")}
      ${kpi("异常概率", Math.round((model.anomaly_probability ?? 0) * 100), "%", session.incident_id ? `已生成 ${session.incident_id}` : "尚未触发告警", "amber")}
    </div>
    <div class="live-grid">
      <article class="panel waveform-panel"><header><div><span>实时信号</span><h3>实时振动波形</h3></div><b>${Number(session.rpm).toFixed(0)} RPM · ${Number(session.load_percent).toFixed(0)}% 负载</b></header>${session.waveform_preview?.length ? miniLine(session.waveform_preview, "waveform-live") : '<div class="empty-mini">等待第一帧数据…</div>'}<div class="waveform-metrics"><span>RMS<b>${Number(analysis?.features?.rms ?? 0).toFixed(3)} g</b></span><span>峭度<b>${Number(analysis?.features?.kurtosis ?? 0).toFixed(2)}</b></span><span>峰值因子<b>${Number(analysis?.features?.crest_factor ?? 0).toFixed(2)}</b></span><span>运行时<b>${e(model.model_id ?? "待加载")}</b></span></div></article>
      <article class="panel quality-panel"><header><div><span>数据质量门控</span><h3>数据可信度</h3></div>${statusPill((quality.score ?? 0) >= .45 ? "low" : "critical", (quality.score ?? 0) >= .45 ? "允许诊断" : "拒绝诊断")}</header>${ring((quality.score ?? 0) * 100, "质量分")}<div class="quality-warnings">${quality.warnings?.length ? quality.warnings.map(item => `<p>${icon("incidents")}<span>${e(item)}</span></p>`).join("") : '<p class="ok-copy">当前没有发现明显采集质量问题。</p>'}</div></article>
    </div>
    ${session.source === "external" ? `<article class="panel connection-guide"><header><div><span>外部数据接入</span><h3>外部设备上传地址</h3></div></header><p>外部采集程序将每个数据窗 POST 到以下接口。请求体包含 samples、rpm、load_percent 和 temperature_c。</p><code>POST /api/v1/analysis/live/sessions/${e(session.id)}/frames</code></article>` : `<div class="simulation-note">${icon("help")}当前为内置演示信号。选择不同故障后，系统会持续生成实时数据帧；该结果不能作为真实物理实验数据。</div>`}
    <article class="panel live-history"><header><div><span>最近数据帧</span><h3>最近处理记录</h3></div></header><div class="data-table"><div class="data-table__head"><span>帧</span><span>时间</span><span>质量</span><span>判断</span><span>置信度</span><span>结果</span></div>${history.slice().reverse().slice(0,12).map(item => `<div><code>#${item.sequence}</code><span>${formatDate(item.timestamp)}</span><span>${Math.round(item.quality_score*100)}%</span><strong>${faultLabel(item.predicted_class)}</strong><span>${Math.round(item.confidence*100)}%</span>${statusPill(item.accepted ? "low" : "critical", item.accepted ? "已分析" : "已拒绝")}</div>`).join("") || '<div class="empty-mini">等待数据帧…</div>'}</div></article>
  </div>`;
}

function csvAnalysisView() {
  const report = state.csvReport;
  return `<div class="csv-layout">
    <form class="panel csv-form" data-csv-form>
      <header><div><span>历史文件</span><h3>上传 CSV 并分析</h3></div>${icon("upload")}</header>
      <label class="file-drop"><input type="file" name="file" accept=".csv,.txt" required /><span>${icon("file")}<b>选择 CSV 文件</b><small>支持单列或多列；UTF-8、GB18030、UTF-16；最大 128 MB、100 万数据行、256 列</small></span></label>
      <div class="form-grid form-grid--compact">
        <label><span>设备</span><select name="asset_id">${state.assets.map(item => `<option value="${e(item.id)}">${e(item.name)} · ${e(item.id)}</option>`).join("")}</select></label>
        <label><span>信号列名或序号</span><input name="signal_column" placeholder="留空自动识别，例如 acceleration_x 或 0" /></label>
        <label><span>采样率 Hz</span><input name="sample_rate_hz" type="number" value="12000" min="64" /></label>
        <label><span>转速 RPM</span><input name="rpm" type="number" value="1800" min="0" /></label>
        <label><span>负载 %</span><input name="load_percent" type="number" value="70" min="0" max="200" /></label>
        <label><span>窗口长度</span><input name="window_size" type="number" value="2048" min="64" /></label>
        <label><span>窗口步长</span><input name="hop_size" type="number" value="1024" min="1" /></label>
        <label class="check-field"><input name="create_incident" type="checkbox" checked /><span>发现异常时创建告警事件</span></label>
      </div>
      <button class="primary-action" ${state.busy ? "disabled" : ""}>${icon("upload")}开始分析</button>
      <p class="form-note">CSV 分析不会修改原文件。结果会保存到 runtime-data/analysis-reports。包含多个 sample_id 的合并长表应先筛选单条波形，避免分析窗口跨越样本边界。</p>
    </form>
    <div class="csv-result-area">${report ? csvReportView(report) : `<article class="panel empty-analysis"><span>${icon("file")}</span><h3>尚未分析 CSV</h3><p>上传历史振动数据后，这里会显示波形、数据质量、窗口级判断、主导故障和告警结果。</p></article>`}</div>
    ${state.csvReports.length ? `<article class="panel report-list"><header><div><span>已保存报告</span><h3>最近分析记录</h3></div></header>${state.csvReports.slice(0,8).map(item => `<button data-csv-report="${e(item.id)}"><div><strong>${e(item.file_name)}</strong><small>${formatDate(item.generated_at)} · ${item.total_windows} 个窗口</small></div><span>${faultLabel(item.dominant_class)}</span>${statusPill(item.maximum_anomaly_probability >= .45 ? "high" : "low", `${Math.round(item.maximum_anomaly_probability*100)}%`)}</button>`).join("")}</article>` : ""}
  </div>`;
}

function csvReportView(report) {
  const labels = report.windows.map((_, index) => String(index + 1));
  const anomaly = report.windows.map(item => item.anomaly_probability * 100);
  const quality = report.windows.map(item => item.quality_score * 100);
  return `<article class="panel csv-report">
    <header><div><span>分析报告</span><h3>${e(report.file_name)}</h3><p>${report.total_samples.toLocaleString()} 个采样点 · ${report.duration_seconds.toFixed(2)} 秒 · 信号列 ${e(report.signal_column)}</p></div>${statusPill(report.maximum_anomaly_probability >= .45 ? "high" : "low", faultLabel(report.dominant_class))}</header>
    <div class="report-kpis"><div><span>有效窗口</span><b>${report.accepted_windows}/${report.total_windows}</b></div><div><span>平均质量</span><b>${Math.round(report.average_quality*100)}%</b></div><div><span>最高异常概率</span><b>${Math.round(report.maximum_anomaly_probability*100)}%</b></div><div><span>生成告警</span><b>${e(report.incident_id ?? "未生成")}</b></div></div>
    ${report.waveform_preview?.length ? `<div class="csv-wave"><h4>文件波形预览</h4>${miniLine(report.waveform_preview, "waveform-csv")}</div>` : ""}
    ${report.windows.length > 1 ? `<div class="csv-trend"><h4>窗口级异常概率与数据质量</h4>${chart(anomaly, labels, quality)}</div>` : ""}
    <div class="data-table csv-window-table"><div class="data-table__head"><span>窗口</span><span>时间</span><span>质量</span><span>判断</span><span>置信度</span><span>异常概率</span></div>${report.windows.slice(0,20).map(item => `<div><code>#${item.sequence+1}</code><span>${item.timestamp_seconds.toFixed(3)} s</span><span>${Math.round(item.quality_score*100)}%</span><strong>${faultLabel(item.predicted_class)}</strong><span>${Math.round(item.confidence*100)}%</span><span>${Math.round(item.anomaly_probability*100)}%</span></div>`).join("")}</div>
    ${report.warnings?.length ? `<div class="report-warnings">${report.warnings.map(item => `<p>${icon("help")}${e(item)}</p>`).join("")}</div>` : ""}
  </article>`;
}

function assetsView() {
  const asset = selectedAsset();
  if (!asset) return emptyState("暂无资产", "请先初始化平台数据。", "box");
  const healthSeries = [96,95,94,94,93,92,92,91,89,87,84,asset.health_score];
  const vib = [0.6,0.7,0.65,0.8,0.75,0.9,1.1,1.3,1.8,2.4,2.9,asset.status === "healthy" ? 0.8 : 3.1];
  return `<div class="assets-layout">
    <aside class="asset-list-panel"><div class="section-heading"><span>设备台账</span><h2>关键资产</h2></div><label class="filter-input">${icon("search")}<input placeholder="搜索资产" /></label><div class="asset-list">${state.assets.map(item => `<button class="asset-row ${item.id === asset.id ? "active" : ""}" data-asset="${e(item.id)}"><div class="asset-row__icon">${icon(item.asset_class.includes("pump") ? "bolt" : "box")}</div><div><strong>${e(item.name)}</strong><small>${e(item.id)} · ${e(item.location)}</small></div><div><b>${Math.round(item.health_score)}</b>${statusPill(item.status)}</div></button>`).join("")}</div></aside>
    <div class="asset-detail">
      <div class="asset-detail__head"><div><span>${e(asset.asset_class)}</span><h2>${e(asset.name)}</h2><p>${e(asset.id)} · ${e(asset.line)} · ${e(asset.location)}</p></div><div class="asset-detail__actions"><button class="secondary-action" data-run-demo>${icon("play")}运行诊断</button><button class="secondary-action" data-nav="decision">打开决策中心 ${icon("arrow")}</button></div></div>
      <div class="asset-health-grid"><article class="panel asset-visual"><div class="machine-visual"><div class="machine-visual__motor"><span></span><i></i><b></b></div><div class="machine-visual__shaft"></div><div class="machine-visual__bearing"></div></div><div class="asset-specs"><div><span>制造商</span><b>${e(asset.manufacturer ?? "—")}</b></div><div><span>型号</span><b>${e(asset.model ?? "—")}</b></div><div><span>基准能耗</span><b>${asset.energy_baseline_kw} kW</b></div><div><span>资产关键度</span><b>${riskLabel(asset.criticality)}</b></div></div></article>
      <article class="panel health-score-card">${ring(asset.health_score, "健康度")}<div class="health-summary"><span>中位 RUL</span><strong>${formatHours(asset.estimated_rul_hours)}</strong><small>模型输出为区间，不作为寿命承诺</small></div></article></div>
      <div class="asset-chart-grid"><article class="panel chart-card"><header><div><span>状态趋势</span><h3>健康度与振动趋势</h3></div><div class="legend"><span><i class="legend__health"></i>健康度</span><span><i class="legend__energy"></i>RMS</span></div></header>${chart(healthSeries, ["D-11","D-10","D-9","D-8","D-7","D-6","D-5","D-4","D-3","D-2","D-1","Now"], vib.map(v => v*20))}</article>
      <article class="panel asset-history"><header><div><span>维修历史</span><h3>历史记录</h3></div></header><div class="history-list"><div><i></i><div><strong>润滑巡检</strong><small>2026-06-18 · 结果正常</small></div>${statusPill("low", "完成")}</div><div><i></i><div><strong>振动基线更新</strong><small>2026-05-02 · 采样 12 kHz</small></div>${statusPill("low", "完成")}</div><div><i></i><div><strong>轴承更换</strong><small>2025-11-21 · 6205-2RS-C3</small></div>${statusPill("low", "验证通过")}</div></div></article></div>
    </div>
  </div>`;
}

function incidentList() {
  return state.incidents.length ? state.incidents.map(item => `<button class="incident-row ${item.id === selectedIncident()?.id ? "active" : ""}" data-incident="${e(item.id)}"><i class="risk-dot risk-dot--${e(enumValue(item.risk))}"></i><div><strong>${e(localizedSummary(item.summary))}</strong><small>${e(item.id)} · ${formatDate(item.updated_at)}</small></div><div>${statusPill(item.status)}<b>${riskLabel(item.risk)}</b></div></button>`).join("") : '<div class="empty-mini">暂无事件。请运行一个 Agent 场景。</div>';
}

function evidenceRows(incident) {
  const evidence = incident?.evidence ?? [];
  return evidence.slice(0, 10).map(item => {
    const value = typeof item.value === "number" ? item.value.toFixed(item.value < 10 ? 2 : 1) : typeof item.value === "string" ? item.value : item.value?.score != null ? `${Math.round(item.value.score * 100)}%` : "结构化证据";
    return `<div class="evidence-row"><div class="evidence-row__kind">${icon(item.kind === "vision" ? "assets" : item.kind === "safety" ? "shield" : item.kind === "sustainability" ? "leaf" : "bolt")}</div><div><strong>${e(evidenceTitleLabel(item.title))}</strong><small>${e(evidenceSourceLabel(item.source))}</small></div><b>${e(value)} ${e(item.unit ?? "")}</b><div class="confidence-bar"><i style="width:${clamp(item.confidence*100)}%"></i><span>${Math.round(item.confidence*100)}%</span></div></div>`;
  }).join("");
}

function traceView(incident) {
  return (incident?.trace ?? []).map((step, index, array) => `<div class="trace-step"><div class="trace-step__rail"><span class="trace-step__node trace-step__node--${e(step.status)}">${icon(step.status === "completed" ? "check" : "agents")}</span>${index < array.length - 1 ? '<i></i>' : ""}</div><div><div class="trace-step__meta"><b>${e(agentLabel(step.agent))}</b><time>${formatDate(step.started_at)}</time></div><strong>${e(traceActionLabel(step.action))}</strong><p>${e(traceRationaleLabel(step.rationale))}</p></div></div>`).join("");
}

function incidentsView() {
  const incident = selectedIncident();
  return `<div class="incidents-layout"><aside class="incident-list-panel"><div class="section-heading"><span>告警事件流</span><h2>工业事件</h2></div><div class="incident-list">${incidentList()}</div></aside><div class="incident-cockpit">${incident ? incidentDetail(incident) : emptyState("暂无事件", "运行 Agent 闭环以创建第一个工业事件。", "incidents")}</div></div>`;
}

function incidentDetail(incident) {
  const diagnosis = incident.diagnosis?.primary;
  const reliability = incident.reliability;
  return `<div class="incident-header"><div><div class="incident-header__meta">${statusPill(incident.status)}${statusPill(incident.risk, riskLabel(incident.risk))}<span>${e(incident.id)}</span></div><h2>${e(localizedSummary(incident.summary))}</h2><p>${e(incident.asset_id)} · 创建于 ${formatDate(incident.created_at)}</p></div><button class="secondary-action" data-nav="decision">打开决策竞技场 ${icon("arrow")}</button></div>
  <div class="incident-hero-grid"><article class="panel diagnosis-card"><header><div><span>证据驱动诊断</span><h3>主故障假设</h3></div><b>${diagnosis ? Math.round(diagnosis.probability*100) : 0}%</b></header><h2>${e(diagnosis?.fault_mode ?? "等待诊断")}</h2><p>${e(diagnosis?.rationale ?? "尚无诊断结果")}</p><div class="contradictions">${(diagnosis?.contradictions ?? []).map(item => `<span>${icon("incidents")}${e(item)}</span>`).join("") || '<span class="ok">' + icon("check") + '未发现关键证据冲突</span>'}</div></article>
  <article class="panel rul-card"><header><div><span>剩余可用寿命</span><h3>RUL 概率区间</h3></div>${statusPill(reliability?.continuation_risk ?? "low", riskLabel(reliability?.continuation_risk ?? "low"))}</header><div class="rul-bars"><div><span>P10</span><i style="width:${clamp((reliability?.rul_hours_p10 ?? 0)/(reliability?.rul_hours_p90 || 1)*100)}%"></i><b>${formatHours(reliability?.rul_hours_p10)}</b></div><div><span>P50</span><i style="width:${clamp((reliability?.rul_hours_p50 ?? 0)/(reliability?.rul_hours_p90 || 1)*100)}%"></i><b>${formatHours(reliability?.rul_hours_p50)}</b></div><div><span>P90</span><i style="width:100%"></i><b>${formatHours(reliability?.rul_hours_p90)}</b></div></div><p>置信度 ${Math.round((reliability?.confidence ?? 0)*100)}% · ${e((reliability?.limiting_factors ?? []).join("、") || "无显著限制因素")}</p></article></div>
  <div class="incident-body-grid"><article class="panel evidence-panel"><header><div><span>证据台账</span><h3>可追溯证据</h3></div><b>${incident.evidence.length} 项证据</b></header><div class="evidence-list">${evidenceRows(incident)}</div></article><article class="panel trace-panel"><header><div><span>智能体执行轨迹</span><h3>多 Agent 协同轨迹</h3></div><b>${incident.trace.length} 步</b></header><div class="trace-list">${traceView(incident)}</div></article></div>`;
}

function decisionView() {
  const incident = selectedIncident();
  if (!incident?.plan) return emptyState("暂无可比较方案", "先运行完整 Agent 闭环，系统会联合生产、库存、人员、安全与环境约束生成方案。", "decision");
  const recommended = incident.plan.options.find(item => item.id === incident.plan.recommended_option_id);
  return `<div class="decision-view"><div class="decision-head"><div><span>Human-in-the-loop decision arena</span><h2>维修方案多目标决策</h2><p>${e(localizedSummary(incident.summary))}</p></div><div class="decision-head__summary"><span>推荐方案</span><strong>${e(recommended?.title ?? "—")}</strong><small>${e(incident.plan.approval_reason)}</small></div></div>
  <div class="value-assessment-grid">${assessmentCard("人员安全", incident.safety?.score, incident.safety?.risk, "shield", incident.safety?.rationale)}${assessmentCard("系统韧性", incident.resilience?.score, incident.resilience?.spare_part_risk, "node", incident.resilience?.fallback_plan)}${assessmentCard("可持续影响", incident.sustainability?.score, "low", "leaf", `异常能耗 ${incident.sustainability?.estimated_excess_energy_kwh_per_day ?? 0} kWh/日`)}</div>
  <article class="panel decision-table-panel"><header><div><span>Multi-objective optimization</span><h3>方案竞技场</h3></div><span class="decision-weight">权重：安全 34% · 韧性 24% · 可持续 18% · 成本 12% · 停机 12%</span></header><div class="decision-table"><div class="decision-table__head"><span>方案</span><span>安全</span><span>韧性</span><span>可持续</span><span>停机</span><span>成本</span><span>风险</span><span>综合</span></div>${incident.plan.options.map(option => `<button class="decision-option ${option.id === incident.plan.recommended_option_id ? "recommended" : ""}" data-option="${e(option.id)}"><div><small>${option.id === incident.plan.recommended_option_id ? "RECOMMENDED" : "OPTION"}</small><strong>${e(option.title)}</strong><p>${e(option.description)}</p>${option.contraindications.length ? `<em>${e(option.contraindications.join("；"))}</em>` : ""}</div><b>${Math.round(option.safety_score)}</b><b>${Math.round(option.resilience_score)}</b><b>${Math.round(option.sustainability_score)}</b><span>${option.estimated_downtime_minutes} min</span><span>${formatMoney(option.estimated_cost)}</span>${statusPill(option.risk, riskLabel(option.risk))}<strong class="decision-score">${option.score.toFixed(1)}</strong></button>`).join("")}</div></article>
  <div class="decision-footer"><div><span>${icon("shield")}</span><div><strong>人工授权是强制安全边界</strong><p>系统仅提供决策支持，不直接控制生产设备。批准记录、证据、模型和工具调用均进入审计链。</p></div></div><div class="decision-actions">${enumValue(incident.status) === "awaiting_approval" ? `<button class="ghost-danger" data-request-evidence>要求补充证据</button><button class="primary-action" data-approve="${e(incident.plan.recommended_option_id)}">${icon("check")}批准推荐方案</button>` : statusPill(incident.status)}</div></div></div>`;
}

function assessmentCard(title, score, risk, iconName, text) {
  return `<article class="assessment-card"><div class="assessment-card__icon">${icon(iconName)}</div><div><span>${e(title)}</span><strong>${Math.round(score ?? 0)}<small>/100</small></strong><p>${e(text ?? "尚未评估")}</p></div>${statusPill(risk ?? "low", riskLabel(risk ?? "low"))}</article>`;
}

function workView() {
  const workOrders = state.incidents.filter(item => item.work_order).map(item => ({ ...item.work_order, incident: item }));
  const selected = workOrders.find(item => item.incident.id === state.selectedIncidentId);
  const active = selected ?? workOrders.find(item => ["approved","assigned","in_progress","verifying"].includes(enumValue(item.status))) ?? workOrders[0];
  return `<div class="work-layout"><aside class="work-list-panel"><div class="section-heading"><span>工单执行区</span><h2>维修工单</h2><small>${workOrders.length ? `共 ${workOrders.length} 张，点击左侧工单切换详情` : "等待已批准的维修方案"}</small></div><div class="work-list">${workOrders.length ? workOrders.map(item => `<button type="button" class="work-row ${active?.id === item.id ? "active" : ""}" data-work-order-incident="${e(item.incident.id)}" aria-pressed="${active?.id === item.id}"><div><strong>${e(item.id)}</strong><small>${e(item.title)}</small></div>${statusPill(item.status)}<span>${e(item.asset_id)}</span></button>`).join("") : '<div class="empty-mini">尚未创建工单</div>'}</div></aside><div class="work-detail">${active ? workOrderDetail(active) : emptyState("没有工单", "在决策竞技场批准方案后，系统会创建受治理的维修工单。", "work")}</div></div>`;
}

function workOrderDetail(order) {
  return `<div class="work-head"><div><div>${statusPill(order.status)}${statusPill(order.priority, riskLabel(order.priority))}</div><h2>${e(order.title)}</h2><p>${e(order.id)} · ${e(order.asset_id)} · ${e(order.assignee_team)}</p></div>${enumValue(order.incident.status) === "in_progress" ? `<button class="verify-action" data-verify="${e(order.incident.id)}">${icon("spark")}运行维修后验证</button>` : ""}</div>
  <div class="work-grid"><article class="panel checklist-card"><header><div><span>受控作业流程</span><h3>安全作业清单</h3></div><b>${order.checklist.length} 步</b></header><ol>${order.checklist.map((step,index) => `<li class="${index < 2 ? "done" : index === 2 ? "active" : ""}"><span>${index < 2 ? icon("check") : index + 1}</span><div><strong>${e(step)}</strong><small>${index < 2 ? "已确认" : index === 2 ? "现场执行中" : "待执行"}</small></div></li>`).join("")}</ol></article>
  <article class="mobile-work-card"><div class="mobile-frame"><header><span>${icon("arrow")}</span><div><small>工单详情</small><strong>${e(order.id)}</strong></div><i></i></header><div class="mobile-progress"><span>执行进度</span><b>40%</b><i><em></em></i></div><div class="mobile-meta"><span>设备<b>${e(order.asset_id)}</b></span><span>优先级<b>${riskLabel(order.priority)}</b></span><span>负责人<b>${e(order.assignee_team)}</b></span></div><ol>${order.mobile_steps.map((step,index) => `<li class="${index < 2 ? "done" : index === 2 ? "active" : ""}"><span>${index < 2 ? "✓" : index+1}</span><b>${e(step)}</b></li>`).join("")}</ol><button>拍照上传</button></div></article></div>
  <article class="panel safety-controls"><header><div><span>人员安全控制</span><h3>人员安全边界</h3></div></header><div>${order.safety_controls.map(item => `<span>${icon("shield")}${e(item)}</span>`).join("")}</div></article>`;
}

function sustainabilityView() {
  const s = state.sustainability ?? {};
  const energy = [11.8,12.2,12.6,13.1,14.4,15.2,14.8,13.9,13.2,12.4,12.0,11.9];
  const carbon = energy.map(value => value * .55);
  return `<div class="sustainability-view"><div class="sustainability-head"><div><span>资源与生命周期</span><h2>能耗、碳与循环维护</h2><p>将可持续价值纳入每个维修方案，而不是在决策完成后附加一张报表。</p></div>${ring(state.summary?.sustainability_index ?? 84, "可持续指数")}</div>
  <div class="kpi-grid sustainability-kpis">${kpi("今日能耗", s.energy_today_kwh ?? 0, "kWh", "覆盖受监测关键资产", "blue")}${kpi("异常能耗", s.excess_energy_kwh ?? 0, "kWh", `${s.assets_with_energy_drift ?? 0} 台资产存在漂移`, "red")}${kpi("避免能耗", s.avoided_energy_kwh ?? 0, "kWh", `避免 CO₂e ${s.avoided_co2e_kg ?? 0} kg`, "green")}${kpi("避免废弃", s.avoided_waste_kg ?? 0, "kg", `${s.circular_parts_used ?? 0} 个循环部件`, "violet")}</div>
  <div class="sustainability-grid"><article class="panel chart-card"><header><div><span>能耗分析</span><h3>设备能耗与碳排趋势</h3></div><div class="legend"><span><i class="legend__health"></i>能耗 kW</span><span><i class="legend__energy"></i>CO₂e</span></div></header>${chart(energy,["00","02","04","06","08","10","12","14","16","18","20","22"],carbon)}</article><article class="panel circularity"><header><div><span>循环维护</span><h3>部件循环策略</h3></div></header><div class="circularity__ring">${ring(72,"循环利用","small")}</div><div class="circularity__list"><span><i class="green"></i>可回收轴承钢 8.4 kg</span><span><i class="cyan"></i>再制造工具 2 套</span><span><i class="amber"></i>消耗性润滑材料 1.2 kg</span></div></article></div>
  <article class="panel sustainability-table"><header><div><span>方案环境影响</span><h3>事件环境影响明细</h3></div></header><div class="data-table"><div class="data-table__head"><span>事件</span><span>异常能耗/日</span><span>CO₂e/日</span><span>废品风险</span><span>避免废弃</span><span>置信度</span></div>${state.incidents.filter(i=>i.sustainability).map(i=>`<div><strong>${e(i.id)}</strong><span>${i.sustainability.estimated_excess_energy_kwh_per_day} kWh</span><span>${i.sustainability.estimated_excess_co2e_kg_per_day} kg</span><span>${i.sustainability.estimated_scrap_risk_kg} kg</span><span>${i.sustainability.repair_avoided_waste_kg} kg</span><b>${Math.round(i.sustainability.confidence*100)}%</b></div>`).join("") || '<div class="empty-row">暂无环境影响记录</div>'}</div></article></div>`;
}

function edgeView() {
  return `<div class="edge-view"><div class="edge-head"><div><span>跨平台边缘运行</span><h2>跨平台边缘节点</h2><p>Windows、Arch Linux、Debian 系 Linux 与 Jetson 共用统一数据契约、离线缓存和安全策略。</p></div><div class="platform-chips"><span>${icon("server")}Windows / WSL2</span><span>${icon("server")}Arch / Debian</span><span>${icon("bolt")}Jetson TensorRT</span></div></div><div class="edge-grid">${state.edgeNodes.map(node => `<article class="edge-card"><header><div class="edge-card__icon">${icon(node.platform.includes("Jetson") ? "bolt" : "server")}</div>${statusPill(node.status)}</header><h3>${e(node.name)}</h3><p>${e(node.platform)}</p><div class="edge-metrics"><div><span>CPU</span><i><em style="width:${clamp(node.cpu_percent)}%"></em></i><b>${node.cpu_percent}%</b></div><div><span>Memory</span><i><em style="width:${clamp(node.memory_percent)}%"></em></i><b>${node.memory_percent}%</b></div>${node.gpu_percent != null ? `<div><span>GPU</span><i><em style="width:${clamp(node.gpu_percent)}%"></em></i><b>${node.gpu_percent}%</b></div>` : ""}</div><div class="modalities">${node.modalities.map(item=>`<span>${e(item)}</span>`).join("")}</div><footer><span>最后在线 ${formatDate(node.last_seen_at)}</span><b>${node.power_w ? `${node.power_w} W` : "CPU fallback"}</b></footer></article>`).join("")}</div>
  <article class="panel deployment-matrix"><header><div><span>部署支持矩阵</span><h3>统一运行方式</h3></div></header><div class="data-table"><div class="data-table__head"><span>平台</span><span>推理后端</span><span>安装方式</span><span>离线模式</span><span>推荐用途</span><span>状态</span></div><div><strong>Windows 10/11</strong><span>ONNX Runtime CPU/GPU</span><span>PowerShell / Docker Desktop</span><span>支持</span><span>开发、演示、管理台</span>${statusPill("low","支持")}</div><div><strong>Arch Linux</strong><span>ONNX / CUDA</span><span>systemd / Docker</span><span>支持</span><span>研发与边缘服务器</span>${statusPill("low","支持")}</div><div><strong>Debian / Ubuntu</strong><span>ONNX / OpenVINO</span><span>systemd / Docker</span><span>支持</span><span>工业 PC 与服务器</span>${statusPill("low","支持")}</div><div><strong>Jetson Orin</strong><span>TensorRT FP16</span><span>JetPack / Docker</span><span>支持</span><span>现场多模态边缘节点</span>${statusPill("low","已验证")}</div></div></article></div>`;
}

function agentRoster() {
  const statusById = new Map(state.agents.map(item => [enumValue(item.agent), item]));
  return agentFlowOrder.map(id => ({
    id,
    ...agentProfiles[id],
    ...(statusById.get(id) ?? {
      agent: id,
      status: "idle",
      current_task: null,
      last_run_at: null,
      success_rate: null,
      average_latency_ms: null,
    }),
  }));
}


function agentSuccessText(agent) {
  const value = Number(agent?.success_rate);
  return Number.isFinite(value) ? `${Math.round(value * 100)}%` : "—";
}

function agentLatencyText(agent) {
  const value = Number(agent?.average_latency_ms);
  return Number.isFinite(value) ? `${value} ms` : "—";
}

function selectedAgentProfile() {
  const roster = agentRoster();
  return roster.find(item => item.id === state.selectedAgentId) ?? roster[0] ?? null;
}

function agentActivity(agentId) {
  const rows = [];
  state.incidents.forEach(incident => {
    (incident.trace ?? []).forEach(step => {
      if (enumValue(step.agent) !== agentId) return;
      rows.push({
        kind: "trace", incident_id: incident.id, at: step.finished_at ?? step.started_at,
        status: step.status, title: traceActionLabel(step.action), detail: traceRationaleLabel(step.rationale),
      });
    });
    (incident.tool_calls ?? []).forEach(call => {
      if (enumValue(call.agent) !== agentId) return;
      rows.push({
        kind: "tool", incident_id: incident.id, at: call.finished_at ?? call.started_at,
        status: call.status, title: `工具调用：${call.tool_name}`,
        detail: call.error ?? call.result_summary ?? "工具调用已记录",
      });
    });
  });
  return rows.sort((a, b) => new Date(b.at ?? 0) - new Date(a.at ?? 0));
}

function relatedIncidentForAgent(agentId) {
  return state.incidents.find(incident =>
    (incident.trace ?? []).some(step => enumValue(step.agent) === agentId) ||
    (incident.tool_calls ?? []).some(call => enumValue(call.agent) === agentId)
  ) ?? null;
}

function toolRiskDescription(risk) {
  return {
    read_only: "只读工具：允许智能体查询，不修改生产状态。",
    low: "低风险工具：允许在审计记录下自动执行。",
    medium: "中风险工具：需要策略检查，必要时升级人工复核。",
    high: "高风险工具：默认阻断，必须取得授权人员批准。",
  }[enumValue(risk)] ?? "工具风险等级由治理策略控制。";
}

function agentDetail(agent) {
  if (!agent) return '<article class="agent-detail panel"><div class="empty-mini">暂无智能体信息</div></article>';
  const activity = agentActivity(agent.id);
  const related = relatedIncidentForAgent(agent.id);
  const tools = (agent.tools ?? []).map(name => state.tools.find(tool => tool.name === name) ?? { name, risk: "read_only" });
  const tab = state.agentTab;
  let body = "";
  if (tab === "overview") {
    body = `<div class="agent-detail__overview"><section><span>核心使命</span><p>${e(agent.mission)}</p></section><section><span>职责边界</span><ul>${agent.responsibilities.map(item => `<li>${icon("check")}${e(item)}</li>`).join("")}</ul></section><div class="agent-io"><article><span>输入</span>${agent.inputs.map(item => `<b>${e(item)}</b>`).join("")}</article><article><span>输出</span>${agent.outputs.map(item => `<b>${e(item)}</b>`).join("")}</article></div><div class="agent-boundary">${icon("shield")}该智能体不能绕过状态机独立执行生产控制；高风险动作必须由授权人员审批。</div></div>`;
  } else if (tab === "activity") {
    body = `<div class="agent-activity">${activity.length ? activity.slice(0, 12).map(item => `<button data-agent-incident="${e(item.incident_id)}"><span class="agent-activity__dot agent-activity__dot--${e(item.status)}"></span><div><strong>${e(item.title)}</strong><p>${e(item.detail)}</p><small>${e(item.incident_id)} · ${formatDate(item.at)}</small></div>${icon("arrow")}</button>`).join("") : '<div class="agent-empty"><b>暂无执行记录</b><p>运行一个工业场景或实时检测事件后，这里会显示该智能体的真实执行轨迹。</p><button data-nav="scenarios">进入工业场景库</button></div>'}</div>`;
  } else {
    body = `<div class="agent-permissions"><div class="agent-permissions__notice">${icon("shield")}权限由工具风险等级、当前流程状态和人工审批共同决定。</div>${tools.map(tool => `<button data-agent-tool="${e(tool.name)}"><div><code>${e(tool.name)}</code><p>${e(toolRiskDescription(tool.risk))}</p></div>${statusPill(tool.risk, enumValue(tool.risk) === "read_only" ? "只读" : enumValue(tool.risk) === "high" ? "需审批" : riskLabel(tool.risk))}</button>`).join("") || '<div class="agent-empty"><b>无直接工具权限</b><p>该智能体只处理上游结构化数据，不直接调用外部系统。</p></div>'}</div>`;
  }
  return `<article class="agent-detail panel"><header><div class="agent-detail__identity"><span class="agent-status__icon">${icon(agent.icon ?? "agents")}</span><div><small>${e(agent.stage)}</small><h3>${e(agent.label)}</h3><p>${e(agent.current_task ?? "当前无运行任务")}</p></div></div>${statusPill(agent.status)}</header><div class="agent-detail__metrics"><span>成功率<b>${agentSuccessText(agent)}</b></span><span>平均延迟<b>${agentLatencyText(agent)}</b></span><span>最近运行<b>${formatDate(agent.last_run_at)}</b></span></div><nav class="agent-tabs"><button class="${tab === "overview" ? "active" : ""}" data-agent-tab="overview">职责与输入输出</button><button class="${tab === "activity" ? "active" : ""}" data-agent-tab="activity">执行记录 ${activity.length ? `<i>${activity.length}</i>` : ""}</button><button class="${tab === "permissions" ? "active" : ""}" data-agent-tab="permissions">工具权限</button></nav>${body}<footer><button class="secondary-action" data-agent-ask="${e(agent.id)}">${icon("chat")}询问此智能体</button>${related ? `<button class="primary-action" data-agent-incident="${e(related.id)}">查看关联事件 ${icon("arrow")}</button>` : `<button class="primary-action" data-nav="scenarios">运行受治理闭环 ${icon("arrow")}</button>`}</footer></article>`;
}

function agentsView() {
  const roster = agentRoster();
  const query = state.agentFilter.trim().toLowerCase();
  const filtered = roster.filter(agent => {
    const matchesQuery = !query || `${agent.label} ${agent.stage} ${agent.mission} ${agent.responsibilities.join(" ")}`.toLowerCase().includes(query);
    const matchesStatus = state.agentStatusFilter === "all" || enumValue(agent.status) === state.agentStatusFilter;
    return matchesQuery && matchesStatus;
  });
  const selected = selectedAgentProfile();
  const statusCounts = roster.reduce((acc, agent) => { const key = enumValue(agent.status); acc[key] = (acc[key] ?? 0) + 1; return acc; }, {});
  const selectedTool = state.tools.find(tool => tool.name === state.selectedToolName) ?? null;
  const selectedModel = state.models.find(model => (model.id ?? model.metadata?.id) === state.selectedModelId) ?? null;
  return `<div class="agents-view"><div class="agents-head"><div><span>受治理多智能体运行时</span><h2>工业智能体协同系统</h2><p>选择任一智能体可查看职责、输入输出、真实执行记录和工具权限。专业智能体不能脱离协调器独立控制生产设备。</p></div><div class="agents-head__actions"><button class="secondary-action" data-nav="scenarios">${icon("play")}运行受治理闭环</button><button class="secondary-action" data-assistant>${icon("chat")}询问智能体解释</button></div></div>
  <article class="agent-architecture"><div class="agent-architecture__user">${icon("user")}<span>操作员请求 / 设备事件</span></div><div class="agent-flow">${agentFlowOrder.map((id,index)=>{const profile=agentProfiles[id];return `<button class="${selected?.id === id ? "active" : ""}" data-agent-select="${e(id)}"><span>${index+1}</span><b>${e(profile.stage)}</b><small>${e(profile.label.replace("智能体", ""))}</small>${index<agentFlowOrder.length-1?icon("arrow"):""}</button>`}).join("")}</div><div class="agent-architecture__layers"><button data-agent-layer="tools"><span>工具层</span><b>资产 · MES · 库存 · 人员 · 工单 · 搜索</b></button><button data-agent-layer="knowledge"><span>知识层</span><b>FMEA · 手册 · 安全规范 · 历史案例</b></button><button data-agent-layer="governance"><span>治理层</span><b>审批 · 权限 · 证据 · 审计 · 回滚</b></button></div></article>
  <div class="agent-toolbar"><label>${icon("search")}<input data-agent-filter value="${e(state.agentFilter)}" placeholder="搜索智能体、职责或能力" /></label><div><button class="${state.agentStatusFilter === "all" ? "active" : ""}" data-agent-status="all">全部 ${roster.length}</button><button class="${state.agentStatusFilter === "running" ? "active" : ""}" data-agent-status="running">运行中 ${statusCounts.running ?? 0}</button><button class="${state.agentStatusFilter === "waiting" ? "active" : ""}" data-agent-status="waiting">等待 ${statusCounts.waiting ?? 0}</button><button class="${state.agentStatusFilter === "idle" ? "active" : ""}" data-agent-status="idle">空闲 ${statusCounts.idle ?? 0}</button></div></div>
  <div class="agent-workspace"><div class="agent-status-grid">${filtered.map(agent=>`<button type="button" class="agent-card ${selected?.id === agent.id ? "active" : ""}" data-agent-select="${e(agent.id)}" aria-pressed="${selected?.id === agent.id}"><header><div class="agent-status__icon">${icon(agent.icon ?? "agents")}</div>${statusPill(agent.status)}</header><span>${e(agent.stage)}</span><h3>${e(agent.label)}</h3><p>${e(agent.mission)}</p><div><span>成功率<b>${agentSuccessText(agent)}</b></span><span>平均延迟<b>${agentLatencyText(agent)}</b></span></div><em>查看详情 ${icon("arrow")}</em></button>`).join("") || '<div class="agent-empty"><b>没有匹配的智能体</b><p>清除搜索条件或切换状态筛选。</p></div>'}</div>${agentDetail(selected)}</div>
  <div class="agents-lower"><article class="panel tool-catalog"><header><div><span>工具权限</span><h3>工具权限目录</h3></div><b>${state.tools.length} 项</b></header><div>${state.tools.map(tool=>`<button class="${selectedTool?.name === tool.name ? "active" : ""}" data-agent-tool="${e(tool.name)}"><code>${e(tool.name)}</code>${statusPill(tool.risk, enumValue(tool.risk) === "read_only" ? "只读" : enumValue(tool.risk) === "high" ? "需审批" : riskLabel(tool.risk))}</button>`).join("")}</div>${selectedTool ? `<aside><strong>${e(selectedTool.name)}</strong><p>${e(toolRiskDescription(selectedTool.risk))}</p><button data-agent-select="${e(Object.values(agentProfiles).find(profile => profile.tools.includes(selectedTool.name)) ? Object.keys(agentProfiles).find(id => agentProfiles[id].tools.includes(selectedTool.name)) : "coordinator")}">查看相关智能体</button></aside>` : ""}</article><article class="panel model-catalog"><header><div><span>模型运行时</span><h3>模型运行时</h3></div><b>${state.models.length} 个</b></header><div>${state.models.map(model=>{const id=model.id ?? model.metadata?.id ?? "model";return `<button class="${selectedModel && (selectedModel.id ?? selectedModel.metadata?.id) === id ? "active" : ""}" data-agent-model="${e(id)}"><div><strong>${e(id)}</strong><small>${e(model.role ?? model.metadata?.role ?? "工业推理")}</small></div><span>${e(model.runtime?.join?.(" / ") ?? model.metadata?.runtime?.join?.(" / ") ?? "runtime")}</span></button>`}).join("") || '<div class="empty-mini">模型目录暂未返回</div>'}</div>${selectedModel ? `<aside><strong>${e(selectedModel.id ?? selectedModel.metadata?.id)}</strong><p>运行时：${e(selectedModel.runtime?.join?.(" / ") ?? selectedModel.metadata?.runtime?.join?.(" / ") ?? "未声明")}</p><p>角色：${e(selectedModel.role ?? selectedModel.metadata?.role ?? "工业推理")}</p></aside>` : ""}</article></div></div>`;
}

function governanceView() {
  return `<div class="governance-view"><div class="governance-head"><div><span>人机共治与可追溯治理</span><h2>安全、权限与审计</h2><p>确保 AI 可以解释、可以拒绝、可以降级，但不能绕过人类授权控制生产设备。</p></div>${ring(state.summary?.human_safety_index ?? 91,"治理成熟度")}</div>
  <div class="policy-grid"><article><div>${icon("shield")}</div><span>治理规则 01</span><h3>高风险工具必须人工批准</h3><p>工单下发、生产变更和设备控制类工具默认阻断，只有授权人员批准后才能执行。</p></article><article><div>${icon("assets")}</div><span>治理规则 02</span><h3>证据不足必须拒识</h3><p>传感器质量、模态冲突或置信度不满足门槛时，Agent 必须要求补采，不能给出确定性结论。</p></article><article><div>${icon("work")}</div><span>治理规则 03</span><h3>维修完成不等于闭环</h3><p>只有维修后数据验证恢复，工单才允许关闭；否则自动重开并保留前后证据。</p></article><article><div>${icon("node")}</div><span>治理规则 04</span><h3>边缘离线安全降级</h3><p>网络中断时继续质量门控、阈值保护与本地缓存；恢复后按序同步，避免证据丢失。</p></article></div>
  <article class="panel audit-panel"><header><div><span>不可篡改审计链</span><h3>审计事件</h3></div><b>${state.audit.length} 条记录</b></header><div class="data-table audit-table"><div class="data-table__head"><span>时间</span><span>类别</span><span>操作者</span><span>动作</span><span>对象</span><span>等级</span></div>${state.audit.map(item=>`<div><span>${formatDate(item.timestamp)}</span><strong>${e(item.category)}</strong><span>${e(item.actor)}</span><span>${e(item.action)}</span><code>${e(item.object_id)}</code>${statusPill(item.severity,riskLabel(item.severity))}</div>`).join("")}</div></article></div>`;
}

function emptyState(title, text, iconName) {
  return `<div class="empty-state"><span>${icon(iconName)}</span><h2>${e(title)}</h2><p>${e(text)}</p><button class="primary-action" data-nav="command">返回运行总览</button></div>`;
}

function currentView() {
  return {
    command: commandView,
    data: dataView,
    scenarios: scenarioView,
    asset: assetsView,
    incident: incidentsView,
    decision: decisionView,
    work: workView,
    sustainability: sustainabilityView,
    edge: edgeView,
    agents: agentsView,
    governance: governanceView,
  }[state.view]?.() ?? commandView();
}

function render() {
  const root = document.querySelector("#root");
  if (state.loading && !state.summary) {
    root.className = "boot";
    root.innerHTML = '<div class="boot__mark"><span></span></div><strong>ForgeGuard Nexus 5.0</strong><small>正在加载跨平台工业智能体运行时…</small>';
    return;
  }
  root.className = "";
  root.innerHTML = shell(currentView());
  const overlay = document.querySelector("#overlay-root");
  if (overlay) overlay.innerHTML = `${assistantDrawer(selectedIncident())}${searchModal()}${helpModal()}`;
  bindEvents();
}

async function mutate(action) {
  if (state.busy) return;
  state.busy = true;
  state.error = null;
  render();
  try {
    await action();
    await loadAll();
  } catch (error) {
    state.error = error.message;
    state.busy = false;
    render();
    return;
  }
  state.busy = false;
  render();
}


function stopLiveSimulatorLoop() {
  if (liveTimer) window.clearInterval(liveTimer);
  liveTimer = null;
}

function startLiveSimulatorLoop() {
  stopLiveSimulatorLoop();
  if (!state.liveSession || state.liveSession.source !== "simulator" || state.liveSession.status !== "running") return;
  const tick = async () => {
    if (state.liveTickBusy || !state.liveSession) return;
    state.liveTickBusy = true;
    try {
      state.liveSession = await api.simulateLive(state.liveSession.id, {
        fault_mode: state.liveFaultMode,
        sensor_fault: state.liveSensorFault,
        severity: state.liveFaultMode === "normal" ? 0.12 : 0.58,
        duration_seconds: 0.5,
      });
      const index = state.liveSessions.findIndex(item => item.id === state.liveSession.id);
      if (index >= 0) state.liveSessions[index] = state.liveSession;
      if (state.view === "data" && state.dataMode === "live") render();
    } catch (error) {
      state.error = `实时检测中断：${error.message}`;
      stopLiveSimulatorLoop();
      render();
    } finally {
      state.liveTickBusy = false;
    }
  };
  tick();
  liveTimer = window.setInterval(tick, 1000);
}

function openSearchResult(type, id) {
  state.searchOpen = false;
  state.searchQuery = "";
  if (type === "page") state.view = id;
  if (type === "scenario") {
    state.scenario = id;
    state.view = "scenarios";
  }
  if (type === "asset") {
    state.selectedAssetId = id;
    state.view = "asset";
  }
  if (type === "incident") {
    state.selectedIncidentId = id;
    state.view = "incident";
  }
  if (type === "work") {
    state.selectedIncidentId = id;
    state.view = "work";
  }
  if (type === "help") {
    if (id === "realtime" || id === "csv") {
      state.view = "data";
      state.dataMode = id === "csv" ? "csv" : "live";
    } else {
      state.helpOpen = true;
    }
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
  render();
}

function bindEvents() {
  document.querySelectorAll("[data-open-search]").forEach(button => button.addEventListener("click", () => {
    state.searchOpen = true;
    state.searchQuery = "";
    state.searchIndex = 0;
    render();
    window.setTimeout(() => document.querySelector("[data-search-input]")?.focus(), 0);
  }));
  document.querySelectorAll("[data-close-search]").forEach(button => button.addEventListener("click", () => {
    state.searchOpen = false;
    render();
  }));
  document.querySelector("[data-search-input]")?.addEventListener("input", event => {
    state.searchQuery = event.target.value;
    state.searchIndex = 0;
    render();
    window.setTimeout(() => {
      const input = document.querySelector("[data-search-input]");
      if (input) { input.focus(); input.setSelectionRange(input.value.length, input.value.length); }
    }, 0);
  });
  document.querySelectorAll("[data-search-type]").forEach(button => button.addEventListener("click", () => openSearchResult(button.dataset.searchType, button.dataset.searchId)));
  document.querySelectorAll("[data-help]").forEach(button => button.addEventListener("click", () => { state.helpOpen = true; render(); }));
  document.querySelectorAll("[data-close-help]").forEach(button => button.addEventListener("click", () => { state.helpOpen = false; render(); }));
  document.querySelectorAll("[data-help-nav]").forEach(button => button.addEventListener("click", () => { state.helpOpen = false; state.view = button.dataset.helpNav; render(); }));
  document.querySelectorAll("[data-data-mode]").forEach(button => button.addEventListener("click", () => { state.dataMode = button.dataset.dataMode; render(); }));
  document.querySelectorAll("[data-quick-mode]").forEach(button => button.addEventListener("click", () => { state.view = "data"; state.dataMode = button.dataset.quickMode; window.scrollTo({ top: 0 }); render(); }));
  document.querySelector("[data-scenario-filter]")?.addEventListener("input", event => {
    state.scenarioFilter = event.target.value;
    render();
    window.setTimeout(() => {
      const input = document.querySelector("[data-scenario-filter]");
      if (input) { input.focus(); input.setSelectionRange(input.value.length, input.value.length); }
    }, 0);
  });
  document.querySelectorAll("[data-scenario-category]").forEach(button => button.addEventListener("click", () => { state.scenarioCategory = button.dataset.scenarioCategory; render(); }));
  document.querySelectorAll("[data-select-scenario]").forEach(button => button.addEventListener("click", () => { state.scenario = button.dataset.selectScenario; render(); }));
  document.querySelectorAll("[data-run-scenario]").forEach(button => button.addEventListener("click", () => mutate(async () => {
    state.scenario = button.dataset.runScenario;
    const incident = await api.runDemo(state.scenario);
    state.selectedIncidentId = incident.id;
    state.view = "incident";
  })));
  document.querySelectorAll("[data-export]").forEach(button => button.addEventListener("click", () => {
    const kind = button.dataset.export;
    if (kind === "summary") downloadJson(`forgeguard-summary-${new Date().toISOString().slice(0,10)}.json`, { generated_at: new Date().toISOString(), summary: state.summary, assets: state.assets, open_incidents: state.incidents.filter(item => enumValue(item.status) !== "resolved"), edge_nodes: state.edgeNodes });
    if (kind === "incident" && selectedIncident()) downloadJson(`${selectedIncident().id}-evidence.json`, selectedIncident());
    if (kind === "csv" && state.csvReport) downloadJson(`${state.csvReport.id}.json`, state.csvReport);
  }));
  document.querySelector("[data-live-start]")?.addEventListener("submit", event => mutate(async () => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const session = await api.startLive({
      asset_id: String(form.get("asset_id")),
      source: String(form.get("source")),
      sample_rate_hz: Number(form.get("sample_rate_hz")),
      rpm: Number(form.get("rpm")),
      load_percent: Number(form.get("load_percent")),
      open_incident: form.get("open_incident") === "on",
    });
    state.liveSession = session;
    state.liveSessions = [session, ...state.liveSessions.filter(item => item.id !== session.id)];
    state.view = "data";
    state.dataMode = "live";
    if (session.source === "simulator") window.setTimeout(startLiveSimulatorLoop, 0);
  }));
  document.querySelector("[data-live-stop]")?.addEventListener("click", () => mutate(async () => {
    stopLiveSimulatorLoop();
    state.liveSession = await api.stopLive(state.liveSession.id);
  }));
  document.querySelector("[data-live-fault]")?.addEventListener("change", event => { state.liveFaultMode = event.target.value; });
  document.querySelector("[data-live-sensor-fault]")?.addEventListener("change", event => { state.liveSensorFault = event.target.value; });
  document.querySelector("[data-csv-form]")?.addEventListener("submit", event => mutate(async () => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const file = form.get("file");
    if (file instanceof File && file.size > CSV_MAX_BYTES) {
      throw new Error("CSV 文件超过 128 MB，无法上传分析。");
    }
    form.set("create_incident", form.get("create_incident") === "on" ? "true" : "false");
    state.csvReport = await api.analyzeCsv(form);
    state.csvReports = [state.csvReport, ...state.csvReports.filter(item => item.id !== state.csvReport.id)];
    state.view = "data";
    state.dataMode = "csv";
  }));
  document.querySelectorAll("[data-csv-report]").forEach(button => button.addEventListener("click", () => {
    state.csvReport = state.csvReports.find(item => item.id === button.dataset.csvReport) ?? state.csvReport;
    render();
  }));
  document.querySelectorAll("[data-open-incidents]").forEach(button => button.addEventListener("click", event => {
    event.preventDefault();
    event.stopPropagation();
    state.view = "incident";
    if (!state.selectedIncidentId && state.incidents.length) state.selectedIncidentId = state.incidents[0].id;
    window.scrollTo({ top: 0, behavior: "smooth" });
    render();
  }));
  document.querySelectorAll("[data-work-order-incident]").forEach(button => button.addEventListener("click", event => {
    event.preventDefault();
    state.selectedIncidentId = button.dataset.workOrderIncident;
    state.view = "work";
    render();
  }));
  document.querySelectorAll("[data-nav]").forEach(button => button.addEventListener("click", () => {
    state.view = button.dataset.nav;
    window.scrollTo({ top: 0, behavior: "smooth" });
    render();
  }));
  document.querySelectorAll("[data-asset]").forEach(button => button.addEventListener("click", () => {
    state.selectedAssetId = button.dataset.asset;
    if (button.closest(".factory-map")) state.view = "asset";
    render();
  }));
  document.querySelectorAll("[data-incident]").forEach(button => button.addEventListener("click", () => {
    state.selectedIncidentId = button.dataset.incident;
    if (button.dataset.nav) state.view = button.dataset.nav;
    render();
  }));
  document.querySelector("[data-scenario]")?.addEventListener("change", event => { state.scenario = event.target.value; });
  document.querySelectorAll("[data-run-demo]").forEach(button => button.addEventListener("click", () => mutate(async () => {
    const incident = await api.runDemo(state.scenario);
    state.selectedIncidentId = incident.id;
    state.view = "incident";
  })));
  document.querySelector("[data-approve]")?.addEventListener("click", event => mutate(async () => {
    await api.approve(selectedIncident().id, event.currentTarget.dataset.approve, "approve");
    state.view = "work";
  }));
  document.querySelector("[data-request-evidence]")?.addEventListener("click", () => mutate(async () => {
    const incident = selectedIncident();
    await api.approve(incident.id, incident.plan.recommended_option_id, "request_evidence");
    state.view = "incident";
  }));
  document.querySelector("[data-verify]")?.addEventListener("click", event => mutate(async () => {
    await api.complete(event.currentTarget.dataset.verify, state.scenario);
    state.view = "incident";
  }));
  document.querySelector("[data-agent-filter]")?.addEventListener("input", event => {
    state.agentFilter = event.target.value;
    render();
    window.setTimeout(() => {
      const input = document.querySelector("[data-agent-filter]");
      if (input) { input.focus(); input.setSelectionRange(input.value.length, input.value.length); }
    }, 0);
  });
  document.querySelectorAll("[data-agent-status]").forEach(button => button.addEventListener("click", () => {
    state.agentStatusFilter = button.dataset.agentStatus;
    render();
  }));
  document.querySelectorAll("[data-agent-select]").forEach(button => button.addEventListener("click", () => {
    state.selectedAgentId = button.dataset.agentSelect;
    state.agentTab = "overview";
    render();
  }));
  document.querySelectorAll("[data-agent-tab]").forEach(button => button.addEventListener("click", () => {
    state.agentTab = button.dataset.agentTab;
    render();
  }));
  document.querySelectorAll("[data-agent-incident]").forEach(button => button.addEventListener("click", () => {
    state.selectedIncidentId = button.dataset.agentIncident;
    state.view = "incident";
    window.scrollTo({ top: 0, behavior: "smooth" });
    render();
  }));
  document.querySelectorAll("[data-agent-ask]").forEach(button => button.addEventListener("click", () => {
    const profile = agentProfiles[button.dataset.agentAsk];
    state.assistantDraft = profile ? `请解释${profile.label}的职责、当前状态、最近执行证据和权限边界。` : "请解释当前智能体状态。";
    state.assistantOpen = true;
    render();
  }));
  document.querySelectorAll("[data-agent-tool]").forEach(button => button.addEventListener("click", () => {
    state.selectedToolName = button.dataset.agentTool;
    state.agentTab = "permissions";
    const owner = Object.keys(agentProfiles).find(id => agentProfiles[id].tools.includes(state.selectedToolName));
    if (owner) state.selectedAgentId = owner;
    render();
  }));
  document.querySelectorAll("[data-agent-model]").forEach(button => button.addEventListener("click", () => {
    state.selectedModelId = button.dataset.agentModel;
    render();
  }));
  document.querySelectorAll("[data-agent-layer]").forEach(button => button.addEventListener("click", () => {
    const layer = button.dataset.agentLayer;
    if (layer === "tools") { state.selectedAgentId = "coordinator"; state.agentTab = "permissions"; }
    if (layer === "knowledge") { state.selectedAgentId = "knowledge"; state.agentTab = "overview"; }
    if (layer === "governance") { state.selectedAgentId = "governance"; state.agentTab = "overview"; }
    render();
  }));
  document.querySelectorAll("[data-assistant]").forEach(button => button.addEventListener("click", () => {
    state.assistantOpen = true;
    render();
  }));
  document.querySelectorAll("[data-close-assistant]").forEach(button => button.addEventListener("click", () => {
    state.assistantOpen = false;
    render();
  }));
  document.querySelector(".assistant__form")?.addEventListener("submit", async event => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const query = String(form.get("query") ?? "").trim();
    if (!query) return;
    state.assistantDraft = "";
    state.assistantMessages.push({ role: "user", text: query });
    state.assistantBusy = true;
    render();
    try {
      const response = await api.assistant({
        query,
        asset_id: state.selectedAssetId,
        incident_id: selectedIncident()?.id ?? null,
        language: "zh-CN",
      });
      state.assistantMessages.push({ role: "assistant", text: `${response.answer}\n\n建议：${response.recommended_actions.join("；")}` });
    } catch (error) {
      state.assistantMessages.push({ role: "assistant", text: `请求失败：${error.message}` });
    } finally {
      state.assistantBusy = false;
      render();
    }
  });
}

window.ForgeGuardUI = {
  openSearch() {
    state.searchOpen = true;
    state.searchQuery = "";
    state.searchIndex = 0;
    render();
    window.setTimeout(() => document.querySelector("[data-search-input]")?.focus(), 0);
  },
  openView(view) {
    state.view = view;
    if (view === "incident" && !state.selectedIncidentId && state.incidents.length) state.selectedIncidentId = state.incidents[0].id;
    window.scrollTo({ top: 0, behavior: "smooth" });
    render();
  },
};

document.addEventListener("keydown", event => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    state.searchOpen = true;
    state.searchQuery = "";
    state.searchIndex = 0;
    render();
    window.setTimeout(() => document.querySelector("[data-search-input]")?.focus(), 0);
    return;
  }
  if (event.key === "Escape") {
    if (state.searchOpen || state.helpOpen || state.assistantOpen) {
      state.searchOpen = false;
      state.helpOpen = false;
      state.assistantOpen = false;
      render();
    }
    return;
  }
  if (state.searchOpen && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
    event.preventDefault();
    const count = document.querySelectorAll("[data-search-type]").length;
    if (count) {
      state.searchIndex = (state.searchIndex + (event.key === "ArrowDown" ? 1 : -1) + count) % count;
      render();
      window.setTimeout(() => document.querySelector("[data-search-input]")?.focus(), 0);
    }
    return;
  }
  if (event.key === "Enter" && state.searchOpen) {
    event.preventDefault();
    const options = [...document.querySelectorAll("[data-search-type]")];
    const selected = options[state.searchIndex] ?? options[0];
    if (selected) openSearchResult(selected.dataset.searchType, selected.dataset.searchId);
  }
});

loadAll().then(() => {
  if (state.liveSession?.source === "simulator" && state.liveSession.status === "running") startLiveSimulatorLoop();
});
