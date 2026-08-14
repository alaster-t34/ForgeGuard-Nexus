# ForgeGuard Nexus v0.7.9 CSV 限制审计

本文件记录工程内所有实际读取或生成 CSV 的代码路径。限制中的 MB 均按 MiB 计算，即 `1 MiB = 1,048,576` 字节。

## 1. 历史 CSV 网页/API 分析

代码入口：

- `frontend/app.js` 文件选择与客户端预检查；
- `backend/app/api/routes.py` 的 `POST /api/v1/analysis/csv`；
- `backend/app/analysis/service.py` 的解析和信号列选择。

限制：

| 项目 | v0.7.9 限制 |
|---|---|
| 文件大小 | 最大 128 MiB |
| 非空数据行 | 最大 1,000,000 行，不含表头 |
| 列数 | 最大 256 列 |
| 单字段长度 | 最大 1 MiB 字符 |
| 最少信号值 | 64 个有限数值 |
| 文件扩展名 | `.csv`、`.txt` 或无扩展名 |
| 编码 | UTF-8、UTF-8 BOM、GB18030、带 BOM 的 UTF-16 |
| 分隔符 | 逗号、分号、Tab、竖线 |
| 表头 | 可有可无 |

自动选列优先匹配 `acceleration_x`、`acceleration`、`vibration`、`signal`、`amplitude`、`sensor_value`、`value`、`ch1`。没有这些名称时，选择有限数值覆盖率最高的列；无表头并列时选择靠后的列，以避免两列波形中的时间戳被优先选中。也可以在界面中显式填写列名或从 0 开始的列序号。

包含 `sample_id` 的合并长表可以通过大小与格式检查，但当前分析报告仍把选中的信号列视为一条连续波形。为避免窗口跨越两条原始波形的边界，正式评测时应先按 `sample_id` 筛选单条波形，或使用原始逐波形 CSV；系统会在报告中给出这一警告。

上传路由最多只读取“上限 + 1 字节”，不会先无边界读完整文件。解析采用两遍扫描，只保留最终信号列，不再把整个 CSV 转成二维 Python 字符串列表。

机器可读配置：

```text
GET /api/v1/analysis/csv/limits
```

## 2. 边缘节点 CSV 回放

代码入口：`edge-node/forgeguard_edge/csv_adapter.py`。

限制与历史分析一致：128 MiB、1,000,000 行、256 列、单字段 1 MiB，支持 UTF-8、GB18030、带 BOM 的 UTF-16和四种分隔符。

v0.7.8 会遍历每个单元格，把时间戳和振动值都追加到同一信号数组。v0.7.9 改为只读取一个信号列，并提供：

```text
--signal-column acceleration_x
```

未指定时使用与网页分析相同的优先列名规则。`--channel` 仍表示发送给服务端的通道名称，两者含义不再混用。

## 3. OpenEval 提交文件

代码入口：`backend/app/benchmark/scoring.py`。

| 项目 | 限制 |
|---|---|
| 文件大小 | 最大 10 MiB |
| 数据行 | 最大 100,000 行 |
| 列数 | 解析器上限 16 列，实际必须恰好 3 列 |
| 表头 | 必须严格为 `sample_id,predicted_label,confidence` |
| 编码 | UTF-8/UTF-8 BOM 或 GB18030 |
| 分隔符 | 逗号 |
| 置信度 | 0 到 1 |
| 样本约束 | 不得重复，且必须与测试集样本一一对应 |

## 4. XJTU-SY 公开数据适配器

代码入口：`backend/app/benchmark/external_datasets.py`。

每个 CSV 最大 64 MiB、1,000,000 行、2 至 64 列；使用逗号分隔、UTF-8/UTF-8 BOM，并跳过第一行表头。前两列分别作为水平和垂直振动。超过限制时明确报错，不再静默跳过列结构异常的文件。

## 5. OpenEval 索引与提交模板生成

代码入口：

- `backend/app/benchmark/datasets.py` 生成 `index.csv`；
- `backend/app/benchmark/scoring.py` 生成 `submission_template.csv`。

`index.csv` 使用 UTF-8、逗号分隔和固定表头，最大 32 MiB、100,000 行、32 列。生成前限制总样本数，生成后再次检查文件大小。提交模板沿用 OpenEval 提交文件的 10 MiB 限制。

## 6. Jetson OpenEval 回放脚本

代码入口：`scripts/jetson/replay-openeval.sh`。

脚本读取受控生成的 `index.csv` 时再次检查 32 MiB、100,000 行、32 列以及必需字段。v0.7.8 把一段波形横向写成一行数千列；v0.7.9 改为带 `acceleration_x` 表头的单列纵向 CSV，因此仍可由新的边缘回放适配器直接读取，并且不会触发 256 列上限。转速和负载随后从已生成的 JSON 清单读取，不再重复无边界读取索引 CSV。

## 7. 不属于 CSV 限制的路径

- `runtime-data/analysis-reports` 保存 JSON 报告，不是 CSV；
- OpenEval 波形主体 `forgeguard_openeval_rm_v0_1.npz` 是压缩 NumPy 数组；
- CWRU、Paderborn 适配器读取 MATLAB 文件；
- MVTec 适配器读取图片目录。

## 8. 验证要求

v0.7.9 测试覆盖：信号列自动选择、中文表头/GB18030、UTF-16 BOM、列数超限、OpenEval 提交表头、边缘回放不混入时间戳，以及 Python 3.12 发现脚本的实际探测结果。
