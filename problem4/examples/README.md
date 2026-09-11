# 第四问自建样本

`demo_case.json` 是默认演示案例；`development_cases.json`、`holdout_cases.json`、`stress_cases.json` 分别保存96、192、96个案例，包含全向和定向源。

方向字段 `orientation_deg=null` 表示全向；数值表示源向外发射的朝向，不是测向机读到的目标方位。所有真值仅供本地环境执行与事后评分，策略不能读取。样本均非官方数据，分布见[实验说明](../../validation/search_experiments.md)。

`--case` 接受一个案例对象，批量案例用统一benchmark入口运行。
