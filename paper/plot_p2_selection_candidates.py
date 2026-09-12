"""Evidence-backed selection/result figure candidates; does not alter the paper."""
from __future__ import annotations

import csv
import math

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from p2_candidate_style import (
    ROOT, BLUE, INK, GREY, GOLD, GREEN, LIGHT_BLUE, LIGHT_GREY,
    setup, save, axes_style, panel_label, read_json,
)

ORIGIN = 'problem2/results/selection.json'
BOUNDARY = 'problem2/results/boundary/selection.json'
COMPARE = 'problem2/results/strategy_comparison.json'
CSVS = ['problem2/results/second_point_candidates.csv',
        'problem2/results/boundary/second_point_candidates.csv']
PAPER_TEXT = 'paper/sections/p12.tex'
BASE_NOTES = ('全部数值来自自建离线算例；A、B、C为最坏相容读数下区域直径的上界，'
              '不是真实定位误差。只在已访问离散候选内选点，未证明连续全局最优。'
              '比较中的选点均满足四圆盘收信条件和正常测向的5米排除条件。')


def load_candidates(path):
    with (ROOT / path).open(encoding='utf-8-sig', newline='') as stream:
        return [{key: float(value) for key, value in row.items()}
                for row in csv.DictReader(stream)]


def safe_domain(ax, label=True):
    """Draw the four exact disk cross-sections, clipped by direction clearance."""
    a = np.linspace(0.0, 1005.0, 5001)
    eps = math.radians(1)
    upper = np.full_like(a, np.inf)
    for distance in (5.0, 1000.0):
        radicand = 1000.0 ** 2 - (a - distance * math.cos(eps)) ** 2
        candidate = np.sqrt(np.maximum(0.0, radicand)) - distance * math.sin(eps)
        candidate[radicand < 0.0] = -1.0
        upper = np.minimum(upper, candidate)
    lower = (5.0 + a * math.sin(eps)) / math.cos(eps)
    keep = upper > lower
    ax.fill_between(a, lower, upper, where=keep, color=LIGHT_GREY,
                    edgecolor=GREY, linewidth=.7,
                    label=r'安全候选域 $\mathcal{F}$' if label else None)
    ax.fill_between(a, -upper, -lower, where=keep, color=LIGHT_GREY,
                    edgecolor=GREY, linewidth=.7)
    ax.plot([0, 1070], [0, 0], color=GREY, ls='--', lw=.8)
    ax.scatter([0], [0], s=22, color=INK, zorder=6)
    ax.annotate('$S_1$', (0, 0), xytext=(-12, 7), textcoords='offset points')
    return {'four_disk_centres_local_m': [[d * math.cos(eps), s * d * math.sin(eps)]
                                         for d in (5.0, 1000.0) for s in (-1, 1)],
            'disk_radius_m': 1000.0, 'move_budget_m': 1100.0,
            'normal_direction_clearance_m': 5.0,
            'rendering': 'analytic disk cross-sections sampled for display only'}


def point(ax, row, marker, color, label=None, size=90):
    x, y = row['local_xy_m']
    ax.scatter([x], [y], s=size, marker=marker, color=color, edgecolor='white',
               linewidth=.65, label=label, zorder=8)


