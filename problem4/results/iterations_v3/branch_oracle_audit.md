# 第四问现有分支的事后 Oracle 审计

结论：现有分支池即使事后知道每例的最快分支，也未达到平均 400 秒/源，因此不值得为当前分支池训练选择器。没有修改策略或运行新场景。

只读取 `problem4/results/iterations_v3` 中带 `development_v2` 的已有结果，按 `case_id` 配对；要求所有已记录案例全部清除、完成证书为真、清除数一致，并验证虚拟总时间等于移动与实际动作成本之和。几何报告、少于所需例数的分支不进入相应比较。145 条结果记录通过检查；其中 135 条覆盖前 48 例、36 条覆盖前 96 例、9 条覆盖全部 384 例。同一批案例上相同时间向量只计一次，完整路径和文件指纹保存在 JSON。

| 前缀样本数 | 原始记录/不同时间向量 | 最佳固定分支均值 | Oracle 每案例均值 | Oracle 加权汇总 | Oracle ≤400 |
|---:|---:|---:|---:|---:|---:|
| 48 | 135/102 | 436.290 | 420.904 | 405.839 | 17/48 |
| 96 | 36/29 | 443.687 | 435.648 | 422.420 | 34/96 |
| 384 | 9/9 | 446.112 | 437.980 | 424.325 | 131/384 |

目标仍是每案例均值 `mean(T_i / N_i)`；加权汇总是 `sum(T_i) / sum(N_i)`，相当于对源数较多的案例赋予较大权重，不能将其较小数值视为原目标达标。这里 T 是完成覆盖确认后的总虚拟时间，不是最后一次清除时间。Oracle 只能说明这个已测分支池的互补上限，不是所有合法算法的性能下界。

前 48 例从最佳固定分支 436.290 降到 Oracle 420.904，最多节省 15.386 秒/源。贪心选 2、4、8 个分支的事后组合分别为 431.799、426.275、422.866；即使用很多分支也不能跨过 400。前 96、384 例的互补空间各约 8 秒/源。

48 例的赢家很分散：SharedLibraryCoverage 赢 5 例，clear_region 与 discovery_nolatency 各 4 例，skeleton_outer_unbounded、skeleton_outer 和 21 点覆盖原分支各 3 例。96 例主要赢家为 clear_region（24 例）、incremental_q30（15 例）、incremental_dynamic（13 例）。384 例中“21点＋仅新发现源共享基线”占 168.5 例，所有已知源共享基线占 47.5 例，其余分散；并列按比例分摊，避免重复结果制造赢家。

## 全部 384 例均有结果的分支

| 分支记录 | 每案例均值 | 加权汇总 |
|---|---:|---:|
| coverage_shared_one21 | 446.112 | 433.020 |
| coverage_shared_all_one21 | 447.515 | 434.379 |
| shared_one_small_all → shared_one_small_all | 461.946 | 448.303 |
| Ring12CoverPolicy | 471.341 | 458.206 |
| shared_two_small_shared_two_small_enroute → shared_two_small | 471.625 | 457.655 |
| shared_two_small_shared_two_small_enroute → shared_two_small_enroute | 472.236 | 458.390 |
| Ring14CoverPolicy | 473.416 | 459.643 |
| Ring13CoverPolicy | 474.996 | 461.503 |
| SearchPolicy | 483.724 | 469.915 |

全部 96 例完整记录（含以上 384 例分支）的 36 条清单、去重后的 29 条排名，分别见 JSON 的 `complete_96_or_more` 与 `scopes.96.branch_rankings`；48 例大集合的 102 条排名见 `scopes.48.branch_rankings`。每个分支均保留原文件和键路径。

## 公共初始观测与证据边界

这些旧结果只保存最终累计观测，没有一致保存原点首次扫频的正信号数或方位分布；出现的 initial 字段只是配置。因此不能从最终 detected_channels、动作次数或源数反推原点特征，也没有给出虚假的可预测性结论。未来若出现显著更强的新分支，可记录原点正信号频道数、near 数量、方位角最大空隙等公开特征；当前 Oracle 本身仍高于目标，没有训练门控器，也不进行新的开发集评估。

以上只使用自建开发结果，不读取留出集、压力集或官方日志。代码为 `problem4/experiments_v3/branch_oracle_audit.py`，逐例结果为 `branch_oracle_audit.json`。
