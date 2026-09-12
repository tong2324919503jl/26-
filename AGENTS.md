# 仓库工作约定

当前选题是 2026 国赛 B 题“无线电干扰源的快速自动定位与清除”。工作范围已扩展为四问；第三、四问本地开发和平台接口准备不代表已完成官方测试。

## 文件位置

- `CUMCM2026Problems/`：原始完整题包，保留原文件与名称，不把生成结果放入其中。
- `materials/problem_b/`：B题工作副本；`statement.pdf`、`attachments/` 是原材料，`extracted/` 是可检索文本，`manifest.json` 记录来源与哈希。
- `problem1/`：第一问说明、求解实现、`examples/`、`results/`、`tests/`。
- `problem2/`：第二问说明、求解实现、`examples/`、`results/`、`tests/`。
- `problem2/trace_hierarchical_search.py`实际调用默认生产选点并记录逐层完整候选，轨迹保存在`problem2/results/hierarchical_trace_20260912/`，拒绝覆盖；新运行须指定新输出目录。`paper/plot_p2_hierarchical_trace.py`重建`paper/figures/problem2_candidates/p2_14_hierarchical_trace/`三种图14候选，原图14保留；图14A已插入5.2.5，正文副本为`paper/figures/p2_14a_progressive_zoom.pdf`，重绘后须同步该副本和Overleaf。颜色按首次访问层；后层保留旧点，不能声称累计点集收缩；半域展示须核验另一侧镜像，安全边界补点不能暗中删除，第三层优选不等于最终统一复核结果。
- `problem3/`：全向搜索策略，共用几何、HTTP客户端、本地仿真器、样本生成器和运行入口。
- `problem4/`：混合定向策略、覆盖证明及样本、结果和测试；复用第三问共用组件。
- 当前默认为用户确认的20260912新版演练代码：两问 `current_policy.py`，版本 `problem3_v5_continuous`、`problem4_v5_visibility_discovery`。模块映射、原包汇总与迁移验证位于 `validation/practice_v5/`，原包归档为 `releases/p34_practice_20260912.zip`。`speed_policy.py` 是新版继承基础，显式 `--strategy v4` 回放 `problem3_v4`、`problem4_v4`；`previous` 回放本轮之前的 `problem3/policy.py` 和 `problem4/policy.py`，第四问 `legacy` 仍回放更早的 `legacy_policy.py`。旧类不覆盖，以便历史结果可复现。
- 新版第三问连续选点在 `continuous_probe.py`；第四问在 `visibility.py`、`incremental_localization.py`、`incremental_visibility.py`、`discovery_route.py`、`global_discovery.py`、`discovery_policy.py`。仅修改原包模块导入路径，保持参数和主体不变；`python scripts/verify_practice_v5.py`核验源码及两问各3个训练案例动作等价，不重跑7000例。第四问需要NumPy，包内7000例只作为原包汇总，不冒充本次重跑或独立留出。
- 第三问生产前瞻与调度在 `lookahead.py`、`planning.py`；第四问融合模块在 `search_layout.py`、`shared_baseline.py`、`bystander.py`、`optical_repair.py`，历史几何与路径模块继续复用。默认运行不能依赖实验脚本、ZIP解压目录或 `tmp/`。
- 第三轮实验保留在 `experiments_v3/`；第四轮融合消融在 `experiments_v4/` 与 `results/iterations_v4/`。历史第四轮的220/400秒均值目标未达到；新版原包7000例汇总为186.19/426.45秒，第四问仍未达标，跨分布不得声称算法改善；历史300/500阈值报告保持原口径，新比较使用220/400。
- `validation/speed_v4_summary.md`：队友融合、同批速度与波动；`speed_v4_freeze.json` 保存留出前冻结指纹，`speed_v4/` 保存每问384/512/256例的配对原始记录。旧第三轮ZIP已从工作树删除；原包对照脚本从Git提交 `8aefbd7` 按需恢复、核对原哈希并隔离运行。第四轮报告为历史结果，不代表当前v5。
- `simulation_guide.md`：依据两份附件整理的平台演练、正式测试和日志导出步骤。
- `validation/search_experiments.md`：第三四问开发、留出和压力测试口径及调优记录。
- `scripts/`：跨问题的资料整理、验证入口。
- `validation/`：最近一次本地验证报告。
- `validation/merge_notes.md`：当前版与队友 ZIP 的合并取舍、来源指纹和比较口径。
- `paper/`：论文正文与图表。按用户最新要求，当前主文件只含摘要、正文、AI声明和参考文献，暂不制作或并入附录。正文采用生产方案和冻结的本地结果；六次第三问演练可从Git历史日志封装头核对，正式测试各三次成绩仍未齐备。修改模型或表中结果后应同步论文与PDF，参见 `paper/README.md`。
- `paper/figures/problem2_candidates/`：第二问19张候选图，样式参照当前第一问正文图，图02、08、09已并入正文。`plot_p2_intro_candidates.py`、`plot_p2_scoring_candidates.py`、`plot_p2_selection_candidates.py`调用现有几何或读取保存结果；正文图09现由`plot_p2_reading_cells_outer_bounds.py`生成，旧评分候选脚本不再覆盖该图，原版保存在`p2_09_outer_bounds_trial/original/`。`build_p2_figure_catalog.py`生成`paper/results/p2_figure_catalog.pdf`和图包。图内仅保留必要标签，图注和证据另存同名JSON。角度保持真实1°/1.05°并通过局部放大展示；A/B/C不得表述为真实定位误差。
- `paper/figures/flowcharts/`：第一、二问正文流程图的编辑副本，基于用户中文draw.io原稿修订；导出为`p1_algorithm_flowchart.pdf`、`p2_algorithm_flowchart.pdf`。原稿保留。存在非零衰退方向对应无界，第二问逐单元检查提前停止；重绘后同步本地正文与Overleaf。
- `tmp/`：被 Git 忽略的临时渲染与检查文件。
- `paper/figures/p34_candidates/`与`p34_figure_catalog.pdf`：上一轮候选图和方案比较的历史稿，暂不替换正文。新的分问图位于`paper/figures/problem3/`、`problem4/`，只画指定批次的当前solve方案；图内保留坐标、单位与必要图例，不放解释段落。两项指标为清除比例与平均定位清除时间，不以本地阈值通过率代替清除比例。
- `problem3/examples/balanced_normal_v2/`、`problem4/examples/balanced_normal_v2/`：默认单一样例池，每问7,000例，10至16源各1,000例。每组以截断标准正态[-3,3]等概率分位点构造连续难度，再固定随机打乱；中间[-1,1]共684例，两侧各158例，不按难度拆分目录或数据子集。难度参数改变空间范围、接收半径和第四问方向条件，不保证实际耗时正态。清单保存独立种子域、生成器指纹与数据校验值。旧`balanced_v1`为本地历史池，保留读取兼容；新默认不覆盖它。`validation/balanced_search.md`为使用说明。
- `scripts/run_balanced_search.py`：校验样例、运行当前solve默认方案、分别出图的一键入口；`prepare_balanced_search.py`只生成/校验，`benchmark_balanced_search.py`支持同指纹断点续跑。结果按`problemN/results/balanced/<run-id>/`隔离，策略只接收独立进程中的公开响应；失败和零清除记录不得丢弃。`paper/plot_balanced_search.py`读取批次结果，`plot_search_mechanisms.py`读取当前配置并核验几何。新入口不连接平台。

