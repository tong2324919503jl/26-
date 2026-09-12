# 论文正文工作稿

5.2.5分层选点已采用[图14A逐级放大版](figures/problem2_candidates/p2_14_hierarchical_trace/README.md)，正文图为`figures/p2_14a_progressive_zoom.pdf`，以原始矢量PDF插入。`problem2/trace_hierarchical_search.py`记录实际生产调用，`plot_p2_hierarchical_trace.py`按首次访问层着色，提供逐级放大、同尺度分层和两场景对照；保存完整逐层点集及核验结果。重绘后将14A的同名PDF同步至`figures/`及Overleaf，另两版仍作候选。正文区分新增网格与累计候选集，并说明第三层临时优选与最终统一复核的差别。

正文现同步20260912新版演练v5：第三问连续选点；第四问可见性评分、可中断定位及发现路线排序。原v4表和比较图明确标成历史结果，新增表仅转录原包7000例汇总，不称为本次重跑或独立留出。来源与迁移等价验证见 [新版记录](../validation/practice_v5/README.md)。当前仅交付摘要、正文、AI使用声明和参考文献，不制作或并入附录。第三问六次旧版演练可由Git历史中的日志封装头与客户端记录配对；它们不是本轮新代码的平台成绩。第三、四问各三次正式成绩尚未取得完整核对材料，不能称为已经完成正式测试的提交终稿。

- `main.tex`：合并后的Overleaf主文件；`sections/`保留可维护的分节来源。
- `figures/`：正文使用十张图。第一问采用`p1_orthogonal_bearings.pdf`（由用户提供的`两点测向_论文加深版.svg`匹配反例图的正常字重及成稿轴框、刻度线宽后矢量导出，同名英文SVG保留可编辑副本）与`p12_geometry.pdf`（边长40米的覆盖反例）。原始SVG保留；旧PNG不再用于正文。第二问的条带交集图`p2_08_strip_intersection.pdf`选自候选图08，符号、图注及相邻推导由`sections/p12.tex`维护；搜索对照两张PDF图由对应绘图脚本维护。
- `figures/problem2_candidates/`：第二问19张待筛选图，分别展示方法引入、解析条带与几何外包评分、选点与自建数值。样式参照当前第一问正文图，每张附PDF、SVG、高清PNG及图注/来源JSON；[图册](results/p2_figure_catalog.pdf)和[选图说明](figures/problem2_candidates/README.md)供筛选。三个`plot_p2_*_candidates.py`入口只读取原有求解器与结果，`build_p2_figure_catalog.py`生成20页图册、三组总览及图包，本批图02、08、09已并入正文，其余仍作为候选。
- `code/`、`source_snapshot.json`、`code_appendix.*`：用户调整范围前的本地草稿，当前主文件不使用，不属于本次交付内容。
- `sources/`：题录、官方格式、公式及数值出处核对记录，供核验而不直接进入正文。
- 第二问引用范围及核查见 [评分参考文献](../problem2/references.md)：Tokekar–Isler 对应最坏扇区交集直径与几何外包上界框架，Bertsimas 等对应鲁棒可行性，Mavrotas 对应字典序与阈值约束，DIRECT/MCS 仅用于说明全域探索与局部细化思想。Jaulin–Walter 保留为历史核对，不再作为正文依据；条带 A、读数分格与同步增宽 B 由本题推导，10%容差仍为可调整偏好。
- `ai_usage.tex`：使用范围说明的预备草稿，后续整理支撑材料时再核对更新；不作为本次正文交付。
- `results/`：当前正文PDF。此前预备草稿不作为已完成支撑材料交付。
- `figures/p34_candidates/`：上一轮中文候选图及旧方案对照，保留为历史版式；本轮新的分问制图使用下面的入口。
- `figures/problem3/`、`figures/problem4/`：均衡样例的分问图；`plot_balanced_search.py`读取指定批次的当前solve单方案结果，`plot_search_mechanisms.py`读取当前策略配置生成独立机制图。图内只保留必要标签和图例，解释放配套图注。新默认每问7,000例，10至16源各1,000例；构造难度呈截断正态形状，中等最多，不按难度拆分数据子集。算法定稿后的测试与出图使用`python scripts/run_balanced_search.py --run-id normal_v2_final`，详见[使用说明](../validation/balanced_search.md)。旧预览保持原数据口径，本轮不替换正文。

