# 问题 2 评分准则：参考文献与证据边界

核查日期：2026-09-11。以下四篇均取得作者稿全文并核对了相关定义、公式与适用条件；出版信息另与作者或机构记录核对。页码默认指所链接 PDF 的文件页序，从 1 开始，不能直接替换为期刊印刷页码。

**最直接的依据是 Tokekar 与 Isler（2013）的式 (1)：它确实用所有可能目标位置、所有合法示向读数下的“扇区交集直径”评价传感器布置。** 本题将这一思想条件化到已知首读数，并限制第二点保证收信。这个具体单步问题、约束和计算上界仍是本题的建模与推导，不能宣称从某篇论文原样得到。

## 1. 哪篇文献支持哪一步

| 文献 | 全文可核查位置 | 支持的内容 | 不应据此声称 |
| --- | --- | --- | --- |
| **[1] Tokekar、Isler，2013** | [作者 PDF 第 3 页](https://tokekar.com/pubs/tokekar2013asensor.pdf#page=3)，§III-A、§III-B 式 (1)、§III-C | 每次有界示向误差形成扇区；测量融合取交集；对目标位置与合法读数取最坏情形，以交集**直径或面积**评价布置。是本题直径指标及对抗读数思想的直接来源。 | 该文研究方形工作区中的静态多传感器布置与数量，未解本题“已知首读数、未知接收半径、只移动一次”的完整问题；其三角网格近似保证不适用于我们的候选搜索。 |
| **[2] Ceccarelli 等，2011** | [作者 PDF 第 4 页](https://www3.diism.unisi.it/~control/MAS/papers/ACSP10.pdf#page=4)，§2 式 (3)–(4)；[第 7–9 页](https://www3.diism.unisi.it/~control/MAS/papers/ACSP10.pdf#page=7)，§3 式 (14)、(17) 后的讨论、§3.1 | 未知但有界误差下用可行集表示定位结果，将可行集大小用于路径选择，并考虑有限可见范围。文中明确讨论了对噪声取最坏值的 min–max 方案。 | 其主目标是路径上的平均可行集**体积**；因完整 min–max 太复杂，实际规划改用零噪声预测。不能写成该文已实现“最坏读数下直径最小”的算法。场景是机器人对已知地标的距离与方位观测。 |
| **[3] Gholami 等，2015** | [机构作者稿 PDF 第 3 页](https://publications.lib.chalmers.se/records/fulltext/218784/local_218784.pdf#page=3)，§II 假设 2、式 (6)–(14)；[第 4 页](https://publications.lib.chalmers.se/records/fulltext/218784/local_218784.pdf#page=4)，§III 式 (15)–(19) | 有界 AOA 误差生成半平面交；对**给定估计位置**，到可行集顶点的最大距离给出最坏位置误差；另讨论最小体积外包椭球。可核对集合几何及“最坏位置误差”的含义。 | 该文不是区域直径选点，也未优化最小覆盖圆圆心。式 (16) 的固定中心最坏距离，不能称为区域直径或最优中心的 minimax 半径。其式 (5) 的重复观测估界不用于本题固定同点误差。 |
| **[4] Zhao、Chen、Lee，2013** | [作者预印本 PDF 第 5–6 页](https://arxiv.org/pdf/1210.7397#page=5)，§III-A 式 (6)、§III-B 问题 3.1 式 (7) | 方位传感器相对几何会改变定位信息；在其高斯噪声、固定传感器到目标距离等条件下，用 Fisher 信息矩阵设计布置。用于解释另一类常见评价范式。 | 该文主目标为 FIM 与各向同性矩阵差的平方范数，不能笼统写成“直接最小化直径”，也不能不加说明地称其主目标为 D-optimality。本题只有误差界，不能直接继承其概率模型与最优构型。 |

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

## 4. 可直接放入解答正文的文字

题设仅给出示向误差的确定性界，而未指定概率分布，因此本文采用集合定位：将每次观测转换为可能源位置的约束，并与已有信息求交。Tokekar 与 Isler 在有界示向误差的传感器布置研究中，明确以所有合法目标位置和读数下的扇区交集直径衡量最坏定位不确定性 [1]。据此，并与第一问的区域直径指标保持一致，本文在固定首次观测后，以 $J_D(q)=\sup_{\psi\in\Psi(q)}\operatorname{diam}U(q,\psi)$ 评价保证收信的第二检测点。该单步、安全约束下的目标是针对本题的条件化建模，不直接继承文献的最优布置或近似比例。数值实现比较 $J_D$ 的保守上界，所得结果仅在已访问候选集合内比较；实际光学定位是否能覆盖全部可能源，另以最小覆盖圆半径判断。

## 5. 完整参考信息与核查链接

**[1]** Tokekar, P.; Isler, V. *Sensor Placement and Selection for Bearing Sensors with Bounded Uncertainty*. 2013 IEEE International Conference on Robotics and Automation (ICRA), 2013, pp. 2515–2520. DOI: [10.1109/ICRA.2013.6630920](https://doi.org/10.1109/ICRA.2013.6630920)。[作者全文](https://tokekar.com/pubs/tokekar2013asensor.pdf)；[明尼苏达大学出版记录](https://experts.umn.edu/en/publications/sensor-placement-and-selection-for-bearing-sensors-with-bounded-u)。本文核对的是 6 页会议作者稿，不混用长篇技术报告的页码或定理编号。

**[2]** Ceccarelli, N.; Di Marco, M.; Garulli, A.; Giannitrapani, A.; Vicino, A. *Path Planning with Uncertainty: A Set Membership Approach*. International Journal of Adaptive Control and Signal Processing, 2011, 25(3): 273–287. DOI: [10.1002/acs.1217](https://doi.org/10.1002/acs.1217)。[作者全文，21 页版本](https://www3.diism.unisi.it/~control/MAS/papers/ACSP10.pdf)；[作者研究组记录](https://www3.diism.unisi.it/~control/MAS/publication/cdggv-11/)；[出版社记录](https://onlinelibrary.wiley.com/doi/abs/10.1002/acs.1217)。出版社线上首发为 2010-12-03，卷期年份为 2011。

**[3]** Gholami, M. R.; Gezici, S.; Wymeersch, H.; Ström, E. G.; Jansson, M. *Characterizing the Worst-Case Position Error in Bearing-Only Target Localization*. 12th Annual Workshop on Positioning, Navigation and Communication (WPNC), Dresden, Germany, March 2015, invited paper. [Chalmers 机构作者稿](https://publications.lib.chalmers.se/records/fulltext/218784/local_218784.pdf)；[机构记录](https://research.chalmers.se/en/publication/218784)；[作者 Jansson 的出版目录，第 124 项](https://people.kth.se/~janssonm/MJpubs150915.pdf)。所核机构记录与作者稿没有列出 DOI 和会议印刷页码，故不补猜；文件共 6 页，第 1 页为机构封面，引用正文位置时已计入封面。

**[4]** Zhao, S.; Chen, B. M.; Lee, T. H. *Optimal Sensor Placement for Target Localization and Tracking in 2D and 3D*. International Journal of Control, 2013, 86(10): 1687–1704. DOI: [10.1080/00207179.2013.792606](https://doi.org/10.1080/00207179.2013.792606)。[作者预印本 arXiv:1210.7397](https://arxiv.org/abs/1210.7397)；[全文](https://arxiv.org/pdf/1210.7397)；[作者 Chen 的期刊目录，第 108 项](https://www.mae.cuhk.edu.hk/~bmchen/journal.html)。上述公式定位使用 25 页预印本，期刊版页码不能直接套用。该条用于 FIM 范式的对照，不作为本题集合直径目标的直接依据。

文献支持方法思想，不是本仓算例的官方验证。所有本地算例、连续上界推导、候选网格和数值结果均应按各自证据范围陈述；同一位置固定误差的题设也不会因为引用其他测量模型而改变。