前期选题分析、文献清单、北京赛区注意事项已仅改名并移至 `docs/background/`，对应关系见其README；原题包保持原位。重复候选图ZIP可由图册脚本重建，不纳入Git；概率实验的 `.jsonl.gz` 是实际结果数据，保留。

## 命名与执行

- 程序、输入、输出使用描述性英文小写文件名；说明使用中文。新数据放 `examples/` 或明确的数据目录，计算输出放 `results/`，不写到根目录。
- 所有默认读写路径相对 `Path(__file__)` 确定，不能依赖启动时工作目录。
- 共用原材料只读取 `materials/problem_b/`，不要在每问各复制一份附件。
- `materials/problem_b/extracted/` 与 `manifest.json` 固定使用 LF 换行（见 `.gitattributes`），避免跨系统检出导致文本哈希失配。
- `python scripts/prepare_materials.py` 重建检索文本，需要 `pypdf`。脚本对已改动的资料副本拒绝覆盖。
- `python scripts/verify_project.py` 运行四问测试、外部目录启动检查、第三四问各8例压力回归、资料完整性检查并更新验证报告。
- `python problem3/solve.py`、`python problem4/solve.py` 默认仅跑本地案例；显式 `--online --robot-id 队号` 才连接平台。`--version` 只显示版本，不产生动作；启动及结果文件均须保留 `algorithm_version`。相对自选输入/输出路径按对应问题目录解析。
- `python scripts/benchmark_search.py --problem 3 --split development --strategies baseline adaptive optical` 批量比较；第四问改为4，留出/压力集改为holdout/stress。生成数据写examples，结果写results。
- 第四问第二轮使用 `--split development_v2/holdout_v2/stress_v2 --strategies legacy adaptive --save-cases`（三个集合分别运行），数量384/512/256。`python scripts/report_problem4_speed.py` 汇总配对速度与阈值变化；旧报告保留为历史结果，不与新代码混写。新参数只用开发集合选择，留出前冻结代码。
- 第三轮新增的 `development_v3` 用于本轮融合选择；`holdout_v3/stress_v3` 在第四轮代码冻结后用于独立验证，不得再用于调参。后续若重新选择算法，须换新留出种子并披露。策略决策代码不得读取场景类别、场景种子或源真值；生成器、外部统计和事后审计除外。
- 第三轮较好候选 P3 `optical_band.AggressiveBandPolicy`、P4 `posterior.Shared21Policy` 保留为历史实验。第四轮第三问等价迁入生产，队友截获等无益分支不采用；第四问在384例开发上由444.38降至440.16，采用22点、共享基线、补测收益筛选及有限光学修复。P3合法单例反例及P4固定架构下界不可扩张成批量均值目标不可能的结论，详见第三轮历史记录。
- `python scripts/compare_teammate_p34.py` 将各分支置于隔离进程，在同一模拟器按实际exit总时间配对；逐未知频道独立检查实际观测点的覆盖，外部真值仅用于核验全清。`python scripts/report_search_v4.py` 检查冻结指纹并重建本轮汇总，结果文件不得覆盖已有冻结快照。
- `python scripts/plot_search.py` 重建实验对照图；仅此可选绘图脚本需要matplotlib。第三问核心与HTTP客户端仅需标准库；第四问v5与统一验证需要NumPy。
- 概率提前停止只在 `problem3/probability_stop.py` 实验分支，两问安全默认不变；可选实验需要 NumPy，`python scripts/run_probability_stop.py --problem 4 --mode guarded --threshold 0.99` 仅本地运行，不支持联网。无 NumPy 时跳过相应可选实验测试。
- 概率实验新生成器为 `problem3/probability_scenarios.py`，每问开发256、校准512、留出2048、压力512例。全部预设阈值报告，冻结记录、轨迹、结果放 `validation/probability_stop/`。这些保留集一经验证不得再调参；批测入口 `scripts/benchmark_probability_stop.py`，汇总入口 `scripts/report_probability_stop.py`。
- `python problem2/compare_strategies.py` 重建同口径策略比较；统一验证也会运行此入口，计算输出放在 `problem2/results/`。
- `python problem2/benchmark_scoring.py` 对照同一统一模型的完整扫描和提前停止，检查评分、排序、完整选点路径一致，并记录扫描量及本地耗时；统一验证也会运行。
- `python scripts/verify_project.py --reference` 额外用 SciPy/HiGHS 独立核验第一问，输出 `validation/reference_geometry.json`；SciPy 仅是此可选检查的依赖。
- 当前演练ZIP原件放 `releases/`；两个旧交付包通过Git历史保留，不再放在根目录。运行与验证不能依赖 `tmp/` 内解压副本，不另建一套平行求解目录。
- 修改数学实现后必须运行对应测试；联合交付运行完整验证。改共用组件同时验证第三、四问。
- 均衡样例固定LF；不得覆盖损坏数据或把不同代码指纹的批次续接。算法定稿后用新`--run-id`完整运行；`--limit-per-count`仅作均衡小样本流程预览，不得标成7,000例实验。此单一样例池不宣称独立留出集；若据此调参须披露，旧留出边界仍有效。构造难度只用于外部数据审计，不能传给策略；不同生成分布的均值变化不能称为算法改善。

