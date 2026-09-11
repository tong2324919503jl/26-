# 问题四：混合全向、定向源的自动搜索与清除

默认已经使用第二轮提速算法。原来的自适应版本保留为 `legacy`，方便逐例比较。

## 直接运行

```powershell
python problem4/solve.py
```

默认跑一个本地自建案例，不联网。结果、路线图、动作记录放在 `problem4/results/`。换例子加 `--index 20`；运行旧版加 `--strategy legacy`。

官方平台的命令不变，按 [模拟测试说明](../simulation_guide.md) 操作。

## 提速结果

与**上一版**比较，代码冻结后使用全新样本，速度阈值仍为500秒/源：

| 自建集合 | 平均秒/源：旧→新 | 耗时减少 | 阈值通过率：旧→新 |
| --- | ---: | ---: | ---: |
| 新留出512例 | 539.0 → 484.3 | 10.2% | 41.2% → 56.8% |
| 新压力256例 | 629.1 → 537.8 | 14.5% | 34.0% → 43.4% |

连同384例开发集，新版1280例全部清除并取得完成确认。时间包含最后一次清除后的覆盖确认；没有把阈值调高。仍有较慢案例，完整记录见 [速度比较](results/speed_comparison_v2.md)。这些是本地自建结果，不是官方成绩。

## 改了什么

- 把有覆盖证明的检测布局从25点减为23点。
- 复用历史观测，只有能证明安全时才用“无信号”缩小候选区，减少过冲和绕行。
- 保留已有路线，并比较多个起点方案、搬移连续停点；发现16个频道后停止找新源，全部清除后才结束。

覆盖证明、定位和调度细节见 [model.md](model.md)，失败尝试见 [开发记录](experiments/README.md)。光学覆盖兜底继续保留。

批量复现：

```powershell
python scripts/benchmark_search.py --problem 4 --split holdout_v2 --strategies legacy adaptive --save-cases
python scripts/verify_project.py
```

核心程序只需Python 3.10以上和标准库。相对自选输入/输出路径按 `problem4/` 解析；例如 `--case examples/demo_case.json`、`--output-dir results/my_run`。
