# 第三、四问：20260912 新版演练代码

当前默认分别为 **`problem3_v5_continuous`**、**`problem4_v5_visibility_discovery`**。用户确认该演练包是实际使用版本，本次按原包迁入生产目录，未重新选型或调参。

| 查什么 | 文件 |
|---|---|
| 原演练交付件 | [releases 中的原包](../../releases/README.md) |
| 原路径、新路径、版本与 ZIP 指纹 | [integration_manifest.json](integration_manifest.json) |
| 原包代码指纹、冻结参数 | [source_manifest.json](source_manifest.json)、[candidate_freeze.json](candidate_freeze.json) |
| 原包整体文件清单 | [package_manifest.json](package_manifest.json) |
| 原包验证说明 | [package_validation.md](package_validation.md) |
| 原包 7000 例汇总及证据边界 | [package_benchmark.md](package_benchmark.md)、[第三问 JSON](problem3_7000_summary.json)、[第四问 JSON](problem4_7000_summary.json) |
| 本次源码与动作等价核验 | [integration_verification.json](integration_verification.json) |
| 仓库重命名与旧压缩包清单 | [repository_cleanup.json](repository_cleanup.json) |

原包报告每问 7000/7000 例全清，平均分别为 186.1942、426.4489 秒/源。这里是原包携带的本地汇总，未包含逐例私有记录；本次没有重跑 7000 例、补做历史重叠核对或将该样本池称为独立留出集。第四问在该批次仍高于 400 秒目标，不能把旧批次与新批次均值差当作算法改善。原文中的外部目录是来源记录，不是本仓库路径。

本次核对 9 个迁入模块的语法树：仅改变导入路径，算法主体与参数不变；共用代码和覆盖证书与原包按 LF 归一后逐字节一致。两问各用 3 个本地训练案例，在独立只读进程中比较原包和迁入代码，策略仅接收公开动作响应；全部动作、策略结果及虚拟耗时一致，并独立核验全清依据。这是迁移回归，不是官方演练或新性能评测。

复现：`python scripts/verify_practice_v5.py`；仅检查源码可加 `--source-only`。四问统一验证为 `python scripts/verify_project.py`，见 [总报告](../report.md)。第四问新版需要 NumPy；原包运行环境是 Python 3.12.14 / NumPy 2.3.5，本次实际环境单独记录在核验 JSON。

## 版本与模块

- `problem3/current_policy.py` → `continuous_probe.py`：沿现有前瞻评分作连续选点改进。
- `problem4/current_policy.py` → `discovery_policy.py`：组合连续朝向的可见性评分、可中断定位及完整发现路线重排。
- `speed_policy.py` 及其几何/定位组件是新版继承的基础，也供显式 `--strategy v4` 历史回放；不能直接删除这些依赖。
- `previous` 仍保持原有含义：第三问 v1、第四问 v2；第四问 `legacy` 为更早的 v1。历史实验、冻结报告和概率停止分支保持原口径。

新版仍需完成认证覆盖并清除已发现源，或实际清除 16 个源才结束。可见性与发现概率只给动作排序，不提供提前停止依据。
