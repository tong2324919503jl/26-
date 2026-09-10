# B题前两问验证报告

总结果：全部通过。

验证时间（UTC）：2026-09-10T12:13:54.890609+00:00；Python：3.12.14。

| 检查项 | 结果 |
| --- | --- |
| original_materials_and_searchable_copies | 通过 |
| problem1_tests | 通过 |
| problem1_solve_from_outside_repository | 通过 |
| problem2_tests | 通过 |
| problem2_solve_from_outside_repository | 通过 |
| result_files_readable | 通过 |
| documentation_links | 通过 |

验证包括三份资料及三个文本副本的一致性、两问测试、从仓库以外目录启动求解、结果文件可读取性和说明文档链接。

算例均为自行构造，只验证本地数学算法；没有运行问题3、4的官方演练或正式测试。

详细测试名称、输出、耗时、结果文件摘要见 [report.json](report.json)。

复现：在仓库根运行 `python scripts/verify_project.py`。
