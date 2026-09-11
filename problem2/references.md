# 问题 2 评分准则：参考文献与证据边界

核查日期：2026-09-11。本轮核对重点为 [1] 的最坏直径准则与几何外包框架，以及新增 [8]、[9] 的全域探索和局部细化思想；[6]、[7] 分别对应鲁棒可行性及字典序与阈值约束。[5] 移至第 7 节作为历史核对，不再作为正文依据。本底稿保留固定索引 [1]—[9]，不等于论文按首次引用顺序编排的参考文献编号。页码默认指所链接 PDF 的文件页序，从 1 开始，不能直接替换为期刊印刷页码。

**最直接的依据是 Tokekar 与 Isler（2013）的式 (1)：它确实用所有可能目标位置、所有合法示向读数下的“扇区交集直径”评价传感器布置。** 本题将这一思想条件化到已知首读数，并限制第二点保证收信。这个具体单步问题、约束和计算上界仍是本题的建模与推导，不能宣称从某篇论文原样得到。

## 1. 哪篇文献支持哪一步

| 文献 | 全文可核查位置 | 支持的内容 | 不应据此声称 |
| --- | --- | --- | --- |
| **[1] Tokekar、Isler，2013** | [会议作者稿第 3 页](https://tokekar.com/pubs/tokekar2013asensor.pdf#page=3)，§III-A、§III-B 式 (1)；[第 5 页](https://tokekar.com/pubs/tokekar2013asensor.pdf#page=5)，§V-A Lemma 3、4 | 有界示向误差形成扇区，融合取交集；式 (1) 直接支持对目标位置与合法读数取最坏交集直径。Lemma 3、4 提供通过几何包络控制不确定区域上界的框架。 | 其静态多传感器布置与本题已知首读数的单步选点不同；原文几何界不能替代本文条带 A、读数分格及同步增宽 B 的推导，也不提供本题候选搜索的近似保证。 |
| **[2] Ceccarelli 等，2011** | [作者 PDF 第 4 页](https://www3.diism.unisi.it/~control/MAS/papers/ACSP10.pdf#page=4)，§2 式 (3)–(4)；[第 7–9 页](https://www3.diism.unisi.it/~control/MAS/papers/ACSP10.pdf#page=7)，§3 式 (14)、(17) 后的讨论、§3.1 | 未知但有界误差下用可行集表示定位结果，将可行集大小用于路径选择，并考虑有限可见范围。文中明确讨论了对噪声取最坏值的 min–max 方案。 | 其主目标是路径上的平均可行集**体积**；因完整 min–max 太复杂，实际规划改用零噪声预测。不能写成该文已实现“最坏读数下直径最小”的算法。场景是机器人对已知地标的距离与方位观测。 |
| **[3] Gholami 等，2015** | [机构作者稿 PDF 第 3 页](https://publications.lib.chalmers.se/records/fulltext/218784/local_218784.pdf#page=3)，§II 假设 2、式 (6)–(14)；[第 4 页](https://publications.lib.chalmers.se/records/fulltext/218784/local_218784.pdf#page=4)，§III 式 (15)–(19) | 有界 AOA 误差生成半平面交；对**给定估计位置**，到可行集顶点的最大距离给出最坏位置误差；另讨论最小体积外包椭球。可核对集合几何及“最坏位置误差”的含义。 | 该文不是区域直径选点，也未优化最小覆盖圆圆心。式 (16) 的固定中心最坏距离，不能称为区域直径或最优中心的 minimax 半径。其式 (5) 的重复观测估界不用于本题固定同点误差。 |
| **[4] Zhao、Chen、Lee，2013** | [作者预印本 PDF 第 5–6 页](https://arxiv.org/pdf/1210.7397#page=5)，§III-A 式 (6)、§III-B 问题 3.1 式 (7) | 方位传感器相对几何会改变定位信息；在其高斯噪声、固定传感器到目标距离等条件下，用 Fisher 信息矩阵设计布置。用于解释另一类常见评价范式。 | 该文主目标为 FIM 与各向同性矩阵差的平方范数，不能笼统写成“直接最小化直径”，也不能不加说明地称其主目标为 D-optimality。本题只有误差界，不能直接继承其概率模型与最优构型。 |
| **[6] Bertsimas 等，2011** | [50页作者稿第8–9页](https://arxiv.org/pdf/1010.5445#page=8)，§2.1 式(2.3)及其后第一个项目 | 鲁棒约束对不确定集合的所有情形成立；不确定目标可写成最坏值不超过辅助变量，再最小化该变量。支持先保证收信、再比较最坏定位损失。 | 不证明四圆盘公式、本题凸性或连续全局最优；原文第10页也指出一般鲁棒问题不自动易解。作者稿文件页序与期刊页码不混用。 |
| **[7] Mavrotas，2009** | 刊印第456页 §2 式(2)，第458页 §3.1，458–460页 §3.2；[GAMS官方作者配套稿](https://www.gams.com/modlib/adddocs/epscm.pdf)第3页式(2)、第7–8页 §4.1 | 字典序表示高优先目标最优后再优化次目标；$\epsilon$-约束法表示优化一个目标、其余转为阈值。分别对应默认精度优先及近优精度内选短路程。 | 不证明10%最优；不代表当前程序实现了 AUGMECON。普通约束法可能只有弱有效解，本文亦有数值舍入，不能宣称连续或精确实数意义的严格 Pareto 最优。配套稿不是原刊同版。 |
| **[8] Jones、Perttunen、Stuckman，1993（新增）** | [原文](https://dumas.perso.math.cnrs.fr/DIRECT.pdf)，§3 潜在最优区间、§4 多维推广；[出版社摘要与题录](https://link.springer.com/article/10.1007/BF00941892) | DIRECT 同时考虑矩形尺度与中心函数值，在全域探索与局部细化之间分配计算。本文仅借鉴这一搜索思想。 | 当前极坐标分层网格未实现潜在最优矩形筛选、矩形划分等 DIRECT 规则，不继承其全局收敛证明；本题逐层提高读数评分精度亦为自己的实现安排。 |
| **[9] Huyer、Neumaier，1999（新增）** | [作者原稿](https://arnold-neumaier.at/ms/mcs.pdf)，§2–4 分层搜索及坐标分裂；[出版社摘要与题录](https://link.springer.com/article/10.1023/A:1008382309369) | MCS 以盒的层级协调全域探索与局部搜索，并可从优良点启动局部优化。本文仅借鉴对候选邻域继续细化的思想。 | 本文没有 MCS 的盒层级、坐标分裂及局部模型规则，不是 MCS 的实现，也不能引用其收敛保证证明有限候选搜索的连续全局最优。 |

## 2. 本题公式与直接文献的关系

文献 [1] 的 §III-B 式 (1) 为

$$
U_D(S)=\max_{x\in A}\max_{\theta^m\in\theta(x)}
\operatorname{diam}\bigl(\widehat P(S,\theta^m)\bigr).
$$

这里 $S$ 是传感器布置，$A$ 是可能目标工作区，$\theta(x)$ 是目标位于 $x$ 时可能产生的合法读数集合，$\widehat P$ 是相应测向扇区的交集。[作者原文](https://tokekar.com/pubs/tokekar2013asensor.pdf#page=3)

在本题中，首次观测已经发生。因此固定这条观测及题设先验，得到首验可行集 $U_1$；再对每个保证收信的候选第二点 $q$，定义可能第二读数集合

$$
\Psi(q)=\{\psi:\ \text{存在与首观测和全部题设约束相容的源位置及接收半径，使 }q\text{ 能产生正常读数 }\psi\}.
$$

令 $U(q,\psi)$ 表示收到该读数后、与全部已知信息相容的源位置集合。本题采用

$$
\boxed{J_D(q)=\sup_{\psi\in\Psi(q)}\operatorname{diam}U(q,\psi),\qquad
q_*\in\arg\min_{q\in\mathcal F}J_D(q).}
$$

**这是对 [1] 的最坏集合直径准则进行条件化，并结合题设第一问直径指标形成的本题选择。** 首次读数不再重新参与对抗选择；$\mathcal F$ 与当前实现一致，是四圆盘安全域、移动预算圆以及保证第二次正常测向的区域之交。最后一项是为统一比较正常读数分支作的保守限制，不表示 near 不好；详见 [统一模型](README.md)。用 $\sup$ 可避免在开放约束或退化边界上未经证明地假设最大值一定达到。若候选点可能失收，便不能只对其成功读数分支评分而仍称它保证定位；应先排除该点，或另行给失收分支定义代价。

这个准则不需要给误差指定高斯或均匀分布。它衡量“最不利合法读数发生后还剩多大的位置歧义”，不是对已知真值算出的实际定位误差，也不是平均成绩。相比面积，直径可直接排除很细长而仍有较大最远距离的候选区域；选择它也与第一问保持一致。这是本题的目标解释，不是文献证明直径对所有定位任务都优于其他指标。

实现采用外包几何和读数半格增宽构造 $C(q)\ge J_D(q)$，并在有限访问候选中比较 $C(q)$。因此输出应称为“已访问候选中较小的最坏直径上界”，不能说已计算连续 $J_D$ 的精确值或已证明第二点连续全局最优。这些上界的有效性由本题包含关系推导负责，不能以文献 [1] 的近似定理替代。

[1] 的会议版 §V-A Lemma 3、4 给出特定传感器构型下的几何上界。[作者上传的配套技术报告](https://www.researchgate.net/publication/261416273_Sensor_placement_and_selection_for_bearing_sensors_with_bounded_uncertainty)附录 B.1 Lemma 7（文件第 15–18 页）以风筝形外包及其对角线式 (1)、(2) 展开证明，附录 B.2 第 24 页另讨论大扇区外包；这些构造不能改称为本文的相交条带上界 A。技术报告仅供补充核对，正文引用仍对应 ICRA 会议版。本文 B 所用第二读数分格、扇区与投影下界及条带的同步增宽，以及 $C=\min(A,B)$ 的提前停止，均由本题自行推导。

## 3. 区域直径与 minimax 点估计半径不能混同

对一个已经形成的非空有界可行集 $U$，三个不同量为

$$
D(U)=\sup_{x,y\in U}\|x-y\|,\qquad
E(\widehat x;U)=\sup_{x\in U}\|\widehat x-x\|,\qquad
R_*(U)=\inf_c\sup_{x\in U}\|c-x\|.
$$

它们依次表示区域直径、**固定估计点**的最坏误差、可选择最优中心的 minimax 点估计半径。文献 [3] 的式 (16) 对应中间量 $E$；它并没有把外层对中心的 $\inf_c$ 也做掉。[机构作者稿 §III](https://publications.lib.chalmers.se/records/fulltext/218784/local_218784.pdf#page=4)

若目标是“第二次观测后选一个位置，使到任意可能源的最坏距离最小”，则另一种合理的主动准则是

$$
J_R(q)=\sup_{\psi\in\Psi(q)}R_*\bigl(U(q,\psi)\bigr).
$$

这是与 $J_D$ 不同的优化任务：圆心可在第二读数之后选择。平面上 $D/2\le R_*\le D/\sqrt3$，所以直径能够提供半径界，但不能一般地令 $R_*=D/2$，也不能据此宣称两个评分必定得到相同第二点。对应证明和可实现三角形反例见 [第一问说明](../problem1/README.md)。题设 20 米光学定位保证应使用 $R_*\le20$；若手中只有保证直径上界 $C$，可用 $C\le20\sqrt3$ 作为充分条件。

## 4. 从文献到当前筛选策略：每一步解决什么问题

| 筛选环节 | 本题含义 | 依据及归属 |
| --- | --- | --- |
| 用集合表示不确定位置 | 所有符合两次误差界、距离及目标圆约束的位置都保留，不假设其概率 | [1] §III-A 的扇区交集模型；距离及目标圆约束由题设推导 |
| 先筛安全域 $\mathcal F$ | 不允许以较好的交会几何补偿可能失收；收信是硬约束 | [6] 的对全部相容情形保证可行；四圆盘公式是本题证明 |
| 比较 $J_D$ | 第二读数尚未知，评价它最不利时还剩多少位置歧义 | [1] 的最坏集合直径准则 |
| 用 $C=\min(A,B)$ 计算保证 | 两个上界约束同一 $J_D$，取较小者仍有效 | [1] §V-A 提供几何外包上界框架；A、B、半格增宽与提前停止由本题自行推导 |
| 分层搜索候选点 | 先访问粗网格，再细化当前最佳点及镜像方位的邻域，最终统一精度复核 | 仅借鉴 [8]、[9] 兼顾全域探索和局部细化的思想，不采用其具体算法或收敛证明 |
| 默认精度优先 | 只有定位评分数值相同才比较移动距离 | [7] 的字典序思想；优先级是本题选择 |
| 可选“精度达标后缩短路程” | 保留上界不超过指定阈值的候选，再最小化本次移动时间 | [7] 的$\epsilon$-约束思想；容差是决策偏好 |

设 $\mathcal V\subset\mathcal F$ 为已访问有限候选集，$d(q)=\|q\|$ 为移动距离。理想的精度优先规则写成
$\operatorname{lexmin}_{q\in\mathcal V}(C(q),d(q))$：
先最小化第一项，再在其最优解中最小化第二项。程序使用 $\widetilde C(q)=\operatorname{round}(C(q),7)$ 判定浮点平局，故严格说实际筛选的是 $(\widetilde C,d)$；若其推荐点为 $q_*$，则阈值基准定义为 $C_*=C(q_*)$，不把它无条件称为未舍入实数意义的 $\min C$。

对于可选的短路程方案，定义

$
\tau_C=(1+\eta)C_*,\qquad
q_\eta\in\arg\min_{q\in\mathcal V}d(q)
\quad\text{s.t.}\quad C(q)\le\tau_C.
$

这是将定位要求变成阈值约束的做法。[7] 中“$\epsilon$-约束”的 $\epsilon$ 是目标阈值，**与本题示向误差 $\varepsilon=1^\circ$ 不同**。由于本次移动与检测时间 $T(q)=d(q)/5+5$ 单调随路程增加，最小化 $d$ 与最小化这项时间等价。因此移动距离只负责解释执行代价，无需给“米”和“秒”指定任意加权和。

默认 $\eta=10\%$ 表示允许**保证上界**相对推荐点放宽10%，不是实际定位误差增加10%、失败概率10%，也不是文献证明的最优参数。该备选不替换默认精度优先推荐。若要主张10%特别合适，还需预先规定精度与时间偏好并做容差敏感性分析，不能仅靠引用文献得出。

实现中的阈值比较另允许 $10^{-9}$ 米边界容差，仅用于浮点边界处理。

候选生成对应 [solve.py](solve.py) 的 `choose_second_refined`：默认三层的移动距离、移动方位、读数评分步长依次为 $(100\text{米},5^\circ,1^\circ)$、$(20\text{米},1^\circ,0.5^\circ)$、$(5\text{米},0.25^\circ,0.25^\circ)$。首层访问全域粗网格，后续围绕当前最佳点及镜像方位细化；各层保留旧候选，并加入解析推荐点和安全径向边界。最后对全部已访问候选用 $0.1^\circ$ 的第二读数网格统一评分。这里的“层”是固定网格与评分步长，不是 [9] 的盒层级；逐层提高评分精度也不是 [8]、[9] 提供的机制。

还应保留三条解释边界：

- **上界排序不必等于真实损失排序。** $C(q_1)<C(q_2)$ 只说明前者的已证明保证更紧，并不能推出未知的 $J_D(q_1)<J_D(q_2)$，更不是实际误差排序。统一圆边数和读数精度，是为了尽量避免数值放松差异主导比较。
- **“最坏”来自题设不确定集合，“保守余量”还来自计算外包。** 不指定概率分布时，无法把有限样本平均值说成期望最优；当前选择是有保证的决策标准，并非所有定位任务唯一合理的指标。面积、最小覆盖半径和FIM各有不同含义。
- **引用不替代实现证明。** 当前提前停止是利用 $b_t\le B$ 和 $b_t\ge A$ 得出 $\min(A,B)=A$；与[7]的AUGMECON循环退出不是同一算法。非劣输出仅对应有限已访问集合和规定数值精度。

## 5. 可直接放入解答正文的文字

本文将有界示向误差对应的扇区相交，并加入距离与目标圆约束，以所有相容第二读数下的候选区域直径 $J_D(q)$ 衡量最坏位置歧义 [1]；对全部相容源位置和接收半径的收信要求作为鲁棒可行性约束 [6]。借鉴 DIRECT 与多层坐标搜索兼顾全域探索和局部细化的思想 [8,9]，先进行粗网格搜索，再细化当前最佳点及镜像方位的邻域，最后以统一精度的上界 $C(q)$ 复核全部已访问候选。默认按定位保证优先、移动距离次优的字典序筛选，另借鉴$\epsilon$-约束思想 [7]，提供在 $C(q)\le(1+\eta)C(q_*)$ 条件下移动距离最短的备选。$\eta=10\%$ 为可调整容差，仅约束评分上界的放宽；文献并不证明该取值最优。本文未实现 DIRECT 或 MCS 的具体划分规则，所有选择均限于已访问候选集合，不继承其全局收敛保证。

## 6. 完整参考信息与核查链接

**[1]** Tokekar, P.; Isler, V. *Sensor Placement and Selection for Bearing Sensors with Bounded Uncertainty*. 2013 IEEE International Conference on Robotics and Automation (ICRA), 2013, pp. 2515–2520. DOI: [10.1109/ICRA.2013.6630920](https://doi.org/10.1109/ICRA.2013.6630920)。[作者全文](https://tokekar.com/pubs/tokekar2013asensor.pdf)；[明尼苏达大学出版记录](https://experts.umn.edu/en/publications/sensor-placement-and-selection-for-bearing-sensors-with-bounded-u)。本文核对的是 6 页会议作者稿，不混用长篇技术报告的页码或定理编号。

**[2]** Ceccarelli, N.; Di Marco, M.; Garulli, A.; Giannitrapani, A.; Vicino, A. *Path Planning with Uncertainty: A Set Membership Approach*. International Journal of Adaptive Control and Signal Processing, 2011, 25(3): 273–287. DOI: [10.1002/acs.1217](https://doi.org/10.1002/acs.1217)。[作者全文，21 页版本](https://www3.diism.unisi.it/~control/MAS/papers/ACSP10.pdf)；[作者研究组记录](https://www3.diism.unisi.it/~control/MAS/publication/cdggv-11/)；[出版社记录](https://onlinelibrary.wiley.com/doi/abs/10.1002/acs.1217)。出版社线上首发为 2010-12-03，卷期年份为 2011。

**[3]** Gholami, M. R.; Gezici, S.; Wymeersch, H.; Ström, E. G.; Jansson, M. *Characterizing the Worst-Case Position Error in Bearing-Only Target Localization*. 12th Annual Workshop on Positioning, Navigation and Communication (WPNC), Dresden, Germany, March 2015, invited paper. [Chalmers 机构作者稿](https://publications.lib.chalmers.se/records/fulltext/218784/local_218784.pdf)；[机构记录](https://research.chalmers.se/en/publication/218784)；[作者 Jansson 的出版目录，第 124 项](https://people.kth.se/~janssonm/MJpubs150915.pdf)。所核机构记录与作者稿没有列出 DOI 和会议印刷页码，故不补猜；文件共 6 页，第 1 页为机构封面，引用正文位置时已计入封面。

**[4]** Zhao, S.; Chen, B. M.; Lee, T. H. *Optimal Sensor Placement for Target Localization and Tracking in 2D and 3D*. International Journal of Control, 2013, 86(10): 1687–1704. DOI: [10.1080/00207179.2013.792606](https://doi.org/10.1080/00207179.2013.792606)。[作者预印本 arXiv:1210.7397](https://arxiv.org/abs/1210.7397)；[全文](https://arxiv.org/pdf/1210.7397)；[作者 Chen 的期刊目录，第 108 项](https://www.mae.cuhk.edu.hk/~bmchen/journal.html)。上述公式定位使用 25 页预印本，期刊版页码不能直接套用。该条用于 FIM 范式的对照，不作为本题集合直径目标的直接依据。

**[6]** Bertsimas, D.; Brown, D. B.; Caramanis, C. *Theory and Applications of Robust Optimization*. SIAM Review, 2011, 53(3): 464–501. DOI: [10.1137/080734510](https://doi.org/10.1137/080734510)。[作者稿 arXiv:1010.5445](https://arxiv.org/abs/1010.5445)；[50页全文](https://arxiv.org/pdf/1010.5445)。本表定位采用该作者稿文件页序，非期刊页码。

**[7]** Mavrotas, G. *Effective Implementation of the ε-constraint Method in Multi-Objective Mathematical Programming Problems*. Applied Mathematics and Computation, 2009, 213(2): 455–465. DOI: [10.1016/j.amc.2009.03.037](https://doi.org/10.1016/j.amc.2009.03.037)。[GAMS官方模型页](https://www.gams.com/latest/gamslib_ml/libhtml/gamslib_epscm.html)列出正式论文并链接[作者配套稿](https://www.gams.com/modlib/adddocs/epscm.pdf)。本轮亦核对[原刊全文镜像](https://www.researchgate.net/profile/Mohamed_Mourad_Lafifi/post/What_is_stopping_criteria_of_the_epsilon_constraint_optimization_algorithm_for_multi_objective_optimization_problems/attachment/59d64e0f79197b80779a77a9/AS%3A490975777824768%401494069155557/download/Mavrotas.pdf)的刊印页码。原刊11页，配套稿12页且题名不同，两版位置不得互换。

**[8]** Jones, D. R.; Perttunen, C. D.; Stuckman, B. E. *Lipschitzian Optimization Without the Lipschitz Constant*. Journal of Optimization Theory and Applications, 1993, 79(1): 157–181. DOI: [10.1007/BF00941892](https://doi.org/10.1007/BF00941892)。[出版社记录](https://link.springer.com/article/10.1007/BF00941892)；[出版社第 79 卷第 1 期目录](https://link.springer.com/journal/10957/volumes-and-issues/79-1)；[刊印原文 PDF](https://dumas.perso.math.cnrs.fr/DIRECT.pdf)。全文共 25 页，第 1 页为刊印 157 页；§3、§4 分别给出一维与多维 DIRECT 规则，§5 讨论收敛。

**[9]** Huyer, W.; Neumaier, A. *Global Optimization by Multilevel Coordinate Search*. Journal of Global Optimization, 1999, 14(4): 331–355. DOI: [10.1023/A:1008382309369](https://doi.org/10.1023/A:1008382309369)。[出版社记录](https://link.springer.com/article/10.1023/A:1008382309369)；[出版社第 14 卷第 4 期目录](https://link.springer.com/journal/10898/volumes-and-issues/14-4)；[作者原稿](https://arnold-neumaier.at/ms/mcs.pdf)；[作者算法主页](https://arnold-neumaier.at/software/mcs/)。作者原稿页脚日期为 1998 年，不改变期刊卷期年份 1999；原稿文件页码与刊印页码分别使用。

## 7. 历史核对：不再作为本轮正文依据

**[5]** Jaulin, L.; Walter, E. *Set Inversion via Interval Analysis for Nonlinear Bounded-error Estimation*. Automatica, 1993, 29(4): 1053–1064. DOI: [10.1016/0005-1098(93)90106-4](https://doi.org/10.1016/0005-1098(93)90106-4)。[作者提供的刊印全文](https://www.ensta-bretagne.fr/jaulin/paper_automatica93.pdf)，12 页，文件第 1 页即刊印 1053 页。此前核对过 §1 式 (1)–(3) 与 §4.2，现仅保留题录和核查记录，不再建议作为本文几何外包的引用依据。本文没有采用该文的 SIVIA 区间算法，其收敛结论不适用于当前浮点多边形计算。

文献支持方法思想，不是本仓算例的官方验证。所有本地算例、连续上界推导、候选网格和数值结果均应按各自证据范围陈述；同一位置固定误差的题设也不会因为引用其他测量模型而改变。
