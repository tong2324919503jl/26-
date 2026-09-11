# 2026 国赛 B 题

题目：**无线电干扰源的快速自动定位与清除**。四问分别放在 `problem1`—`problem4`。

| 要做什么 | 从这里看 |
| --- | --- |
| 第一问：根据测向信息计算定位区域 | [问题1](problem1/README.md) |
| 第二问：选择第二个检测点 | [问题2](problem2/README.md) |
| 第二问评分依据与提前停止效果 | [文献核查](problem2/references.md)、[等价性与计算量](problem2/results/scoring_benchmark.md) |
| 第三问：自动搜索并清除全部全向源 | [问题3](problem3/README.md) |
| 第四问：自动处理全向与定向混合源 | [问题4](problem4/README.md) |
| 本轮队友方案融合、速度与波动 | [第四轮对照结果](validation/speed_v4_summary.md) |
| 概率提前停止能省多少、会漏多少 | [风险实验报告](validation/probability_stop/report.md) |
| 去官方平台演练、正式测试 | [模拟测试简明说明](simulation_guide.md) |
| 看本地比较与调优依据 | [实验说明](validation/search_experiments.md) |
| 220/400秒目标的历史开发记录 | [第三轮实验](validation/threshold_220_400_v3.md)、[第二轮提速](problem4/results/speed_comparison_v2.md) |
| 看程序检查是否通过 | [验证报告](validation/report.md) |
| 论文正文与图表 | [论文工作稿](paper/README.md)（暂不含附录，正式成绩待核对补齐） |

## 先在本地跑

Python 3.10 或以上，核心求解只用标准库。在仓库文件夹运行：

```powershell
python problem3/solve.py
python problem4/solve.py
python scripts/verify_project.py
```

第三、四问默认分别使用 **`problem3_v4`、`problem4_v4`**，启动时会显示。加 `--version` 可只检查版本；加 `--strategy previous` 可回放本轮之前的默认算法。

前两条各跑一个自建案例，输出到对应 `results/`，包括统计、动作记录和路线图。默认不联网、不占平台测试次数。第一、二问分别运行 `python problem1/solve.py`、`python problem2/solve.py`。

## 第三、四问的思路

搜索、定位和清除交错进行，根据观测不断更新路线。第三问采用条件外环与前瞻检测；第四问融合队友22点布局、补测收益筛选及失败清除后的候选碎片处理。无法顺利测向时，用有限的光学覆盖兜底。

算法只有完成覆盖并清除全部已发现源，或已成功清除数量上限 16 个时，才确认完成。具体证明和局限见各问 `model.md`。

概率提前停止另放在实验入口，安全默认不变。该实验额外需要 NumPy；本地运行方法见[简明步骤](simulation_guide.md#5-概率提前停止实验仅本地)。概率高不等于覆盖证明，是否采用以漏清风险检验为准。

## 文件放在哪里

- 原题与两份附件：[materials/problem_b](materials/problem_b/README.md)。原始题包 `CUMCM2026Problems/` 保持不变。
- 每问的说明、程序、样本、结果、测试：`problem1/`—`problem4/`。
- 统一验证和批量比较：`scripts/`；报告：`validation/`。
- 前两问与队友 ZIP 的合并记录：[merge_notes.md](validation/merge_notes.md)；第三四问见[本轮对照](validation/speed_v4_summary.md)。原 ZIP 均保留，生产运行不依赖解压副本。

**本地自建样本结果不是官方演练或正式成绩。** 本仓库已准备平台接口程序和测试步骤；官方测试仍需你登录模拟器运行。第三、四问正式测试各仅 3 次，导出的加密日志须保留原文件名。
