# 问题三：搜索并清除全向干扰源

默认已启用 **`problem3_v4`**，包含上一轮表现最好的算法。启动时会显示版本。

概率提前停止单独作为实验，默认算法不变；见[测试步骤](../simulation_guide.md#5-概率提前停止实验仅本地)和[漏清风险结果](../validation/probability_stop/report.md)。

```powershell
python problem3/solve.py --version
python problem3/solve.py
```

默认只跑本地自建案例，不联网。换案例加 `--index 20`；查看 `results/demo_result.json` 的统计和 `results/demo_route.svg` 的路线。

去官方平台运行，按 [模拟测试说明](../simulation_guide.md) 操作。回放本轮之前的默认算法，加 `--strategy previous`。

## 清除逻辑

1. 在原点搜索未知频道；原点没有发现源时使用9点外环，否则使用原有6点环。两种布局均有连续覆盖保证。
2. 用方位误差和全向源的阴性观测维护可能区域，根据预计移动和后续定位成本选择检测点。
3. 搜索、定位、清除交错进行，每一步更新路线；区域足够小时清除，狭长区域可做有限光学扫描。
4. 完成覆盖并清除已发现源，或实际成功清除16个源，才确认结束。

本轮队友的途中截获等新组合未超过已有最好算法，因此没有加入。此前最快分支只在实验目录中，本轮已迁入默认入口。

同一512例留出集合中，原默认 **272.55→226.78秒/源**，全部清除；仍未达到220秒均值目标。这是本地自建结果。完整比较见 [本轮报告](../validation/speed_v4_summary.md)，数学说明见 [model.md](model.md)。

核心程序仅需 Python 3.10以上和标准库。生产入口在 `speed_policy.py`，不依赖实验目录或队友ZIP。自选 `--case`、`--output-dir` 的相对路径按 `problem3/` 解析。
