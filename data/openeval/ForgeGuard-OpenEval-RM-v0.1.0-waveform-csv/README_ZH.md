# ForgeGuard OpenEval-RM 波形 CSV

本目录由 `forgeguard_openeval_rm_v0_1.npz` 转换得到，共 448 个单样本 CSV。

## CSV 格式

每个波形文件包含两列：

```csv
timestamp,acceleration_x
0.000000000,...
0.000083333,...
```

- 采样率：12000 Hz
- 每条样本：2048 点
- 记录时长：0.170666667 秒
- 最后一个时间戳：0.170583333 秒
- 目录结构：`split/fault_mode/sample_id__fault_mode.csv`

`waveform_index.csv` 保存样本元数据、相对路径和每个 CSV 的 SHA-256。

## 导入 ForgeGuard

- 信号列：`acceleration_x`
- 采样率：`12000`
- 窗口大小：`2048`
- 一个 CSV 对应一个故障状态样本，不要跨文件拼接后再解释单一故障。

## 科研边界

这是物理规律驱动的合成数据，用于软件回归、鲁棒性测试和公开基线演示；
不能作为真实工厂准确率或真实实验结果的证据。
