# 第四问开发分支

这里用于复现选型和失败尝试，默认求解不依赖这些脚本。计算结果保存在 [results/iterations_v2](../results/iterations_v2/)。核心求解只需标准库；几何布局的离线优化脚本 `coverage.py` 另用SciPy，生成后的布局由标准库重新认证。

本轮先保留上一版为 `legacy_policy.py`，主要使用新的384例开发集合。方法冻结后才运行新的512例留出和256例压力集合。最终结果看 [配对速度报告](../results/speed_comparison_v2.md)，不要把这里的多次开发试验当成独立泛化证据。

## 采用的改动

- **历史阴性裁剪**：重复利用经过距离证明的旧无信号点，减少定位过冲；历史阳性还提供未知接收半径的下界。生产版在 `../localization.py`。
- **23点非均匀覆盖**：由有限Voronoi圆缺极值证书确认任意发射朝向，接收距离余量约15.58米。不是仅靠采样验证，也没有证明23点全局最少。
- **路线保留、多起点与短段搬移**：已有路线不再每次丢弃，把连续1—3个停点搬到其他位置，配合估计扫频成本改善访问顺序。详见 [路线同口径对照](../results/iterations_v2/route_escape_report.md)。
- **发现16后停止找新源**：仍须实际清除16个才完成，并保留真实覆盖完成标记。

## 没有采用的尝试

| 尝试 | 开发观察与取舍 |
| --- | --- |
| 只增加2-opt次数、减少定位轮数 | 没有稳定收益；改用短段搬移跳出原局部最优。 |
| 固定外环先扫 | 少一些读数却增加行走，24例筛查平均更慢。 |
| 初始读数后旋转布局、固定插入服务、定位入口成本排序 | 收益不稳定或变差，保留记录后停止此方向。 |
| 更精细的阳性半径残余分割 | 384例仅再省0.011秒/源，增加计算，未选。 |
| 清除点替换巡检点 | 更强证书下48例仅省约0.14秒/源，阈值通过数不变，未选。 |
| 19点规则布局 | 存在解析漏检反例，直接否定。 |
| 22点布局 | 多种几何修复没有获得证书；这不能证明不存在22点解。 |
| 单独把25点换成23点 | 在早期384例组合中反而更慢，说明少停点不等于少走路，必须联合比较。 |

各模块收益不能直接相加。早期非均匀布局使用未舍入坐标，最终统一六位小数后重新比较；固定地点误差使微小坐标变化也可能改变后续路线，两个口径不混用。

## 复现选型

```powershell
python problem4/experiments/compare.py problem4.experiments.localization:RadiusBoundSearchPolicy --split development_v2 --count 384
python problem4/experiments/route_escape_rounded.py info warm warmhybrid_info --count 384
python problem4/experiments/route_escape.py --self-test
```

第一条复现25点下的定位分支；第二条比较最终舍入23点下的三种路线。更早的探索与瓶颈分析见 [路由记录](../results/iterations_v2/routing_report.md)。生产文件冻结记录在 [problem4_freeze_v2.json](../../validation/problem4_freeze_v2.json)。全部证据是本地自建测试，没有使用官方测试机会。
