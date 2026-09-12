# 问题3：搜索并清除全向干扰源

当前默认为 **`problem3_v5_continuous`**，对应用户实际使用的20260912新版演练包。生产策略入口是 `current_policy.py`，无需解压包或实验目录。

```powershell
python problem3/solve.py --version
python problem3/solve.py
```

默认只跑本地自建案例。换案例加 `--index 20`；统计、动作与路线放在 `results/demo_result.json`、`results/demo_trace.jsonl`、`results/demo_route.svg`。自选输入输出相对路径均按 `problem3/` 解析。

第三问核心仅需 Python 3.10 以上和标准库。

## 当前算法

1. 依据原点反馈选择6点环或9点外环，保持连续覆盖保证。
2. 由阳性、阴性反馈维护相容区域，沿前瞻评分作连续选点优化。
3. 搜索、定位和清除交错调度；细长区域比较窄带光学与射频定位成本。

只有完成认证覆盖并清除已发现源，或实际成功清除16个源才结束。假想位置和可见性评分只用于动作排序，不能作为全清证明。数学说明见 [model.md](model.md)。

## 查结果与运行记录

- [新版来源、模块对应与迁移验证](../validation/practice_v5/README.md)：保留原包7000例汇总；本次仅做迁移回归，没有重跑7000例或调参。
- [均衡样例与分问绘图](../validation/balanced_search.md)：每问7000例，10至16源各1000例。新版必须使用新的运行批次名称，不能续接旧版结果。
- [平台演练与正式测试步骤](../simulation_guide.md)：本地验证不占官方测试次数。
- [历史v4对照](../validation/speed_v4_summary.md)：仅代表当时冻结代码；`speed_policy.py` 保留为新版依赖与显式 `--strategy v4` 历史回放入口。
- `--strategy previous` 保留更早版本的原有含义；第四问 `--strategy legacy` 仍为最早25点版本。
- [概率提前停止实验](../validation/probability_stop/report.md)：使用历史基线的独立风险实验，当前默认未启用。

**所有本地汇总均不是官方成绩。**
