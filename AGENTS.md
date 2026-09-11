# 仓库工作约定

当前选题是 2026 国赛 B 题“无线电干扰源的快速自动定位与清除”。工作范围已扩展为四问；第三、四问本地开发和平台接口准备不代表已完成官方测试。

## 文件位置

- `CUMCM2026Problems/`：原始完整题包，保留原文件与名称，不把生成结果放入其中。
- `materials/problem_b/`：B题工作副本；`statement.pdf`、`attachments/` 是原材料，`extracted/` 是可检索文本，`manifest.json` 记录来源与哈希。
- `problem1/`：第一问说明、求解实现、`examples/`、`results/`、`tests/`。
- `problem2/`：第二问说明、求解实现、`examples/`、`results/`、`tests/`。
- `problem3/`：全向搜索策略，共用几何、HTTP客户端、本地仿真器、样本生成器和运行入口。
- `problem4/`：混合定向策略、覆盖证明及样本、结果和测试；复用第三问共用组件。
- `simulation_guide.md`：依据两份附件整理的平台演练、正式测试和日志导出步骤。
- `validation/search_experiments.md`：第三四问开发、留出和压力测试口径及调优记录。
- `scripts/`：跨问题的资料整理、验证入口。
- `validation/`：最近一次本地验证报告。
- `validation/merge_notes.md`：当前版与队友 ZIP 的合并取舍、来源指纹和比较口径。
- `tmp/`：被 Git 忽略的临时渲染与检查文件。

原根目录的选题分析、文献清单、北京赛区注意事项以及原题包均是既有资料。修改前核对其用途；本轮未改写它们。

## 命名与执行

- 程序、输入、输出使用描述性英文小写文件名；说明使用中文。新数据放 `examples/` 或明确的数据目录，计算输出放 `results/`，不写到根目录。
- 所有默认读写路径相对 `Path(__file__)` 确定，不能依赖启动时工作目录。
- 共用原材料只读取 `materials/problem_b/`，不要在每问各复制一份附件。
- `materials/problem_b/extracted/` 与 `manifest.json` 固定使用 LF 换行（见 `.gitattributes`），避免跨系统检出导致文本哈希失配。
- `python scripts/prepare_materials.py` 重建检索文本，需要 `pypdf`。脚本对已改动的资料副本拒绝覆盖。
- `python scripts/verify_project.py` 运行四问测试、外部目录启动检查、第三四问各8例压力回归、资料完整性检查并更新验证报告。
- `python problem3/solve.py`、`python problem4/solve.py` 默认仅跑本地案例；显式 `--online --robot-id 队号` 才连接平台。相对自选输入/输出路径按对应问题目录解析。
- `python scripts/benchmark_search.py --problem 3 --split development --strategies baseline adaptive optical` 批量比较；第四问改为4，留出/压力集改为holdout/stress。生成数据写examples，结果写results。
- `python scripts/plot_search.py` 重建实验对照图；仅此可选绘图脚本需要matplotlib。核心算法、HTTP客户端、本地测试与统一验证仅需标准库。
- `python problem2/compare_strategies.py` 重建同口径策略比较；统一验证也会运行此入口，计算输出放在 `problem2/results/`。
- `python scripts/verify_project.py --reference` 额外用 SciPy/HiGHS 独立核验第一问，输出 `validation/reference_geometry.json`；SciPy 仅是此可选检查的依赖。
- 根目录队友 ZIP 保留为原始交付件。运行与验证不能依赖 `tmp/` 内解压副本，不另建一套平行求解目录。
- 修改数学实现后必须运行对应测试；联合交付运行完整验证。改共用组件同时验证第三、四问。

## 数学与证据边界

- 原题中角度从+x轴逆时针，默认误差±1°，同一位置误差固定。不能用重复测量平均来假设误差减少。
- 前两问未提供具体观测样本。自建数据和自建验证不可描述为官方数据、正式成绩或模拟器测试。
- 第一问需区分空、无界、退化和有界交集；有限大边框不能证明交集有界。区域直径与最小覆盖圆直径不是同一量。
- 第一问旋转卡壳只优化凸多边形的直径步骤；半平面枚举和最小覆盖圆仍各有独立复杂度，不把完整求解说成线性时间。
- 第二问未知真实距离和接收半径。首次收信条件也提供半径下界；必须解释候选区域的收信保证、定位指标及离散搜索局限。
- 第二问保留四圆盘安全域和解析条带上界，融合目标圆条件化与第二读数网格半步增宽。比较选点时统一移动预算、圆盘边数和读数精度，分别报告评分变紧与选点变化，不能将不同上界之差写成真实误差改善。
- 1800米目标圆约束干扰源位置，不限制第二检测点只能在圆内。
- 原文件为权威来源；提取文本可能损失公式排版或图示。
- 第三四问不能把自建环境、mock HTTP或本地奖励写成官方模拟器或官方成绩。每问开发96、留出192、压力96例，种子与误差场固定，策略不访问真值。留出后再调优须更换留出集合并披露。
- 接口读数两位小数，几何误差至少按±1.005°处理；阴性不自动删除定向候选区域，收紧前须验证相应距离/半平面前提。
- 第四问允许检测点在目标圆外；全清终止须完成有证明的覆盖并清除已发现源，或成功清除上限16个，达到10个不能认定完成。
- 官方正式测试每问仅3次，成功启动和手工中止均占次。须先读两份附件，原名保存平台加密日志，本地JSONL不能替代。
- 平台请求串行，同动作重试复用同ID同内容，未知结果不发新动作。clear不切频道，accepted=false不更新状态；读取enter实际剩余时间，结束后不能用exit查询原因。

有实质目录或流程变动时，同步更新此文件和根 `README.md`。
