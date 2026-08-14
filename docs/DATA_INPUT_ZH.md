# 实时检测与 CSV 分析说明

ForgeGuard 提供两种数据入口。它们不是两个互不相干的演示模块，而是共享相同的数据质量门控、特征提取、模型推理、告警创建和证据保存机制。

## 实时检测

适合连续采集。软件先创建一个会话，再接收一个个数据窗。

### 内置演示

在“数据检测与分析 → 实时检测”选择“内置实时演示”。该模式用于验证软件链路，不代表真实物理实验。

### 外部 HTTP 上传

创建来源为“外部传感器/网关”的会话后，向以下接口发送数据：

```text
POST /api/v1/analysis/live/sessions/{session_id}/frames
```

请求体：

```json
{
  "samples": [0.01, 0.02, -0.01],
  "rpm": 1800,
  "load_percent": 70,
  "temperature_c": 42.5,
  "metadata": {
    "sensor": "drive-end radial",
    "unit": "g"
  }
}
```

### 串口采集

```bash
PYTHONPATH=edge-node python -m forgeguard_edge.cli stream-live-serial \
  --port /dev/ttyUSB0 \
  --server http://127.0.0.1:8000 \
  --asset-id FG-BRG-001 \
  --sample-rate 12000 \
  --window-size 2048
```

### 把 CSV 按实时速度回放

```bash
PYTHONPATH=edge-node python -m forgeguard_edge.cli stream-live-csv vibration.csv \
  --server http://127.0.0.1:8000 \
  --asset-id FG-BRG-001 \
  --sample-rate 12000 \
  --window-size 2048 \
  --hop-size 1024 \
  --signal-column acceleration_x \
  --interval 0.5
```

该命令适合比赛演示和离线采集数据的准实时复现。它仍应标注为“文件回放”，不能表述为真实在线传感器采集。

## CSV 文件分析

适合历史数据、公开数据集、台架导出和设备离线采样。

推荐格式：

```csv
timestamp,acceleration_x
0.000000,0.0132
0.000083,0.0151
0.000167,-0.0067
```

操作时必须填写真实采样率。转速、负载不确定时应明确标注未知或使用有来源的实验元数据，不应随意填写。

### 文件限制

- 最大 128 MiB；
- 最大 1,000,000 个非空数据行；
- 最大 256 列；
- 单字段最大 1 MiB 字符；
- 编码支持 UTF-8/UTF-8 BOM、GB18030、带 BOM 的 UTF-16；
- 分隔符支持逗号、分号、Tab 和竖线；
- 表头可选，但至少需要 64 个有限数值信号点。

多列文件会优先识别 `acceleration_x` 等常见信号列。长表数据集应显式选择 `acceleration_x`，以免把转速、负载或标签字段当作信号。完整边界见 `CSV_LIMITS_AUDIT_ZH.md`。

分析结果包括：

- 总样本数和时长；
- 窗口数量；
- 通过/拒绝质量检查的窗口；
- 每个窗口的类别、置信度和异常概率；
- 主导类别；
- 可选告警编号；
- JSON 报告和证据记录。

报告保存在：

```text
runtime-data/analysis-reports/
```

## 关键边界

- 实时检测不等于模型永久正确；
- CSV 文件的标签、采样率和工况必须来自真实元数据；
- 数据质量不合格时，系统允许拒绝诊断；
- 模拟数据、公开数据回放和物理台架结果必须分开标注；
- 当前默认 HGB 模型是 CPU 基线，不应宣传为 TensorRT 神经网络。