def figure14(selections, candidates):
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 6.9))
    fig.subplots_adjust(wspace=.27, bottom=.21, top=.95)
    extra = []
    for idx, (ax, result, rows) in enumerate(zip(axes, selections, candidates)):
        extra.append(safe_domain(ax))
        ax.scatter([r['local_a_m'] for r in rows], [r['local_b_m'] for r in rows],
                   s=10, facecolors=BLUE, edgecolors='none', alpha=.72,
                   label='已访问近优点', zorder=4)
        point(ax, result['baseline_analytic_selected'], 's', GOLD, '解析基线', 48)
        point(ax, result['selected'], '*', INK, r'推荐点 $q_*$', 120)
        point(ax, result['fastest_near_best'], 'D', GREEN, r'10%内最短点 $q_\eta$', 43)
        ax.annotate('$q_*$', result['selected']['local_xy_m'], xytext=(7, 9),
                    textcoords='offset points', color=INK)
        ax.annotate(r'$q_\eta$', result['fastest_near_best']['local_xy_m'],
                    xytext=(-26, -17), textcoords='offset points', color=GREEN)
        ax.set_xlim(-65, 1090)
        ax.set_ylim(-910, 910)
        ax.set_xticks([0, 250, 500, 750, 1000])
        ax.set_yticks([-800, -400, 0, 400, 800])
        axes_style(ax)
        ax.legend(loc='lower left', fontsize=8.2, handlelength=1.8)
        panel_label(ax, [r'(a) 首点 $S_1=(0,0)$',
                         r'(b) 首点 $S_1=(1500,0)$'][idx])
    save(fig, 'p2_14_visited_candidate_regions', '安全候选域与已访问近优代表点',
         '两种自建首验场景的安全候选域、已访问近优代表点和推荐点。采用局部坐标；'
         '四圆盘与正常测向条件定义灰色区域，蓝点为CSV中实际访问且满足10%阈值的代表点。',
         '评分组合与分层选点', [ORIGIN, BOUNDARY, *CSVS, PAPER_TEXT], BASE_NOTES +
         '灰色区域不施加源位置的1800米目标圆于第二检测点；蓝点不代表连续近优域的全部点。'
         '首次示向度均为0度；M=360，h=0.1度。',
         '适合替换现有问题二候选点图，展示相同安全域中随首验而改变的推荐点。',
         data={'scenes': [{'first_station_xy_m': r['first_station_xy_m'],
                          'visited_near_best_count': len(c), 'selected': r['selected'],
                          'fastest_near_best': r['fastest_near_best']}
                         for r, c in zip(selections, candidates)], 'domain': extra[0]})


def figure15(comparison):
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.9))
    fig.subplots_adjust(wspace=.3, bottom=.26, top=.89)
    raw = []
    for idx, (ax, scene) in enumerate(zip(axes, comparison['scenarios'])):
        rows = [next(row for row in scene['rows'] if row['key'] == key)
                for key in ('legacy_analytic', 'merged')]
        x = np.arange(2)
        a = [r['analytic_diameter_upper_bound_m'] for r in rows]
        b = [r['geometric_diameter_upper_bound_m'] for r in rows]
        c = [r['diameter_upper_bound_m'] for r in rows]
        ax.bar(x-.22, a, .22, color=LIGHT_GREY, edgecolor=GREY, linewidth=.8,
               label=r'解析上界 $A$')
        ax.bar(x, b, .22, color=BLUE, edgecolor=BLUE, linewidth=.8,
               label=r'几何上界 $B$')
        ax.bar(x+.22, c, .22, color='#d7e8e3', edgecolor=GREEN, linewidth=.8,
               label=r'组合评分 $C$')
        upper = 195 if idx == 0 else 1000
        for shift, values, color in [(-.22, a, GREY), (0, b, BLUE), (.22, c, GREEN)]:
            for xx, value in zip(x+shift, values):
                ax.text(xx, value + upper*.016, f'{value:.2f}', ha='center', va='bottom',
                        fontsize=7.5, color=color, rotation=90 if idx else 0)
        ax.set_xticks(x, ['解析基线点', '本文推荐点'])
        ax.set_ylim(0, upper)
        ax.set_xlim(-.58, 1.58)
        axes_style(ax, xlabel='', ylabel='直径上界（米）', equal=False)
        panel_label(ax, [r'(a) 首点 $S_1=(0,0)$',
                         r'(b) 首点 $S_1=(1500,0)$'][idx])
        raw.append({'scene': scene['name'], 'rows': rows})
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', ncol=3,
               bbox_to_anchor=(.5, 1.005), fontsize=9)
    save(fig, 'p2_15_same_point_score_comparison', '同一候选点的两类上界与组合评分',
         '在两种自建首验场景下，对解析基线点及本文推荐点分别计算A、B和C=min(A,B)。'
         '所有B均完整扫描，统一M=360、h=0.1度；两个面板分别采用线性纵轴。',
         '评分组合与分层选点', [COMPARE, PAPER_TEXT], BASE_NOTES +
         '同点的不同上界之差是保守程度差异；两点的C值之差是上界评分差异，均不表示真实误差改善。',
         '适合接在组合评分公式后，直观显示两种上界可以对同一候选点给出不同保证。', raw)


