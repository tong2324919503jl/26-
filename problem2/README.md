# 问题 2：统一几何模型与第二检测点选择

**只优化一个目标：固定首次观测后，让最不利合法第二读数留下的候选区域直径尽可能小。** A 和 B 是这个目标的两个上界，最终评分 C=min(A,B)。默认先算 A，扫描 B 的部分最大值达到 A 就停止；完整扫描与提前停止得到相同评分。

题面依据见 [原题](../materials/problem_b/statement.pdf) 问题 2 及附录 1、2。文献和可用于正文的文字见 [参考文献](references.md)；效果见 [策略比较](results/strategy_comparison.md) 与 [提前停止对照](results/scoring_benchmark.md)。全部示例均为自建离线实验，不是官方数据或模拟器成绩。

## 1. 已知信息与定位区域

第一检测点为 $S_1$，示向度为 $\theta$，误差上限 $\varepsilon=1^\circ$。令

$$u=(\cos\theta,\sin\theta),\qquad n=(-\sin\theta,\cos\theta).$$

用 $S_1$ 为原点、$u,n$ 为坐标轴的局部坐标描述第二点：$S_2=S_1+a u+b n$。第一读数是正常 `direction`，所以未知源 $G$ 满足

$$U_1=\{G:\|G\|\le1800,\quad 5<\|G-S_1\|\le1500,\quad |\operatorname{wrap}(\arg(G-S_1)-\theta)|\le\varepsilon\}.$$

距离不超过 5 米时是 `near`，无需第二次示向度，可直接光学精确定位并清除。误差是在同一检测位置固定的，重复检测不能通过平均读数消除误差。本模型不假设误差独立、均匀或高斯，也不为未知距离指定概率先验。

若第二点也返回正常示向度 $\theta_2$，精确候选源区域是

$$U_{12}=U_1\cap\{G:5<\|G-S_2\|\le1500,\quad |\operatorname{wrap}(\arg(G-S_2)-\theta_2)|\le\varepsilon\}.$$

两个正常读数对于未知共同接收半径的相容条件正是 $\max(1000,\|G-S_1\|,\|G-S_2\|)\le1500$。加入圆域与接收半径后的 $U_{12}$ 带圆弧边界，并不一定是问题 1 中的纯示向度交会多边形。

令 $\Psi(q)$ 为与首次观测和全部题设相容的第二正常读数，$U(q,\psi)=U_{12}$ 为相应候选区域，定义唯一目标

$$
\boxed{J(q)=\sup_{\psi\in\Psi(q)}\operatorname{diam}U(q,\psi),\qquad
\min_{q\in\mathcal F}J(q).}
$$

$\mathcal F$ 是下面的安全候选域，默认还排除可能产生 near 的点，以统一比较第二次正常测向分支。这个指标衡量最坏位置歧义，不是平均误差或对真值算出的实际点估计误差。

