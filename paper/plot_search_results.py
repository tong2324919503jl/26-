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
    """P4 坐标直接读取当前冻结的解析覆盖证书。"""
    certificate = read_result("problem4/results/coverage_certificate_v2.json")
    if not certificate["certified"] or certificate["point_count"] != 23:
        raise ValueError("第四问论文图要求通过认证的23点冻结布局")
    a = (read_result("problem3/results/benchmark_development.json")["config"] or {}).get(
        "ring_radius", 1150.0
    )
    points3 = [(0, 0)] + [
        (a * math.cos(k * math.pi / 3), a * math.sin(k * math.pi / 3))
        for k in range(6)
    ]
    points4 = certificate["points"]
    fig, axes = plt.subplots(1, 2, figsize=(6.4, 3.6))
    for ax in axes:
        ax.add_patch(Circle((0, 0), 1800, fill=False, color="#222222", lw=1.1, zorder=3))
        ax.axhline(0, color="#dddddd", lw=0.5, zorder=0)
        ax.axvline(0, color="#dddddd", lw=0.5, zorder=0)
        ax.set(xlim=(-2400, 2400), ylim=(-2400, 2400), xlabel="$x$ / 米", ylabel="$y$ / 米")
        ax.set_xticks([-2000, -1000, 0, 1000, 2000])
        ax.set_yticks([-2000, -1000, 0, 1000, 2000])
        ax.set_aspect("equal")
    for point in points3:
        axes[0].add_patch(Circle(point, 1000, facecolor="#2670a6", edgecolor="#2670a6", alpha=0.10, lw=0.65))
    axes[0].scatter(*zip(*points3), s=16, c="#125986", zorder=4)
    axes[0].set_title("(a) 第三问：七点全向覆盖", pad=9)
    axes[1].scatter(*zip(*points4[1:13]), marker="^", s=20, c="#b45527", zorder=4, label="外环点")
    axes[1].scatter(*zip(*([points4[0]] + points4[13:])), s=16, c="#125986", zorder=4, label="原点及内点")
    axes[1].set_title("(b) 第四问：23点认证布局", pad=9)
    handles, labels = axes[1].get_legend_handles_labels()
    fig.legend(handles, labels, loc="center", bbox_to_anchor=(0.76, 0.10), ncol=2, frameon=False, handletextpad=0.3, columnspacing=1.1)
    fig.text(0.285, 0.10, "浅色圆盘：保证接收半径1000米", ha="center", va="center", fontsize=7)
    fig.text(0.5, 0.03, "黑色圆为1800米目标边界；第四问任意发射朝向的覆盖由正文有限极值证书保证。", ha="center", fontsize=7)
    fig.subplots_adjust(left=0.10, right=0.98, bottom=0.24, top=0.91, wspace=0.32)
    fig.savefig(DEST / "search_coverage.pdf", metadata={"Title": "第三、四问的冻结覆盖布局", "Subject": "来源：P3生产配置；P4 coverage_certificate_v2.json"})
    plt.close(fig)


def label_bars(ax, bars, percentage=False):
    for bar in bars:
        value = bar.get_height()
        text = f"{value:.1f}%" if percentage else f"{value:.1f}"
        ax.annotate(text, (bar.get_x() + bar.get_width() / 2, value), xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=7)


def comparison_figure():
    """各条形均来自现有冻结结果，不将不同样本集合合并评分。"""
    p3 = read_result("problem3/results/benchmark_development.json")["summary"]
    p4 = read_result("problem4/results/speed_comparison_v2.json")["paired"]
    fig, axes = plt.subplots(2, 2, figsize=(6.4, 4.85))
    names3 = ["先覆盖后清除", "本文策略", "直接光学"]
    strategy_keys = ["baseline", "adaptive", "optical"]
    colors3 = ["#8d959e", "#2670a6", "#cc8451"]
    for col, field in enumerate(["mean_average_clear_time_s", "threshold_pass_rate"]):
        values = [p3[key][field] * (100 if col else 1) for key in strategy_keys]
        bars = axes[0, col].bar(range(3), values, color=colors3, width=0.57, edgecolor="#333333", linewidth=0.4)
        for bar, hatch in zip(bars, ["//", "", ".."]):
            bar.set_hatch(hatch)
        label_bars(axes[0, col], bars, percentage=bool(col))
        axes[0, col].set_xticks(range(3), names3)
    axes[0, 0].set(title="(a) 第三问：同一开发集96例", ylabel="平均时间 / (秒/源)", ylim=(0, 720))
    axes[0, 1].set(title="(b) 第三问：300秒/源阈值", ylabel="全清且达到阈值 / %", ylim=(0, 100))
    keys4 = ["development_v2", "holdout_v2", "stress_v2"]
    labels4 = ["开发\n384例", "留出\n512例", "压力\n256例"]
    for col, pair in enumerate(
        [("old_seconds_per_source", "new_seconds_per_source"), ("old_threshold_pass_rate", "new_threshold_pass_rate")]
    ):
        for index, (field, color, offset, legend, hatch) in enumerate(
            [(pair[0], "#a3a8ad", -0.19, "旧版25点", "//"), (pair[1], "#2670a6", 0.19, "新版23点", "")]
        ):
            values = [p4[key][field] * (100 if col else 1) for key in keys4]
            bars = axes[1, col].bar([x + offset for x in range(3)], values, width=0.34, color=color, edgecolor="#333333", linewidth=0.4, label=legend, hatch=hatch)
            label_bars(axes[1, col], bars, percentage=bool(col))
        axes[1, col].set_xticks(range(3), labels4)
    axes[1, 0].set(title="(c) 第四问：集合内新旧配对", ylabel="平均时间 / (秒/源)", ylim=(0, 740))
    axes[1, 1].set(title="(d) 第四问：500秒/源阈值", ylabel="全清且达到阈值 / %", ylim=(0, 100))
    for ax in axes.flat:
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", linewidth=0.4, color="#dddddd", zorder=0)
        ax.set_axisbelow(True)
    handles, labels = axes[1, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, 0.055), ncol=2, frameon=False)
    fig.text(0.5, 0.023, "全部为自建样本；每例先计算总虚拟时间/清除数，再取均值。阈值为本地预设标准。", ha="center", fontsize=7)
    fig.subplots_adjust(left=0.10, right=0.98, top=0.93, bottom=0.18, hspace=0.63, wspace=0.31)
    fig.savefig(DEST / "search_comparison.pdf", metadata={"Title": "第三、四问本地冻结算法对照", "Subject": "P3同一96例开发集；P4 v2各集合内逐例配对"})
    plt.close(fig)


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    setup_style()
    coverage_figure()
    comparison_figure()
    print(f"已根据现有结果生成两张论文图：{DEST}")


if __name__ == "__main__":
    main()
