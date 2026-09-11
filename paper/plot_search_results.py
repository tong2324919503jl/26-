"""依据已保存的结果重建论文搜索图；不运行算法或连接测试平台。"""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Circle


PAPER = Path(__file__).resolve().parent
ROOT = PAPER.parent
DEST = PAPER / "figures"


def read_result(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def setup_style():
    for candidate in (
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    ):
        if candidate.exists():
            font_manager.fontManager.addfont(str(candidate))
            family = font_manager.FontProperties(fname=str(candidate)).get_name()
            break
    else:
        family = "DejaVu Sans"
    plt.rcParams.update(
        {
            "font.family": family,
            "font.size": 8,
            "axes.titlesize": 9,
            "axes.labelsize": 8,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "axes.linewidth": 0.6,
            "savefig.facecolor": "white",
        }
    )


def coverage_figure():
    """P4 uses the current production certificate; P3 shows both safe branches."""
    certificate=read_result("problem4/results/coverage_certificate_v4.json")
    if not certificate["certified"] or certificate["point_count"]!=22:
        raise ValueError("第四问论文图要求当前22点完整覆盖证书")
    layouts=[]
    for count,radius in ((6,1150.),(9,1700.)):
        layouts.append([(0.,0.)]+[(radius*math.cos(k*math.tau/count),radius*math.sin(k*math.tau/count)) for k in range(count)])
    layouts.append(certificate["points"])
    fig,axes=plt.subplots(1,3,figsize=(6.4,2.85))
    titles=["(a) 第三问：原点收信，7点", "(b) 第三问：原点无信号，10点", "(c) 第四问：22点认证布局"]
    for index,(ax,points,title) in enumerate(zip(axes,layouts,titles)):
        ax.add_patch(Circle((0,0),1800,fill=False,color="#222222",lw=.9,zorder=3))
        ax.axhline(0,color="#dddddd",lw=.4,zorder=0);ax.axvline(0,color="#dddddd",lw=.4,zorder=0)
        ax.set(xlim=(-2300,2300),ylim=(-2300,2300),xlabel="$x$ / 米",ylabel="$y$ / 米")
        ax.set_xticks([-2000,0,2000]);ax.set_yticks([-2000,0,2000]);ax.set_aspect("equal")
        if index<2:
            for point in points:ax.add_patch(Circle(point,1000,facecolor="#2670a6",edgecolor="#2670a6",alpha=.09,lw=.5))
            ax.scatter(*zip(*points),s=10,c="#125986",zorder=4)
        else:
            inner=[p for p in points if math.hypot(*p)<1500.];outer=[p for p in points if math.hypot(*p)>=1500.]
            ax.scatter(*zip(*outer),marker="^",s=13,c="#b45527",zorder=4)
            ax.scatter(*zip(*inner),s=11,c="#125986",zorder=4)
        ax.set_title(title,fontsize=7.2,pad=7)
    fig.text(.5,.10,"第三问浅色圆盘半径1000米；图示相位不影响覆盖，实际相位按公共状态选择。",ha="center",fontsize=6.6)
    fig.text(.5,.035,"第四问蓝点为原点和内点、三角为外点；任意朝向覆盖由独立有限几何证书保证。",ha="center",fontsize=6.6)
    fig.subplots_adjust(left=.105,right=.985,bottom=.25,top=.91,wspace=.40)
    fig.savefig(DEST/"search_coverage.pdf",metadata={"Title":"第三四问当前冻结覆盖布局","Subject":"P3条件覆盖；P4 coverage_certificate_v4.json"})
    plt.close(fig)


def label_bars(ax, bars, percentage=False):
    for bar in bars:
        value = bar.get_height()
        text = f"{value:.1f}%" if percentage else f"{value:.1f}"
        ax.annotate(text, (bar.get_x() + bar.get_width() / 2, value), xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=7)


def comparison_figure():
    """Read the same-simulator, isolated-process final reports; never run a policy."""
    fig,axes=plt.subplots(2,2,figsize=(6.4,4.9))
    splits=("development_v3","holdout_v3","stress_v3")
    labels=["开发\n384例","留出\n512例","压力\n256例"]
    legends={"original":"原默认","previous":"上一轮最好","teammate":"队友方案","selected":"本文方案"}
    colors={"original":"#999fa5","previous":"#91b4c7","teammate":"#d09665","selected":"#17608d"}
    handles={}
    for row,problem in enumerate((3,4)):
        reports=[read_result(f"validation/speed_v4/p{problem}_{split}.json")["results"][str(problem)] for split in splits]
        keys={"original":f"problem{problem}.policy:SearchPolicy","teammate":"teammate","selected":f"problem{problem}.speed_policy:SearchPolicy"}
        extras=[k for k in reports[0] if k not in keys.values()]
        if extras:keys["previous"]=extras[0]
        order=[kind for kind in ("original","previous","teammate","selected") if kind in keys]
        width=.72/len(order)
        for column,field in enumerate(("mean_seconds_per_source","threshold_pass_rate")):
            ax=axes[row,column]
            for index,kind in enumerate(order):
                summaries=[report[keys[kind]]["summary"] for report in reports]
                if any(s["cases"]!=n for s,n in zip(summaries,(384,512,256))):raise ValueError("Incomplete final report")
                values=[s[field]*(100 if column else 1) for s in summaries]
                positions=[x+(index-(len(order)-1)/2)*width for x in range(3)]
                bars=ax.bar(positions,values,width=width*.9,color=colors[kind],edgecolor="#333333",linewidth=.35,label=legends[kind])
                handles[kind]=bars[0]
                if kind=="selected":label_bars(ax,bars,percentage=bool(column))
            ax.set_xticks(range(3),labels)
            ax.set_ylabel("全清且达到阈值 / %" if column else "平均时间 / (秒/源)")
            threshold=220 if problem==3 else 400
            ax.set_title(f"({chr(97+row*2+column)}) 第{['三','四'][row]}问："+(f"{threshold}秒/源阈值" if column else "同集合逐例配对"))
            if column:ax.set_ylim(0,100)
            else:ax.set_ylim(0,max(ax.get_ylim()[1],350 if problem==3 else 660))
            ax.spines[["top","right"]].set_visible(False);ax.grid(axis="y",linewidth=.4,color="#dddddd");ax.set_axisbelow(True)
    ordered=[kind for kind in ("original","previous","teammate","selected") if kind in handles]
    fig.legend([handles[kind] for kind in ordered],[legends[kind] for kind in ordered],loc="lower center",bbox_to_anchor=(.5,.054),ncol=4,frameon=False)
    fig.text(.5,.023,"自建样本，非官方成绩；每例先算总虚拟时间/清除数，再取均值；阈值为本地目标。",ha="center",fontsize=6.8)
    fig.subplots_adjust(left=.10,right=.985,top=.93,bottom=.18,hspace=.65,wspace=.32)
    fig.savefig(DEST/"search_comparison.pdf",metadata={"Title":"第三四问第四轮冻结算法比较","Subject":"validation/speed_v4；统一模拟器与独立进程"})
    plt.close(fig)


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    setup_style()
    coverage_figure()
    comparison_figure()
    print(f"已根据现有结果生成两张论文图：{DEST}")


if __name__ == "__main__":
    main()
