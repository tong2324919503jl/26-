# 第三问自建样本

`demo_case.json` 是默认演示案例；`development_cases.json`、`holdout_cases.json`、`stress_cases.json` 分别保存96、192、96个案例。每例含来源标记、随机种子、场景类别、噪声模型和环境真值。

这些真值只由本地环境与事后评分器读取，策略只接收接口反馈。不是官方数据。分布和统计口径见[实验说明](../../validation/search_experiments.md)。

单例运行使用一个案例对象的JSON，不直接把整个案例列表传给 `--case`；批量列表通过统一benchmark入口按同种子生成与运行。
