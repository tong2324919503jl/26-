# 问题四：混合全向、定向源的自动搜索与清除

定向源只向一个半平面发射信号。**无信号不能直接解释为没有目标或距离太远**；光学清除则不受发射方向影响。

## 怎么运行

```powershell
python problem4/solve.py
```

默认运行自建困难案例。统计、路线图、动作记录分别输出到 `results/demo_result.json`、`results/demo_route.svg`、`results/demo_trace.jsonl`。

换例子：`python problem4/solve.py --index 20`。`--case examples/demo_case.json` 和 `--output-dir results/my_run` 的相对路径均按 `problem4/` 解析。

去官方平台运行：[模拟测试说明](../simulation_guide.md)。平台默认使用优化后的 `adaptive` 分支。

## 与第三问有什么不同

- 用内外两圈与中心构成的 **25 个检测点** 搜索，外圈可以超出目标圆，处理位于边界且向外发射的源。
- 检测点把目标圆包在若干小三角形内，三角形直径小于最短接收半径；配合半平面性质，可证明任意朝向都不会漏检。
- 定位时处理移动后的信号丢失；只有满足证明条件的阴性反馈才用于缩小区域，其余保留不确定性。
- 保留光学覆盖兜底，完成确认与第三问一致。

模型和证明见 [model.md](model.md)。共用协议、仿真、几何实现放在 `problem3/`，第四问不复制原附件。

## 比较分支

`adaptive` 是默认优化策略；`baseline` 使用 31 点三角格网和基础定位；`optical` 使用光学覆盖作对照。

```powershell
python scripts/benchmark_search.py --problem 4 --split development --strategies baseline adaptive optical --save-cases
```

自定速度阈值为 **全清且完成确认后，总时间 ≤ 500 × 源数秒**。奖励先惩罚漏清，再奖励更快完成；此阈值不是官方评分规则。不同分支用完全相同的自建场景和误差。

结果、消融与泛化检查见 [实验说明](../validation/search_experiments.md)。本地结果不能替代平台演练和三次正式测试。
