# B题四问验证报告

总结果：全部通过。

验证时间（UTC）：2026-09-12T12:28:46.987653+00:00；Python：3.12.7。

自动测试：问题1 36 项，问题2 27 项，问题3 106 项，问题4 49 项。

| 检查项 | 结果 |
| --- | --- |
| 原材料与检索副本完整性 | 通过 |
| 第一问数学与程序测试 | 通过 |
| 第一问从仓库外目录运行 | 通过 |
| 第二问数学与程序测试 | 通过 |
| 第二问从仓库外目录运行 | 通过 |
| problem3_tests | 通过 |
| problem3_solve_from_outside_repository | 通过 |
| problem4_tests | 通过 |
| problem4_solve_from_outside_repository | 通过 |
| 同口径策略比较及跨目录复现 | 通过 |
| 提前停止的评分与选点等价性及计算量 | 通过 |
| problem3_search_smoke_from_outside_repository | 通过 |
| problem4_search_smoke_from_outside_repository | 通过 |
| 结果文件完整且可读取 | 通过 |
| 说明文档本地链接 | 通过 |

验证包括三份资料及三个文本副本的一致性、四问测试、从仓库以外目录启动求解与策略对比、问题三四各8例困难样本回归、结果文件可读取性和说明文档链接。

算例均为自行构造，只验证本地数学算法；没有运行问题3、4的官方演练或正式测试。

详细测试名称、输出、耗时、结果文件摘要见 [report.json](report.json)。

复现：在仓库根运行 `python scripts/verify_project.py`。加 `--reference` 可额外运行独立 SciPy/HiGHS 几何核验（仅这一可选项需要 SciPy）。

本次独立参考核验：未请求；已有 reference_geometry.json 不代表本次已重跑。