## 数学与证据边界

- 原题中角度从+x轴逆时针，默认误差±1°，同一位置误差固定。不能用重复测量平均来假设误差减少。
- 前两问未提供具体观测样本。自建数据和自建验证不可描述为官方数据、正式成绩或模拟器测试。
- 第一问需区分空、无界、退化和有界交集；有限大边框不能证明交集有界。区域直径与最小覆盖圆直径不是同一量。
- 第一问旋转卡壳只优化凸多边形的直径步骤；半平面枚举和最小覆盖圆仍各有独立复杂度，不把完整求解说成线性时间。
- 第二问未知真实距离和接收半径。首次收信条件也提供半径下界；必须解释候选区域的收信保证、定位指标及离散搜索局限。
- 第二问保留四圆盘安全域和解析条带上界，融合目标圆条件化与第二读数网格半步增宽。比较选点时统一移动预算、圆盘边数和读数精度，分别报告评分变紧与选点变化，不能将不同上界之差写成真实误差改善。
- 第二问评分与实际后验共用几何构造，扇区、条带和5米投影下界须同步半步增宽；唯一定位目标为最坏相容读数下的区域直径。先算A，扫描B的部分最大值达到A即停止；此时完整B及全局最坏单元必须记null，部分最大值仅为B的下界。依据与适用范围见 `problem2/references.md`。
- 1800米目标圆约束干扰源位置，不限制第二检测点只能在圆内。
- 原文件为权威来源；提取文本可能损失公式排版或图示。
- 第三四问不能把自建环境、mock HTTP或本地奖励写成官方模拟器或官方成绩。第一轮每问开发96、留出192、压力96例；第四问第二轮另用384/512/256个不重叠种子，策略不访问真值。留出后再调优须更换留出集合并披露。
- 接口读数两位小数，几何误差至少按±1.005°处理；阴性不自动删除定向候选区域，收紧前须验证相应距离/半平面前提。
- 第四问允许检测点在目标圆外；全清终止须完成有证明的覆盖并清除已发现源，或成功清除上限16个，达到10个不能认定完成。
- 概率实验可在所有已发现源清完且至少清10个后，首次跨阈值时退出，但必须标记 `completion_certified=false`。全清后验依赖源数与独立位置/方向先验；guarded 的数值误差联合界不保证真实平台全清，零粒子幸存不等于不存在遗漏。评估按整局第一次跨阈值计时，外部真值仅作事后标签，漏源与节时必须分别报告。
- 第四问默认22点布局已由队友有理数证书及我方有限Voronoi圆缺极值证书独立认证，坐标固定，见 `coverage_certificate_v4.json`；不能仅用采样网格接受新布局。发现16个频道只允许停止发现阶段，实际清除16个才能结束，并保持 `coverage_complete` 与 `completion_certified` 的区别。历史阴性裁剪须先证明其在未知接收半径内，不能直接减圆盘。
- 第四问光学修复只从辅助候选碎片并集中扣除已接受失败clear对应的内接20米盘多边形，不放宽原有方位外包区域。面积/动作代价仅用于排序，每源最多额外16次，不能把启发式候选点集当作独立全清证书。补测收益预测也只排序，真实观测负责更新几何。
- 官方正式测试每问仅3次，成功启动和手工中止均占次。须先读两份附件，原名保存平台加密日志，本地JSONL不能替代。
- 平台请求串行，同动作重试复用同ID同内容，未知结果不发新动作。clear不切频道，accepted=false不更新状态；读取enter实际剩余时间，结束后不能用exit查询原因。

有实质目录或流程变动时，同步更新此文件和根 `README.md`。