历史v4图表更新流程运行`python paper/plot_search_results.py`重建两张搜索图，再运行`python paper/build_paper.py`合并正文，在`paper/`目录用XeLaTeX编译`main.tex`两次。`plot_geometry.py`及第一、二问两张图保留并行修订内容，本轮不重建。合并入口只生成正文，不冻结程序或生成附录。LaTeX使用既有JXUST模板及项目字体，最终正文保存在`results/paper_body.pdf`。

历史v4第三问为原点反馈触发的条件九环、全向阴性约束、有限前瞻及窄带光学；第四问为22点独立认证布局、共享基线、假想收缩筛选顺路补测及失败后的有界光学修复。完整比较读取`validation/speed_v4/`的同一模拟器、独立进程报告，开发384、留出512、压力256例；阈值分别为220、400秒/源，属于本地目标。光学面积只用于排序，额外最多16次不是独立完成证明。覆盖图只读取当前`coverage_certificate_v4.json`，不沿用旧23点坐标。

上传Overleaf时保留原模板和字体，替换`main.tex`并上传正文引用的PDF图，以XeLaTeX编译。第一、二问图的位置、图注和正文引用直接维护在`sections/p12.tex`，合并入口不额外插图。修订正文后应重新检查引用、页数、图表和编译日志；修订程序或数值结果后应同步核验文中说明与统计。

官方格式以2026修订稿为准：电子版摘要为第一页、无目录、A4四边不少于2.5厘米、摘要起连续页码；正文与AI声明、参考文献合计不超过30页，代码附录另计。未改动既有原始题包及其他开发实验。

本轮标点与评分一排版修订：行间公式不保留末尾英文句号；第一/第二检测相关称谓统一。图08的A(q)双向箭头直接沿长对角线，β₀与A(q)不显示算例数值，标签和图例无白色底块。Overleaf修改基于当前在线主文件，仅同步本轮改动，保留线上第三、四问原有内容；本地`main.tex`和分节来源同步同样的标点及评分一修订。

`results/paper_overleaf_review.pdf`及同名TeX保存本轮在线版本的校样，`results/paper_body.pdf`对应本地生产正文；两者第三、四问原有版本不同，本轮没有把本地第三、四问替换到Overleaf。图08修改后由`plot_p2_scoring_candidates.py`同步正文图文件。

评分二已插入图09`p2_09_reading_cells.pdf`：保留三组角度和直径数值，标签与图例透明、D字号放大，上下图间距缩小。正文按Q、读数单元、Pk、Dk和全部单元最大值B的顺序解释图片，并保留同步增宽证明；脚本同步正文PDF图文件。

图09现采用用户新优化的圆边界版，由`plot_p2_reading_cells_outer_bounds.py`重建并同步`figures/p2_09_reading_cells.pdf`。旧评分候选脚本不再覆盖正文图09；原版保存在`figures/problem2_candidates/p2_09_outer_bounds_trial/original/`。新版(c)以圆圈标明第一距离圆盘的实际裁边；(d)、(e)、(f)分别为目标圆外切边界、第二距离圆外切边界、第一距离圆局部裁边。正文按子图编号引用，区分通用外切构造与(c)实际局部，并交代最下排的非等比例单位。

第一、二问算法流程图与四圆盘图已纳入正文，分别使用`p1_algorithm_flowchart.pdf`、`p2_algorithm_flowchart.pdf`和`p2_02_four_disks.pdf`。流程图依据用户最新中文draw.io稿修订，编辑副本保存在`figures/flowcharts/`；原始draw.io和PNG保留。第一问纠正非零衰退方向的真假分支，第二问明确单元扫描与提前停止顺序；四圆盘图的阴影仅表示`C_safe`。本轮逐条行文精简和四问推导核查见`sources/math_audit_20260912.md`。完整扫描14.821秒、提前停止14.868秒为同一历史冻结记录，正文据实表述耗时基本相当。

本轮移除正文中的`p2_candidates.pdf`及图注，原图文件保留；合并入口同步移除该图，防止重新构建时恢复。第二问流程图改用紧凑均衡的布局，节点浅粉填充，所有文字及分支标签无白色底块，仍保存为`p2_algorithm_flowchart.pdf`。

20260912代码整合后已同步本地分节、摘要、主TeX及PDF；保留第一二问已有图文。历史在线校样 `paper_overleaf_review.*` 保留原貌，不能当作已同步新版的正文。本次整理没有操作Overleaf。