def figure16(comparison):
    specs = [(0, 'legacy_analytic', '原点 · 解析基线', GOLD),
             (0, 'merged', '原点 · 本文选点', BLUE),
             (0, 'merged_faster', '原点 · 10%内最短点', GREEN),
             (1, 'legacy_analytic', '边界 · 解析基线', GOLD),
             (1, 'merged', '边界 · 本文选点', BLUE)]
    rows = [next(r for r in comparison['scenarios'][scene]['rows'] if r['key'] == key)
            for scene, key, _, _ in specs]
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.4), sharey=True)
    fig.subplots_adjust(left=.19, right=.98, wspace=.11, bottom=.25, top=.96)
    ypos = np.arange(len(rows))
    colors = [r[3] for r in specs]
    for ax, field, xlabel, limits, letter in [
        (axes[0], 'diameter_upper_bound_m', r'组合评分 $C$（米）', (0, 147), '(a)'),
        (axes[1], 'move_and_detect_time_s', '移动加检测时间（秒）', (0, 247), '(b)')]:
        values = [row[field] for row in rows]
        ax.barh(ypos, values, .57, color=colors, alpha=.88, edgecolor='white', linewidth=.6)
        for y, value in zip(ypos, values):
            ax.text(value + limits[1]*.016, y, f'{value:.2f}', va='center', fontsize=9)
        ax.axhline(2.5, color=GREY, lw=.8, ls='--')
        ax.set_xlim(*limits)
        axes_style(ax, xlabel=xlabel, ylabel='', equal=False)
        ax.grid(axis='y', visible=False)
        panel_label(ax, letter + (' 最坏直径上界' if ax is axes[0] else '本次移动与检测'))
    axes[0].set_yticks(ypos, [r[2] for r in specs])
    axes[0].invert_yaxis()
    save(fig, 'p2_16_selection_score_and_time', '同口径选点结果与本次行动时间',
         '问题二正文比较表的图形化版本。左侧为统一模型、统一精度下的C；右侧仅计'
         '本次移动距离除以5米每秒，加5秒检测。原点和边界为两种自建首验场景。',
         '评分组合与分层选点', [COMPARE, PAPER_TEXT], BASE_NOTES +
         '本图不是整局定位时间或正式测试结果；10%为上界放宽偏好，不是实际误差增加比例。',
         '适合数值结果部分，正文表格与本图可择一使用。',
         data={'rows': [{'label': item[2], 'values': row} for item, row in zip(specs, rows)],
               'circle_sides': 360, 'angle_step_deg': .1})


