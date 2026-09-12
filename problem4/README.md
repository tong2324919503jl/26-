# 问题4：搜索并清除混合定向干扰源

当前默认为 **`problem4_v5_visibility_discovery`**，对应用户实际使用的20260912新版演练包。生产策略入口是 `current_policy.py`，无需解压包或实验目录。

```powershell
python problem4/solve.py --version
python problem4/solve.py
```

默认只跑本地自建案例。换案例加 `--index 20`；统计、动作与路线放在 `results/demo_result.json`、`results/demo_trace.jsonl`、`results/demo_route.svg`。自选输入输出相对路径均按 `problem4/` 解析。

第四问新版需要 NumPy，依赖见根目录 `requirements.txt`；原包验证环境为 NumPy 2.3.5，本次迁移核验环境另有记录。

## 当前算法

1. 继续使用已独立认证的22点布局。
2. 根据公开观测，对候选位置、接收半径和连续发射朝向积分，为成对探测评分。
3. 单次定位动作后允许重排任务，保留成对探测证据和有限光学队列。
4. 比较不同首动作的完整发现路线，以移动和预计扫频成本排序。

只有完成认证覆盖并清除已发现源，或实际成功清除16个源才结束。假想位置和可见性评分只用于动作排序，不能作为全清证明。数学说明见 [model.md](model.md)。

## 查结果与运行记录

- [新版来源、模块对应与迁移验证](../validation/practice_v5/README.md)：保留原包7000例汇总；本次仅做迁移回归，没有重跑7000例或调参。
- [均衡样例与分问绘图](../validation/balanced_search.md)：每问7000例，10至16源各1000例。新版必须使用新的运行批次名称，不能续接旧版结果。
- [平台演练与正式测试步骤](../simulation_guide.md)：本地验证不占官方测试次数。
- [历史v4对照](../validation/speed_v4_summary.md)：仅代表当时冻结代码；`speed_policy.py` 保留为新版依赖与显式 `--strategy v4` 历史回放入口。
- `--strategy previous` 保留更早版本的原有含义；第四问 `--strategy legacy` 仍为最早25点版本。
- [概率提前停止实验](../validation/probability_stop/report.md)：使用历史基线的独立风险实验，当前默认未启用。

**所有本地汇总均不是官方成绩。**