**直接文献依据。** Tokekar 与 Isler（ICRA 2013）§III-B 式 (1) 使用合法目标位置和读数下的最坏扇区交集直径评价布置。本题固定已经获得的首次观测，再加入未知接收半径的收信约束，是对该准则的条件化改编；并不继承其静态多传感器布置近似保证。[作者原文，第 3 页](https://tokekar.com/pubs/tokekar2013asensor.pdf#page=3)

直径与第一问一致，还能避免“面积很小但区域很细长”的歧义。若改为最小化最坏点估计半径，则应另定义最小覆盖圆准则。七篇文献的公式位置、适用范围、完整书目及指标区别详见 [references.md](references.md)。

补充依据形成以下论证链：Jaulin–Walter（1993）说明从误差界构造相容集合及以外包界定单调集合特征；Bertsimas等（2011）解释对全部相容情形保证可行；Tokekar–Isler（2013）直接支持最坏直径指标；Mavrotas（2009）支持精度优先的字典序及近优阈值内选短路程的约束法。每篇对应的原文位置和本题推导边界见 [评分到筛选的解释](references.md#4-从文献到当前筛选策略每一步解决什么问题)。

## 2. 保证收信的连续候选区域

设源的有效接收半径为 $R\in[1000,1500]$。第一点已接收到正常示向度，意味着 $R\ge r=\|G-S_1\|$。对该候选源，要对所有相容的 $R$ 保证第二点收信，只需且必须有

$$\|S_2-G\|\le\max(1000,r).$$

如果仅要求第二点与所有候选源的距离不超过 1000 米，会浪费“第一点已经收信”的信息；远源的 $R$ 已经至少等于第一距离。

暂时忽略全局 1800 米目标圆，用完整环扇形 $5<r\le1500,\ |\phi|\le\varepsilon$ 作保守先验。令 $u_\pm=(\cos\varepsilon,\pm\sin\varepsilon)$，四个局部圆心为

$$c_{5,\pm}=5u_\pm,\qquad c_{1000,\pm}=1000u_\pm.$$

给出连续安全候选区域

$$\boxed{\mathcal C_{\rm safe}=\bigcap_{d\in\{5,1000\},\ s\in\{-,+\}}\{(a,b):\|(a,b)-c_{d,s}\|\le1000\}.}$$

所有点都保证对任意相容全向源有信号。第二点若距源不超过 5 米，会返回 `near`，仍是有利结果。机器狗可以离开 1800 米目标圆；该圆只约束源的位置。

队友方案把首距放松到 $r\ge0$，得到三个圆盘（包括 $\|v\|\le1000$）的安全子域；这里保留 $r>5$ 给出的四圆盘，允许部分移动距离略超过 1000 米。两者都有收信证明，四圆盘较少保守。令移动极坐标为 $v=\rho(\cos\beta,\sin\beta)$、$\alpha=|\beta|+\varepsilon<90^\circ$，给定移动预算 $L$ 时的精确径向上限为

$$\rho_{\max}(\beta)=\min\left\{L,\ 2000\cos\alpha,\ 5\cos\alpha+\sqrt{1000^2-25\sin^2\alpha}\right\}.$$

前两类圆盘的二次不等式分别给出上述后两项。融合搜索在每个访问的移动方位上都加入这个边界点，避免普通距离网格漏掉约 0—5 米宽的新增安全范围。

**证明。** 写 $v=(a,b)$。两个 $d=1000$ 圆盘约束给出 $v\cdot u_\pm\ge\|v\|^2/2000\ge0$。所以在整个 $[-\varepsilon,\varepsilon]$ 上，$v\cdot u_\phi$ 的最小值在两个角端点；不能对任意未经约束的 $v$ 直接假定只查端点即可。对 $5\le r\le1000$，$\|v-r u_\phi\|^2-1000^2$ 关于 $r$ 是凸函数，其最大值在 $r=5$ 或 $r=1000$；对 $1000\le r\le1500$，约束化为 $\|v\|^2-2r v\cdot u_\phi\le0$，由内积非负，最严格处为 $r=1000$。于是四个圆盘充分且对完整环扇形也必要。首距的开边界 $r>5$ 用闭包端点 $r=5$ 取极限，不改变保证条件。重新加入全局目标圆后，这仍是充分保证区域，但不一定是最大的安全区域。

**为什么不能直接横着走？** 设 $S_1=(0,0)$、首示向度 $0^\circ$，真实源 $G=(1000,0)$、$R=1000$。任何纯横向移动 $S_2=(0,b),b\ne0$ 都有第二距离 $\sqrt{1000^2+b^2}>R$，因此失去信号。四圆盘交集在 $a=0$ 上也只有原点。

默认正常测向候选域为

$$
\mathcal F=\mathcal C_{\rm safe}\cap
\{\|q\|\le L,\ |b|\cos\varepsilon-a\sin\varepsilon>5\}.
$$

最后一个条件保证第二点距首扇区所有可能源超过 5 米。这是为比较第二正常读数采用的保守限制，并不表示 near 不好。四圆盘已经蕴含 $\|q\|\le1005$，故默认 $L=1100$ 米不会额外限制候选域。

## 3. 同一模型的解析上界 A

记本节的 $D_{\rm bound}$ 为 $A(q)$。它放松目标圆等约束，覆盖完整连续环扇形和任意符合 $\pm1^\circ$ 的第二读数，**不是采样最坏值，也不是小误差线性近似**。它比较保守，适合需要保证时的初始策略。

对于安全点 $v=(a,b)$，第一次环扇形被矩形

$$x\in[5\cos\varepsilon,1500],\qquad y\in[-1500\sin\varepsilon,1500\sin\varepsilon]$$

包含。定义

$$h=|b|-1500\sin\varepsilon,\quad k=\max(|a-5\cos\varepsilon|,|a-1500|),\quad \beta_0=\arctan2(h,k)-\varepsilon.$$

当 $h>0$ 且 $\beta_0>0$ 时，任意可能源到第二点的真实方向与第一条示向直线的锐角至少为 $\arctan2(h,k)$；第二次读数再偏差至多 $\varepsilon$，所以两条测量中心直线的锐角至少为 $\beta_0$。

同理由角端点和径向端点取极值，第二距离的统一上界为

$$r_{2,\max}=\max_{r\in\{5,1500\},s\in\{-,+\}}\|v-r u_s\|.$$

候选源到两条示向中心直线的垂距分别不超过 $w_1=1500\sin\varepsilon$、$w_2=r_{2,\max}\sin\varepsilon$。相交条带形成平行四边形：任意两个候选点之差在两个法向上的投影分别不超过 $2w_1,2w_2$。当夹角锐角为 $\beta$ 时，其直径为 $2\sqrt{w_1^2+w_2^2+2w_1w_2\cos\beta}/\sin\beta$，在 $0<\beta\le\pi/2$ 上随 $\beta$ 增大而减小。故

$$\boxed{\operatorname{diam}(U_{12})\le D_{\rm bound}(a,b)=\frac{2\sqrt{w_1^2+w_2^2+2w_1w_2\cos\beta_0}}{\sin\beta_0}.}$$

若角度下界不为正，程序将 A 设为无穷；这仅表示本保守公式不能保证非退化交会，不表示该点在实际场景下一定无法定位。

A 由有限个代数和三角运算给出，不扫描第二读数。A 无穷时仍继续几何扫描，可能得到有限的 B。四端点距离公式只在安全域成立；不安全比较点不能套用这项收紧。

## 4. 共用几何构造与扫描上界 B

评分与实际第二读数后的区域展示调用同一套构造：

1. 首扇区与目标圆、首接收距离圆求交，加入有效约束 $x\ge5\cos\varepsilon$、$|y|\le1500\sin\varepsilon$，得到首验外包 $\overline U_1$。
2. 每个候选点只裁入一次第二距离上界圆 $\|x-q\|\le R_2$，得到与第二读数无关的区域 $Q(q)$。安全点用 $R_2=\min(1500,r_{2,\max})$；不安全比较点只使用正常读数给出的 $R_2=1500$。
3. 每个第二读数裁入第二扇区、有效前向投影下界和第二条带。实际读数的约束为
   $u_\psi\cdot(x-q)\ge5\cos\varepsilon$、
   $|n_\psi\cdot(x-q)|\le R_2\sin\varepsilon$。

圆用 $M$ 个外切半平面近似，始终向外放松；两次 5 米排除圆用有效投影下界放松，以保持凸多边形。因此精确区域包含于实际读数外包 $P(q,\psi)$。默认 $M=360$，半径 $R$ 的圆外包径向膨胀最多为 $R(\sec(\pi/M)-1)$，对1800米圆约0.06854米；这不是所有交会顶点位置误差的统一界。

读数网格采用 $N=\lceil360/h_{\rm input}\rceil$、$h=360^\circ/N$。任意第二读数与最近格中心 $\psi_k$ 的环形角差不超过 $\delta=h/2$。**需要同步增宽所有随读数转动的约束，不能只增宽扇区：**

$$
\begin{aligned}
&\text{扇区半角：}\quad \varepsilon+\delta,\\
&\text{前向投影下界：}\quad 5\cos(\varepsilon+\delta),\\
&\text{条带半宽：}\quad R_2\sin\varepsilon+2R_{\rm out}\sin(\delta/2),\\
&R_{\rm out}=\max_{v\in\operatorname{vertices}Q(q)}\|v-q\|.
\end{aligned}
$$

三角函数按一致的弧度制计算。条带增量来自
$\|n_{\psi_k}-n_\psi\|\le2\sin(\delta/2)$；使用 $R_{\rm out}$，是为了同时覆盖外切圆带来的少量半径放松。

近区投影也覆盖实际外包：设点相对原读数角为 $t\in[-\varepsilon,\varepsilon]$，且 $r\cos t\ge5\cos\varepsilon$。读数转动 $|\Delta|\le\delta$ 后，新投影至少为
$5\cos\varepsilon(\cos|\Delta|-\tan\varepsilon\sin|\Delta|)
=5\cos(\varepsilon+|\Delta|)\ge5\cos(\varepsilon+\delta)$。
这个证明不要求外包中每个点都满足 $r>5$。

记同步增宽后的单元外包为 $P_k(q)$，则

$$
U(q,\psi)\subseteq P(q,\psi)\subseteq P_k(q),\qquad
\boxed{J(q)\le B(q)=\max_k\operatorname{diam}P_k(q).}
$$

默认最终 $h=0.1^\circ$，扇区半角增宽至 $1.05^\circ$；实际观测仍用原始 $1^\circ$。不相容读数单元也可能有非空外包，使 B 偏大，属于上界放松。有限个未经增宽的读数样本最大值不能充作连续最坏上界。

A 和 B 不需要分立：它们共用首验、距离信息和条带约束。A 用解析放松直接给保证，B 用上述几何细化计算；两者不必逐点具有固定大小关系。A 约束真实后验，但不能断言增宽后的每个评分单元也都满足 A。

## 5. 最终评分与正确的提前停止

因为 $J(q)\le A(q)$ 且 $J(q)\le B(q)$，所以

$$\boxed{J(q)\le C(q)=\min(A(q),B(q)).}$$

取 min 本身只收紧保证，不构成加速，也不会破坏 $C\ge J$ 的保证。加速来自扫描的单调性：第 $t$ 格后的部分最大值 $b_t\le B$，一旦 $b_t\ge A$，便已确定 $C=A$。

~~~text
A = analytic_bound(q)
partial_max = 0
for cell in angle_cells:
    partial_max = max(partial_max, diameter(cell_region(q)))
    if partial_max >= A:
        return A
return min(A, partial_max)
~~~

程序不放宽停止阈值，不因“接近 A”提前结束。若 A 无穷，或完整 B 小于 A，仍需全部扫描。不能用“A 大于当前最好评分”淘汰候选，因为 A 是上界，而非该候选评分的下界。

默认 early_stop=True；输入 JSON 可设 early_stop=false，或在 evaluate / choose_second_refined 调用时传 early_stop=False。输出含义为：

| 字段 | 含义 |
| --- | --- |
| diameter_upper_bound_m / capped_diameter_upper_bound_m | 已确定的 C，与完整扫描相同 |
| geometric_diameter_upper_bound_m | 完整 B；提前停止时为 null |
| geometric_max_lower_bound_m | 已扫最大值，是完整 B 的下界，不能当成 J 的上界 |
| scanned_cells / total_cells / early_stopped | 实际工作量和是否提前结束 |
| worst_cell_* | 完整扫描的最坏单元；提前停止时为 null |
| observed_max_cell_* | 已访问单元中的最大值位置，非全局最坏证明 |
| score_exact_for_capped_objective | C 已确定；不代表真实 J 被精确求出 |
| scan_statistics | 各层、最终复核及全流程的累计扫描统计 |

默认细网格多数 B 小于 A，不能保证明显提速；实际节省和等价性见 [提前停止实验](results/scoring_benchmark.md)。完整 B 的策略比较显式关闭提前停止；不会把部分最大值误报成完整上界。

## 6. 有限搜索与移动距离的角色

| 阶段 | 移动距离步长 | 移动方位步长 | 读数评分步长 |
| --- | ---: | ---: | ---: |
| 全域粗搜索 | 100 米 | 5° | 1° |
| 局部细化及镜像分支 | 20 米 | 1° | 0.5° |
| 再细化 | 5 米 | 0.25° | 0.25° |
| 全部已访问候选统一复核 | 不增候选 | 不增候选 | 0.1° |

每层保留已有候选，并加入安全径向边界、原解析推荐点和若干直观点。最终全部候选按相同精度复核。这只保证已访问有限集合中的评分最小，未证明连续全局最优。原解析接口 choose_second 和配置 selection_mode="analytic" 保留，供独立快速运行和基线对照。

**默认 selected 优先最小化 C；移动距离只在评分相同（按 $10^{-7}$ 米数值舍入判平局）时决定顺序。** 不将路程乘任意权重加进定位评分。报告 $\|q\|/5+5$ 秒，是依据题设速度和第二次检测时间说明执行代价，不包括首次检测、后续定位、清除或总任务时间。

可选 fastest_near_best 是已访问集合中满足 $C(q)\le(1+\eta)C(q_*)$ 的最短移动点。默认 $\eta=10\%$ 是可调整的方案容差，不是题目要求或文献常数。pareto_frontier 给出同一有限集合中的时间/直径非劣选项，它们不替换默认精度优先推荐。

默认优先顺序对应字典序，可选备选对应$\epsilon$-约束思想；方法依据见[7]。这里的$\epsilon$表示目标阈值，不能与测向误差$\varepsilon$混同。实现以数值舍入判平局，只在有限访问集合和给定精度下筛选；较小的C表示保证更紧，不必推出真实J或实际误差也更小。

连续近优候选域为
$\mathcal C_{\rm good}=\{q\in\mathcal F:C(q)\le(1+\eta)C(q_*)\}$；
CSV、SVG只展示已访问代表点，不是连续域的精确边界。

同口径比较及预算、精度、空间细化结果见 [策略比较](results/strategy_comparison.md)。应区分：加入约束使同一点的界更紧、换点使同口径评分更好、提前停止减少计算。不同上界之差不能直接说成真实误差改善。

20米光学定位保证另检查最小覆盖圆半径。只有直径上界时，$C/\sqrt3\le20$ 是平面上的充分条件；$C/2$ 并非一般覆盖半径保证。默认原点例仍不能保证两次测向后一次光学清除。

## 7. 运行、结果与验证

在仓库根目录运行，Python 3.10+，核心实现无第三方依赖：

~~~text
python problem2/solve.py
python problem2/compare_strategies.py
python problem2/benchmark_scoring.py
python -m unittest discover -s problem2/tests -v
python scripts/verify_project.py
~~~

所有默认和自选相对输入/输出路径均相对于脚本所在目录；绝对路径原样使用。两个比较脚本的 --quick 跳过扩展实验，默认写入独立 results/quick，避免覆盖完整报告。

| 文件 | 用途 |
| --- | --- |
| [solve.py](solve.py) | 统一几何、四圆盘、评分、提前停止与实际后验 |
| [compare_strategies.py](compare_strategies.py) | 同模型同精度重评基线，需要完整 B 时关闭提前停止 |
| [benchmark_scoring.py](benchmark_scoring.py) | 仅切换提前停止，对照评分、排序、选点、扫描量和耗时 |
| [references.md](references.md) | 七篇文献核查、筛选逻辑对应及可用于正文的说明 |
| [默认结果](results/selection.json) / [边界结果](results/boundary/selection.json) | 推荐点、统计与自建第二读数后的区域 |
| [候选表](results/second_point_candidates.csv) / [示意图](results/candidate_region.svg) | 近优已访问点 |
| [验证记录](results/validation.md) | 当前结果和证据边界 |
| [四问统一验证](../validation/report.md) | 数学测试、跨目录运行与原材料完整性 |

源真值、真实接收半径只用于选点后的自建验证，不被选点函数读取。默认实际后验与评分共用360边圆外包；独立 posterior_outer_polygon 默认720边，做包含对照时应传入相同精度。

第二问27项测试覆盖安全域端点、失收反例、旋转与目标圆边界、半格增宽、外切圆与近区投影、提前停止触发/不触发/无穷A、恰好相等及浮点临界值、排序和选点等价性。基准另比较完整默认搜索路径。数学保证来自集合包含和解析推导；有限测试及双精度浮点裁剪不是严格区间算术认证。首验相容性对首距使用闭包，仅在 $r=5$ 相切的退化输入可能被保守接受；实际正常读数不含该情形。
