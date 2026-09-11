# 第三问结果

- [开发集比较](benchmark_development.md)：96个相同案例，比较3个分支。
- [独立留出集](benchmark_holdout.md)：192例，默认算法全部清除；平均275.99虚拟秒/源，300秒阈值通过61.5%。
- [困难压力集](benchmark_stress.md)：96例，全部清除；平均318.42虚拟秒/源。
- [演示路线](demo_route.svg)、[演示统计](demo_result.json)、[动作记录](demo_trace.jsonl)。

同名JSON保留每例指标、参数及代码指纹。带 `verification` 后缀的是统一验证所跑的8例回归，不加入完整样本数量。

全部是本地自建结果。在线运行的客户端记录写入 `online/`；正式平台导出的原名加密日志可保存至 `official/`，本次没有这些正式日志。
