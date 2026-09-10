# 结果文件

运行 `python -m problem1.solve` 可重新生成全部结果。输入来自 `../examples/`，均为自建数据，不是官方演练或正式测试记录。

- `two_station_crossing.result.json`、同名 `.svg`：两站近正交交会，直径约 `4.9385425824 m`。
- `triangle_counterexample.result.json`、同名 `.svg`：符合题设误差的三角形交会反例，直径约 `20 m`，最小覆盖圆半径约 `11.5470053838 m`。
- `triangle_optical_counterexample.result.json`、同名 `.svg`：吸收队友的 `40 m` 等边三角形反例，最小覆盖圆半径约 `23.0940107676 m`，因此 `D <= 40 m` 仍不能保证 `20 m` 光学定位。
- `wide_baseline_crossing.result.json`、同名 `.svg`：吸收队友的 `800 m` 基线两站交会算例，直径约 `31.4796747478 m`，最小覆盖圆半径约 `15.7398373739 m`。
- `parallel_unbounded.result.json`：同向观测的无界角度交集。
- `inconsistent_measurements.result.json`：互相背离观测的空交集。

无界和空集没有有限区域图。输出里的 `null` 应结合 `status` 解读；无界情形附带 `diameter_is_infinite: true`。

合并后的有界结果另有 `area_m2`、最远点对中点到区域的最大距离，以及 `optical_localization` 覆盖判据。后者直接检查最小覆盖圆半径是否不超过 `20 m`，并分别列出 `D <= 20√3` 的充分条件、`D <= 40` 的必要条件；理论边界上的三角系数舍入可能影响阈值真假，详见第一问说明的数值边界段落。新增示例的压缩包来源保留在 JSON 的 `data_origin` 中。