def figure17(selections, candidates):
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.9))
    fig.subplots_adjust(wspace=.30, bottom=.27, top=.85)
    for idx, (ax, result, rows) in enumerate(zip(axes, selections, candidates)):
        times = [r['move_and_detect_time_s'] for r in rows]
        scores = [r['diameter_upper_bound_m'] for r in rows]
        ax.scatter(times, scores, s=15, facecolors=BLUE, edgecolors='none', alpha=.64,
                   label='已访问近优点')
        threshold = result['candidate_threshold_m']
        ax.axhline(threshold, color=GOLD, lw=1.3, ls='--',
                   label=r'$1.1C(q_*)$')
        selected, fastest = result['selected'], result['fastest_near_best']
        ax.scatter([selected['move_and_detect_time_s']], [selected['diameter_upper_bound_m']],
                   marker='*', s=125, facecolors=INK, edgecolors='white', lw=.65,
                   label=r'推荐点 $q_*$', zorder=5)
        ax.scatter([fastest['move_and_detect_time_s']], [fastest['diameter_upper_bound_m']],
                   marker='D', s=49, color=GREEN, edgecolors='white', lw=.65,
                   label=r'10%内最短点 $q_\eta$', zorder=5)
        ax.annotate('$q_*$', (selected['move_and_detect_time_s'], selected['diameter_upper_bound_m']),
                    xytext=(-26, -2), textcoords='offset points', ha='right')
        ax.annotate(r'$q_\eta$', (fastest['move_and_detect_time_s'], fastest['diameter_upper_bound_m']),
                    xytext=(6, -10) if idx == 0 else (-14, 12),
                    textcoords='offset points', color=GREEN)
        margin = (max(times)-min(times))*.07
        ax.set_xlim(min(times)-margin, max(times)+margin)
        low = selected['diameter_upper_bound_m']
        ax.set_ylim(low-(threshold-low)*.11, threshold+(threshold-low)*.19)
        axes_style(ax, xlabel='移动加检测时间（秒）', ylabel=r'组合评分 $C$（米）', equal=False)
        panel_label(ax, [r'(a) 首点 $S_1=(0,0)$',
                         r'(b) 首点 $S_1=(1500,0)$'][idx])
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', ncol=4,
               bbox_to_anchor=(.5, 1.005), fontsize=9)
    save(fig, 'p2_17_near_best_score_time', '已访问近优点的上界评分与行动时间',
         '仅展示两份候选CSV实际保存的近优代表点。虚线表示默认10%上界阈值；星形点'
         '按评分优先选取，菱形点在满足阈值的已访问集合中最短。对称点可能在图上重叠。',
         '评分组合与分层选点', [ORIGIN, BOUNDARY, *CSVS, PAPER_TEXT], BASE_NOTES +
         '不将离散点连接成连续Pareto前沿；图中未显示阈值之外的所有访问点。'
         '同一场景下缩短路程等价于减少本次移动加检测时间。',
         '适合解释10%容差的含义，比单列最短点坐标更直观。',
         data={'scenes': [{'first_station_xy_m': r['first_station_xy_m'],
                          'near_best_count': len(c), 'threshold_m': r['candidate_threshold_m'],
                          'candidate_csv': source} for r, c, source in zip(selections, candidates, CSVS)]})


def figure18(selections):
    fig, axes = plt.subplots(1, 2, figsize=(9.7, 5.5))
    fig.subplots_adjust(wspace=.34, bottom=.25, top=.9)
    marker_colors = [GREY, GOLD, GREEN]
    all_paths = []
    for idx, (ax, result) in enumerate(zip(axes, selections)):
        path = np.array([h['selected_local_xy_m'] for h in result['search_history']] +
                        [result['selected']['local_xy_m']])
        for segment, (before, after) in enumerate(zip(path[:-1], path[1:])):
            ax.annotate('', xy=after, xytext=before,
                        arrowprops={'arrowstyle': '-|>', 'lw': 1.0,
                                    'color': [GOLD, GREEN, BLUE][segment],
                                    'connectionstyle': 'arc3,rad=' +
                                    str(([.30, .4, -.20] if idx == 0 else [0., 0., 0.])[segment]),
                                    'shrinkA': 6, 'shrinkB': 7})
        offsets = [(6, -13), (-13, 8), (7, 1)] if idx == 0 else [(-12, 8), (-18, -13), (8, -13)]
        for level, (coordinate, color, offset) in enumerate(zip(path[:3], marker_colors, offsets), 1):
            ax.scatter(*coordinate, marker='o', s=54, color=color, edgecolor='white', lw=.6, zorder=4)
            ax.annotate(str(level), coordinate, xytext=offset, textcoords='offset points', color=color)
        ax.scatter(*path[-1], marker='*', s=135, color=BLUE, edgecolor='white', lw=.65, zorder=5)
        ax.annotate('$q_*$', path[-1], xytext=(7, 6), textcoords='offset points', color=BLUE)
        span = max(np.ptp(path[:, 0]), np.ptp(path[:, 1]))
        center = (np.min(path, axis=0)+np.max(path, axis=0))/2
        ax.set_xlim(center[0]-span*.71, center[0]+span*.71)
        ax.set_ylim(center[1]-span*.71, center[1]+span*.71)
        axes_style(ax)
        panel_label(ax, [r'(a) 首点 $S_1=(0,0)$',
                         r'(b) 首点 $S_1=(1500,0)$'][idx])
        all_paths.append({'first_station_xy_m': result['first_station_xy_m'],
                          'search_history': result['search_history'],
                          'final_selected_local_xy_m': result['selected']['local_xy_m'],
                          'final_angle_step_deg': result['final_angle_step_deg']})
    legend = [Line2D([], [], marker='o', ls='', color=color, label=text)
              for color, text in zip(marker_colors, ['1：100米 / 5°', '2：20米 / 1°', '3：5米 / 0.25°'])]
    legend.append(Line2D([], [], marker='*', ls='', color=BLUE, markersize=10,
                         label='最终统一精度复核'))
    fig.legend(handles=legend, loc='upper center', ncol=2, bbox_to_anchor=(.5, 1.02),
               columnspacing=2.5, fontsize=9)
    save(fig, 'p2_18_hierarchical_selected_points', '分层搜索中的优选点更新',
         '按照输出search_history展示各层优选点，箭头表示算法优选点的更新顺序；'
         '星形点为全部已访问候选经最终0.1度读数精度复核后的推荐点。坐标为局部坐标。',
         '评分组合与分层选点', [ORIGIN, BOUNDARY, PAPER_TEXT], BASE_NOTES +
         '箭头不是机器人实际移动轨迹。各层读数步长依次为1、0.5、0.25度，最终复核为0.1度；'
         '不同层的评分精度不同，故本图不画跨层分数下降曲线，也不声称收敛。'
         '图示距离/方位为候选搜索网格步长。',
         '适合解释分层细化与最终统一精度复核，是算法方法图的补充。', all_paths)


