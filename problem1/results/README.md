# 结果文件

运行 `python -m problem1.solve` 可重新生成全部结果。输入来自 `../examples/`，均为自建数据，不是官方演练或正式测试记录。

- `two_station_crossing.result.json`、同名 `.svg`：两站近正交交会，直径约 `4.9385425824 m`。
- `triangle_counterexample.result.json`、同名 `.svg`：符合题设误差的三角形交会反例，直径约 `20 m`，最小覆盖圆半径约 `11.5470053838 m`。
- `parallel_unbounded.result.json`：同向观测的无界角度交集。
- `inconsistent_measurements.result.json`：互相背离观测的空交集。

无界和空集没有有限区域图。输出里的 `null` 应结合 `status` 解读；无界情形附带 `diameter_is_infinite: true`。
