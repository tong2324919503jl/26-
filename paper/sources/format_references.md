# 官方格式与参考文献核验（2026-09-11）

本文件仅作论文整合依据，不是提交论文。已读仓库 `docs/background/beijing_contest_notes.pptx`（原名“北京赛区注意事项(1).pptx”） 的原始 slide XML；赛题依据 `materials/problem_b/statement.pdf` 的检索副本；论文格式与 AI 规定另与全国组委会当前原文核对。参考文献优先核对作者全文、作者机构出版记录和出版社页面。

## 1. 应直接落实的格式

| 项目 | 本次应采用的要求 | 精确依据 |
|---|---|---|
| 电子版首部 | 第一页就是摘要专用页，不放承诺书、编号页，不作学校封面 | 全国 2026 格式第十条；北京 PPT 第4页 |
| 摘要 | 题目、摘要、关键词合计原则上一页；无需英文翻译 | 全国第三条；北京 PPT 第4页 |
| 正文 | 不要目录；正文不超过30页 | 全国第四条 |
| 正文计页范围 | 正文主体、AI工具使用声明、参考文献均计入30页；附录不限页 | 北京 PPT 第4页作出明确说明 |
| 纸张边距 | A4，上下左右至少2.5厘米 | 全国第一条 |
| 字体字号 | 全国没有统一规定字号、字体、行距、颜色；可沿用现有清晰版式 | 全国第八条；已读北京 PPT 未发现更具体的字体字号规定 |
| 页码 | 从摘要起用阿拉伯数字1连续编号，位于页脚中部 | 全国第三条 |
| 引用 | 所有借用成果列参考文献，并在正文相应位置标注 | 全国第七条 |
| 附录代码 | 同一论文文件的附录内应有全部完整、可运行源代码，不能仅放算法伪码或入口脚本 | 全国第五条；北京 PPT 第4—5页 |
| 支撑材料目录 | 列入论文附录；所有可运行源程序还须另放支撑材料 | 全国第五、十一条；北京 PPT 第4—5页 |
| 文件规格 | 论文单文件PDF或Word，推荐PDF，不压缩，≤20MB；支撑材料一个RAR或ZIP，≤20MB | 全国第十、十一条 |
| 匿名 | 摘要、正文、附录及支撑文件内容、文件属性、内部文件名均不得泄露参赛者/学校/赛区身份 | 全国第六、十一条；北京 PPT 第5页 |
| 北京补交 | 全国系统提交之外，校内另收电子版和签字承诺书；此为北京/校内流程，不能泛化为全国线上正文格式 | 北京 PPT 第6、11—13页 |