def figure19(comparison):
    fig, ax = plt.subplots(figsize=(7.0, 4.7))
    fig.subplots_adjust(left=.13, bottom=.27, right=.97, top=.95)
    configs = comparison['precision_sensitivity']
    raw = []
    for key, color, marker, label in [('legacy_analytic', GOLD, 's', '固定解析基线点'),
                                      ('merged', BLUE, 'o', '固定本文原点选点')]:
        values = [next(r for r in config['fixed_candidate_bounds'] if r['key'] == key)
                  for config in configs]
        scores = [r['diameter_upper_bound_m'] for r in values]
        ax.plot(range(len(configs)), scores, color=color, marker=marker, markersize=5.5,
                lw=1.35, label=label)
        for x, score in enumerate(scores):
            ax.annotate(f'{score:.4f}', (x, score), xytext=(0, 8),
                        textcoords='offset points', ha='center', color=color, fontsize=9)
        raw.append({'key': key, 'fixed_local_xy_m': values[0]['local_xy_m'], 'bounds_m': scores})
    ax.set_xticks(range(len(configs)),
                  [f'$M={c["circle_sides"]}$\n$h={c["angle_step_deg"]}^\\circ$' for c in configs])
    ax.set_xlim(-.17, 2.2)
    ax.set_ylim(111, 118.8)
    ax.set_yticks(range(111, 119))
    axes_style(ax, xlabel='圆外包边数与第二读数步长', ylabel=r'组合评分 $C$（米）', equal=False)
    ax.legend(loc='upper right', bbox_to_anchor=(1., .81), fontsize=9)
    save(fig, 'p2_19_discretization_sensitivity', '固定候选点的离散精度敏感性',
         '固定原点场景中的解析基线点与本文推荐点，同时加密圆外包和第二读数网格，'
         '比较同一候选点的C。纵轴范围为111至118.8米，展示外包保守性的细微变化。',
         '评分组合与分层选点', [COMPARE, PAPER_TEXT], BASE_NOTES +
         '横轴为三组联合精度配置，不是时间或迭代次数；本图没有在每种精度重新选点。'
         '不能将差异归因于某一单独离散参数。',
         '适合数值敏感性或局限说明；展示离散外包仍有保守性。',
         data={'configurations': [{'circle_sides': c['circle_sides'],
                                  'angle_step_deg': c['angle_step_deg']} for c in configs],
               'fixed_candidates': raw})


def main():
    setup()
    selections = [read_json(ORIGIN), read_json(BOUNDARY)]
    candidates = [load_candidates(path) for path in CSVS]
    comparison = read_json(COMPARE)
    figure14(selections, candidates)
    figure15(comparison)
    figure16(comparison)
    figure17(selections, candidates)
    figure18(selections)
    figure19(comparison)


if __name__ == '__main__':
    main()
