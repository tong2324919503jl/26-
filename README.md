# 2026 国赛 B 题

题目：**无线电干扰源的快速自动定位与清除**。四问分别放在 `problem1`—`problem4`。

| 要做什么 | 从这里看 |
| --- | --- |
| 第一问：根据测向信息计算定位区域 | [问题1](problem1/README.md) |
| 第二问：选择第二个检测点 | [问题2](problem2/README.md) |
| 第三问：自动搜索并清除全部全向源 | [问题3](problem3/README.md) |
| 第四问：自动处理全向与定向混合源 | [问题4](problem4/README.md) |
| 去官方平台演练、正式测试 | [模拟测试简明说明](simulation_guide.md) |
| 看本地比较与调优依据 | [实验说明](validation/search_experiments.md) |
| 看程序检查是否通过 | [验证报告](validation/report.md) |

## 先在本地跑

Python 3.10 或以上，核心求解只用标准库。在仓库文件夹运行：

```powershell
python problem3/solve.py
python problem4/solve.py
python scripts/verify_project.py
```

前两条各跑一个自建案例，输出到对应 `results/`，包括统计、动作记录和路线图。默认不联网、不占平台测试次数。第一、二问分别运行 `python problem1/solve.py`、`python problem2/solve.py`。

## 第三、四问的思路

先用有覆盖保证的检测点发现目标，再根据带误差的方位信息逐步接近并清除；顺路补测其他目标以减少绕行。第四问额外处理定向源背面无信号，并在目标圆外安排必要检测点。无法顺利测向时，用有限的光学覆盖兜底。

算法只有完成覆盖并清除全部已发现源，或已成功清除数量上限 16 个时，才确认完成。具体证明和局限见各问 `model.md`。

## 文件放在哪里

- 原题与两份附件：[materials/problem_b](materials/problem_b/README.md)。原始题包 `CUMCM2026Problems/` 保持不变。
- 每问的说明、程序、样本、结果、测试：`problem1/`—`problem4/`。
- 统一验证和批量比较：`scripts/`；报告：`validation/`。
- 前两问与队友 ZIP 的合并记录：[merge_notes.md](validation/merge_notes.md)。原 ZIP 保留。

**本地自建样本结果不是官方演练或正式成绩。** 本仓库已准备平台接口程序和测试步骤；官方测试仍需你登录模拟器运行。第三、四问正式测试各仅 3 次，导出的加密日志须保留原文件名。