全国官方格式：[网页原文](https://www.mcm.edu.cn/html_cn/node/4cd596519c9eb9fbd866398f6df0caa3.html)，发布于2026-03-03；[官方PDF](https://www.mcm.edu.cn/upload_cn/node/775/cQMeL0YY905244c8bd4b9af832f1699446d8385e.pdf)，2页。

### AI 声明与支撑文件

全国2026试行规定自2026-09-01生效，明确允许辅助使用AI，但核心建模分析由参赛队主导，AI参与内容逐项人工审查核实。参考文献**之前**必须有“AI工具使用声明”；支撑材料须有精确文件名 `AI工具使用详情.pdf`，包含工具名称/版本、具体目的和环节、提示方式和过程，以及采纳、人工修改和核验情况。来源：[全国官方2026规定](https://www.mcm.edu.cn/html_cn/node/fef94648f2836ab6cc81586f4c38512b.html)，第2—4条；北京 PPT 第9—10页一致。

可用声明（与当前实质用途一致，不可缩写成只有“语言润色”）：

```latex
\section*{AI工具使用声明}
本参赛队在竞赛过程中使用了AI工具，主要用于建模思路讨论、程序实现与调试、实验结果整理、参考文献核查及论文撰写辅助，详细使用情况见支撑材料。
```

注意：这段只陈述使用范围，没有替参赛队虚构“已逐项完成人工审查”。支撑说明中的人工修改与核验必须写已实际发生的内容；未发生的工作不能写成已完成。自动程序验证与人工审查也是不同事项。

### 本题额外的结果材料

原题第1—2页要求第三、四问在充分演练后各做三次正式测试，正文按原表四列列出“测试案例编码、清除干扰源个数、平均定位清除时间、程序运行时间”；三次正式日志按原名放支撑材料。不能用本地合成案例或普通在线联调记录代替这些正式结果。当前需以实存日志/摘要中明确的测试类型证据判定，不能凭 `online/` 目录名推断。

## 2. 推荐参考文献（8项；按需要引用，不必全部塞进正文）

### [1] 集合定位与最坏直径指标：最直接、建议必用

**TOKEKAR P, ISLER V. Sensor placement and selection for bearing sensors with bounded uncertainty[C]//2013 IEEE International Conference on Robotics and Automation. IEEE, 2013: 2515–2520. DOI: 10.1109/ICRA.2013.6630920.**

- 主源：[作者全文](https://tokekar.com/pubs/tokekar2013asensor.pdf)；[明尼苏达大学题录](https://experts.umn.edu/en/publications/sensor-placement-and-selection-for-bearing-sensors-with-bounded-u/)。已本轮核对作者、题名、会议、页码、DOI及全文式(1)。
- 精确内容：6页作者稿第3页 §III-B 式(1)，在目标位置和所有合法测向读数上取最坏值，以扇区交集直径评价布置；§III-A说明有界角误差对应楔形。
- 文内落点：第二问目标函数前；也可在集合建模总述处引用。
- 可写：“借鉴有界测向误差下的最坏交集直径准则\cite{tokekar2013}，固定首次观测后，以所有相容第二读数形成区域的最大直径评价候选点。”
- 边界：该文是方形区域静态多传感器布置。本题四圆盘、安全收信、已知首读数条件化、半格增宽与提前停止均为本题构造，不能归给此文；其近似倍数也不能移植。

### [2] AOA 半平面交与固定中心最坏误差：建议使用

**GHOLAMI M R, GEZICI S, WYMEERSCH H, et al. Characterizing the worst-case position error in bearing-only target localization[C]//Workshop on Positioning, Navigation and Communication. 2015.**

- 主源：[Chalmers作者稿](https://publications.lib.chalmers.se/records/fulltext/218784/local_218784.pdf)；[机构题录](https://research.chalmers.se/en/publication/218784)。5位作者依次为 Mohammad Reza Gholami、Sinan Gezici、Henk Wymeersch、Erik G. Ström、Magnus Jansson。机构未列 DOI/印刷页码，勿补猜。
- 精确内容：文件第3页 §II 式(7)—(14)，有界示向误差构成半平面交；第4页 §III 式(16)，固定估计点到顶点的最大距离界。
- 文内落点：第一問半平面表达式后；或区分直径与覆盖半径处。
- 可写：“将误差扇区表示为半平面交，得到与全部观测相容的位置集合\cite{gholami2015}。”
- 边界：固定估计点最坏误差、区域直径、可自由选圆心的最小覆盖半径是三个不同量。不要继承其重复观测估计误差界的方案，也不要把最小体积椭球误写成最小覆盖圆。

### [3] 旋转卡壳：建议必用

**TOUSSAINT G T. Solving geometric problems with the rotating calipers[C]//Proceedings of IEEE MELECON '83. Athens, Greece, 1983.**

- 主源：[作者所在McGill原文](https://cgm.cs.mcgill.ca/~godfried/publications/calipers.pdf)。原文脚注核实1983年5月、雅典IEEE MELECON；此扫描PDF为8页，内部顺序倒置，开头正文实际在文件第8页。
- 精确内容：Introduction叙述遍历对踵顶点对，以其最大距离求凸多边形直径，所需时间为顶点数的线性量级。
- 文内落点：第一问旋转卡壳算法介绍处。
- 可写：“对已按环序排列的凸多边形顶点，采用旋转卡壳遍历对踵点对\cite{toussaint1983}。”
- 边界：不写“Toussaint首次提出直径算法”（文中归于Shamos），也不能将直径阶段的线性复杂度扩张为完整半平面求交和最小覆盖圆程序的复杂度。印刷页码未核实，省略优于猜测。

### [4] 最小覆盖圆：建议必用

**WELZL E. Smallest enclosing disks (balls and ellipsoids)[C]//MAURER H, ed. New Results and New Trends in Computer Science. Lecture Notes in Computer Science, vol. 555. Berlin, Heidelberg: Springer, 1991: 359–370. DOI: 10.1007/BFb0038202.**

- 主源：[作者全文](https://people.inf.ethz.ch/emo/PublFiles/SmallEnclDisk_LNCS555_91.pdf)；[作者出版目录](https://people.inf.ethz.ch/emo/MiscellaneousPubl.html)；[Springer题录](https://doi.org/10.1007/BFb0038202)。已核实年份为1991；出版网页“First Online 2005”是上网时间，不改为2005年论文。
- 支持最小覆盖圆这一独立几何任务、由边界少量支撑点决定的性质，以及随机化增量法的背景。
- 文内落点：第一问最小覆盖圆的构造；第三四问光学20米充分条件。
- 可写：“覆盖可行区域所需的圆采用最小覆盖圆表述\cite{welzl1991}，其半径与区域直径分别计算。”
- 边界：若仓库实现采用枚举二/三支撑点而非Welzl随机算法，不要把本实现称作Welzl算法或给出其期望线性复杂度；20米阈值来自题设。

### [5] 集合估计用于路径规划：可用于总述，非必需

**CECCARELLI N, DI MARCO M, GARULLI A, et al. Path planning with uncertainty: A set membership approach[J]. International Journal of Adaptive Control and Signal Processing, 2011, 25(3): 273–287. DOI: 10.1002/acs.1217.**

- 主源：[作者研究组题录](https://www3.diism.unisi.it/~control/MAS/publication/cdggv-11/)；[21页作者稿](https://www3.diism.unisi.it/~control/MAS/papers/ACSP10.pdf)；[Wiley题录](https://onlinelibrary.wiley.com/doi/abs/10.1002/acs.1217)。完整作者另有 Antonio Giannitrapani、Antonio Vicino；线上首发2010-12-03，卷期年份2011。
- 精确内容：作者稿第4页§2式(3)—(4)集合定位；第7—9页§3以沿途平均可行集体积规划，并考虑有限可见范围。
- 文内落点：模型建立总述“用相容集合表达未知状态，并通过新增观测收缩集合”。
- 边界：其完整最坏噪声min–max被认为计算困难，实际用零噪声预测；不能说其已给出“最坏读数直径最小”算法。本文引用[1]作为直径准则直接依据更准确。

### [6] Voronoi几何基础：仅在第四问证书说明引用

**DE BERG M, CHEONG O, VAN KREVELD M, OVERMARS M. Computational Geometry: Algorithms and Applications[M]. 3rd ed. Berlin, Heidelberg: Springer, 2008. DOI: 10.1007/978-3-540-77974-2.**

- 主源：[Springer第三版题录与目录](https://link.springer.com/book/10.1007/978-3-540-77974-2)；[第7章Voronoi Diagrams，147–171页](https://link.springer.com/chapter/10.1007/978-3-540-77974-2_7)。书作者全名在章节题录中保留了 de/van 前缀；总页题录有截短，著录采用完整名。
- 文内落点：第四问“按最近检测点的Voronoi单元分解目标域”这一个标准定义处。本文有限圆缺极值证书的具体充要条件仍需本题给出证明。
- 边界：本轮核对出版社章节摘要、目录、版次与出版信息，未精读整本书；不应挂上未核对的书中定理编号，也不能把23点定向覆盖结论归于这本书。

### [7] 访问顺序局部改进的历史来源：可用但不要夸大适用范围

**CROES G A. A method for solving traveling-salesman problems[J]. Operations Research, 1958, 6(6): 791–812. DOI: 10.1287/opre.6.6.791.**

- 主源：[INFORMS期刊页](https://pubsonline.informs.org/doi/10.1287/opre.6.6.791)。本轮核实题录和原始摘要；页内卷期总页范围“791–908”不是该文页码，著录使用其Cite as给出的791–812。
- 文内落点：第四问从构造路线开始作局部边交换的背景；可写“参考旅行商问题的局部改进思想\cite{croes1958}，对候选访问序列实施2-opt交换，并补充短段搬移与频道成本修正。”
- 边界：本轮未逐页核对该文算法正文；不写具体定理/精确改进比例，不把本题开放路径、频道切换代价或Or-opt实现归给此文，不声称有限次数交换可得全局最优。若希望每项都基于全文算法细节，此条可不引用，保留前六项即可。

### [8] Jung 定理的原始文献：用于 `\cite{jung}`

**JUNG H. Ueber die kleinste Kugel, die eine räumliche Figur einschliesst[J]. Journal für die reine und angewandte Mathematik, 1901, 123: 241–257. DOI: 10.1515/crll.1901.123.241.**

- 主源：[De Gruyter Brill 原刊文章页](https://www.degruyterbrill.com/document/doi/10.1515/crll.1901.123.241/html)；[原刊对应卷目录](https://www.degruyterbrill.com/journal/key/crll/1901/123/html?lang=en)；[EuDML数字数学图书馆原刊记录](https://eudml.org/doc/149122)。三处核对作者 Heinrich Jung、原题名、1901年、241–257页；EuDML标明卷123。
- 著录细节：保留原文旧拼写 `Ueber`、`einschliesst`；现代化为 `Über`、`einschließt` 并非另一篇论文。出版社旧刊数据库将年1901标为volume、原卷123标为issue；按EuDML与原刊学术著录采用“1901, 123: 241–257”，不另捏造期号。网页的2009-12-09是数字上线日期，其“Erschienen im Druck”给1901-01-01。
- 用途：为Jung直径—最小覆盖球半径不等式提供原始出处。本文平面结论为 $R_*\le D/\sqrt3$，下界 $D/2\le R_*$ 可由三角不等式直接证明；等边三角形达到上界。正文应同时给简短平面证明，而不要只凭书目引用跳过它。
- 本輪核验边界：已查原刊元数据与原刊目录，未逐页读完1901年德文扫描本，故不指定原文定理号。原文仍是此经典定理的可靠原始出处；不把原始证明编号或现代符号表达伪装成原文逐字内容。

## 3. 建议的LaTeX著录

下列顺序可按正文首次引用重排，不要保留未实际引用条目。若使用 `\url`，先确保模板载入 `url` 或 `hyperref`；正文短引用采用 `\cite{...}`。

```latex
\begin{thebibliography}{99}
\bibitem{tokekar2013}
TOKEKAR P, ISLER V. Sensor placement and selection for bearing sensors with bounded uncertainty[C]//2013 IEEE International Conference on Robotics and Automation. IEEE, 2013: 2515--2520. DOI: 10.1109/ICRA.2013.6630920.
\bibitem{gholami2015}
GHOLAMI M R, GEZICI S, WYMEERSCH H, et al. Characterizing the worst-case position error in bearing-only target localization[C]//Workshop on Positioning, Navigation and Communication. 2015.
\bibitem{toussaint1983}
TOUSSAINT G T. Solving geometric problems with the rotating calipers[C]//Proceedings of IEEE MELECON '83. Athens, Greece, 1983.
\bibitem{welzl1991}
WELZL E. Smallest enclosing disks (balls and ellipsoids)[C]//MAURER H, ed. New Results and New Trends in Computer Science. Lecture Notes in Computer Science, vol. 555. Berlin, Heidelberg: Springer, 1991: 359--370. DOI: 10.1007/BFb0038202.
\bibitem{ceccarelli2011}
CECCARELLI N, DI MARCO M, GARULLI A, et al. Path planning with uncertainty: A set membership approach[J]. International Journal of Adaptive Control and Signal Processing, 2011, 25(3): 273--287. DOI: 10.1002/acs.1217.
\bibitem{deberg2008}
DE BERG M, CHEONG O, VAN KREVELD M, OVERMARS M. Computational Geometry: Algorithms and Applications[M]. 3rd ed. Berlin, Heidelberg: Springer, 2008. DOI: 10.1007/978-3-540-77974-2.
\bibitem{croes1958}
CROES G A. A method for solving traveling-salesman problems[J]. Operations Research, 1958, 6(6): 791--812. DOI: 10.1287/opre.6.6.791.
\bibitem{jung}
JUNG H. Ueber die kleinste Kugel, die eine r\"aumliche Figur einschliesst[J]. Journal f\"ur die reine und angewandte Mathematik, 1901, 123: 241--257. DOI: 10.1515/crll.1901.123.241.
\end{thebibliography}
```

不建议为了“有中文文献”抄入仓库早期候选清单中未读全文或与当前算法关系不明的论文。上述来源分别支撑方法的确切局部论点；本题参数、覆盖点布局、实验统计和完成证明必须以题设及实际程序结果为依据。

## 4. 完整程序附录的范围：原文与判断分开

官方第五条的关键原文短摘为：**“建模所用到的全部完整、可运行的源程序代码”**。见[全国组委会2026论文格式原文，第五条](https://www.mcm.edu.cn/html_cn/node/4cd596519c9eb9fbd866398f6df0caa3.html)或[官方PDF第1页](https://www.mcm.edu.cn/upload_cn/node/775/cQMeL0YY905244c8bd4b9af832f1699446d8385e.pdf)。这一摘录只引用必要短语。

官方第十一条还将支撑材料范围设为支撑模型、结果、结论的全部必要材料；明确包括全部可运行源程序、自主查得并使用的数据（赛题原始数据除外）、篇幅较大的中间结果图表，并要求清单进论文附录。北京PPT第4—5页重申同一要求，没有新增“核心代码可代替全部代码”的条款，也未把测试、样本生成、作图分别列为可免或必列类别。

**明确规定**：论文附录和支撑材料两处均应提供建模用的完整可运行程序，缺必要程序、无法运行或与文中结果不符均有问题。

**对本仓库的合理落实（是解释，不是新增官方条文）**：

1. 四问正式采用算法的完整调用链和依赖模块都入附录及支撑材料，不能只列四个 `solve.py`。
2. 正文直接报告的自建样本生成器、批量对比入口、本地仿真器、覆盖证书计算与相应验证程序属于复现该结论的必要程序，应一并收录。若正文强调测试通过数量，相应测试源程序也应可核对。
3. 本次用于计算或绘制正文图表的程序宜一并收录。若仅用现有结果文件排版图，至少保存具体作图脚本及输入结果，避免“同结论不可重建”；这属于对可复现性的保守落实，官方没有单独命令“所有绘图脚本必须入附录”。
4. 没有被本文采用、没有支撑正文结论的开发试验分支、失败草稿、临时调试脚本，无须为追求“仓库全量”全部打印。若正文报告某实验分支的结果，则相应完整程序转为相关支撑材料。

因此，不能笼统回答“只放核心程序就一定够”。更准确的边界是“本文实际使用并支撑模型、结果、结论的完整程序”，而不是“整个仓库所有历史脚本”。附录不限页，可通过列出程序清单、每模块明确标题和紧凑等宽排版解决篇幅问题，不应删去必要模块。
