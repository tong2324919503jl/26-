# 首48例快照补充说明

原 `compare_teammate_p34_development_v3_48.json` 和 Markdown 保留，不覆盖。其第三问 `ours` 实际运行的是 `problem3.experiments_v3.optical_band:OpticalBandPolicy`，均值220.6474018秒/源；原JSON的 `worker_metadata.config.branch` 已准确记录该类。

上一轮最好的第三问分支是 `AggressiveBandPolicy`，不是该基础类。根代理独立核对同批最佳分支均值为220.6327396秒/源。比较脚本后续默认已改为 AggressiveBandPolicy，下一轮大样本以正确分支或显式 `--targets` 为准，不将旧快照改名成最佳分支结果。

第四问原快照运行 `posterior.Shared21Policy`，与上一轮最佳分支一致。队友两问均使用ZIP中的原配置与原factory：phase3_intercept、phase3_optical_nonuniform。

已支持对单问指定多个我方分支，队友默认配置始终一并运行。例如：

```text
python scripts/compare_teammate_p34.py --problem 3 --count 384 --split development_v3 --targets problem3.policy:SearchPolicy problem3.experiments_v3.optical_band:AggressiveBandPolicy problem3.speed_policy:SearchPolicy
python scripts/compare_teammate_p34.py --problem 4 --count 384 --split development_v3 --targets problem4.policy:SearchPolicy problem4.experiments_v3.posterior:Shared21Policy problem4.speed_policy:SearchPolicy
```

留出和压力选项已支持，但本次没有运行；应先冻结候选，再显式选择对应集合。默认输出名包含问题号及目标列表指纹，已有文件拒绝覆盖。通过 `--output` 可指定 validation/ 或 tmp/ 下新的输出文件。
