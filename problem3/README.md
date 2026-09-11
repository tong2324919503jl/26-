# 问题三：全向源的自动搜索与清除

目标是在不知道具体数量、位置和接收半径时，清除所有源，并缩短总虚拟时间。

## 怎么运行

```powershell
python problem3/solve.py
```

默认运行自建困难案例。查看 `results/demo_result.json` 的统计、`results/demo_route.svg` 的路线和 `results/demo_trace.jsonl` 的动作记录。

换一个案例：`python problem3/solve.py --index 20`。也可用 `--case examples/demo_case.json`；相对路径按 `problem3/` 解析。`--output-dir results/my_run` 可指定输出目录。

去官方平台运行：[模拟测试说明](../simulation_guide.md)。平台默认使用优化后的 `adaptive` 分支。

## 算法做什么

1. 从原点出发，在能覆盖整个目标圆的 7 个检测点搜索未知频道。
2. 用“方位 ±1.005°”维护目标可能区域，包含接口保留两位小数带来的增宽。
3. 根据移动距离和定位不确定性安排搜索、测向和清除；停下时补测有价值的其他已知目标。
4. 区域足够小时直接清除；定位困难时以有限光学网格兜底。
5. 完成覆盖且已发现源全部清除，或清除数达到 16，才确认结束。

数学模型、时间目标与完成保证见 [model.md](model.md)。

## 比较分支

- `adaptive`：优化策略，默认使用。
- `baseline`：先完成检测点搜索，再依次定位清除。
- `optical`：保留全局搜索，主要以光学覆盖清除，用来检验测向定位的价值。

```powershell
python scripts/benchmark_search.py --problem 3 --split development --strategies baseline adaptive optical --save-cases
```

每例使用相同场景和固定地点误差。开发集用于调参，留出集与压力集用于检查泛化；样本均为自建。自定速度阈值为 **全清且完成确认后，总时间 ≤ 300 × 源数秒**，源数只用于事后评分。

结果与复现方式见 [实验说明](../validation/search_experiments.md)。策略在 `policy.py`；`geometry.py`、`client.py`、`simulator.py` 同时供第四问复用。
