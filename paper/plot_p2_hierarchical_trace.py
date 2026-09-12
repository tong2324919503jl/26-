"""Draw actual production-search candidate traces, keeping old figure 14 intact."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import ConnectionPatch, Rectangle
from matplotlib.ticker import MaxNLocator

from p2_candidate_style import ROOT, BLUE, GOLD, GREEN, INK, GREY, setup, axes_style

SOURCE = ROOT / 'problem2/results/hierarchical_trace_20260912'
DEST = ROOT / 'paper/figures/problem2_candidates/p2_14_hierarchical_trace'
COLORS = [BLUE, GOLD, GREEN]
LABELS = ['第一层', '第二层', '第三层']
STEPS = ['100 米 / 5°', '20 米 / 1°', '5 米 / 0.25°']
MANIFEST = []


def points(rows):
    return np.array([r['local_xy_m'] for r in rows], dtype=float).reshape(-1, 2)


def subset(stage, positive=False, new=True):
    return [r for r in stage['rows']
            if (not positive or r['local_xy_m'][1] > 0)
            and (not new or r['is_new'])]


def key(p):
    return tuple(round(float(x), 8) for x in p)


def check_trace(trace):
    seen = set()
    for i, stage in enumerate(trace['stages']):
        keys = {key(r['local_xy_m']) for r in stage['rows']}
        new = {key(r['local_xy_m']) for r in subset(stage)}
        assert seen <= keys and new == keys-seen
        assert len(keys) == stage['candidate_count']
        assert len(new) == stage['new_candidate_count']
        # Upper-half selection is allowed only after confirming true symmetry.
        assert all(key((a, -b)) in keys for a, b in keys)
        assert all(key((a, -b)) in new for a, b in new)
        seen = keys


def domain(ax, positive=False):
    a = np.linspace(0, 1005, 6001)
    e = math.radians(1)
    upper = np.full_like(a, np.inf)
    for d in (5., 1000.):
        t = 1000**2-(a-d*math.cos(e))**2
        upper = np.minimum(upper, np.where(t >= 0, np.sqrt(np.maximum(t, 0))-d*math.sin(e), -1))
    lower = (5+a*math.sin(e))/math.cos(e)
    ax.fill_between(a, lower, upper, where=upper > lower, color='#f2f2f2',
                    edgecolor='#999999', linewidth=.65, zorder=0)
    if not positive:
        ax.fill_between(a, -upper, -lower, where=upper > lower, color='#f2f2f2',
                        edgecolor='#999999', linewidth=.65, zorder=0)
    return ax


def best(ax, stage, label=True):
    x, y = stage['selected_local_xy_m']
    ax.scatter([x], [y], marker='*', s=95, c=INK, edgecolors='white',
               linewidths=.55, zorder=6)
    if label:
        ax.annotate(r'$q_{%d}$' % stage['level'], (x, y), xytext=(7, 9),
                    textcoords='offset points', fontsize=11)


def new_dots(ax, rows, level, size=15):
    p = points(rows)
    ax.scatter(p[:, 0], p[:, 1], s=size, facecolors=COLORS[level-1],
               edgecolors='none', alpha=.92, zorder=3)


def legend(fig, y=.055, include_old=True):
    handles = [Line2D([], [], marker='o', ls='', color=c, markersize=5,
                      label=l+'新增点') for c, l in zip(COLORS, LABELS)]
    if include_old:
        handles.append(Line2D([], [], marker='o', ls='', markerfacecolor='none',
                              markeredgecolor='#b8b8b8', markersize=5, label='保留的旧点'))
    handles.append(Line2D([], [], marker='*', ls='', color=INK, markersize=9,
                          label='本层优选点'))
    fig.legend(handles=handles, loc='lower center', bbox_to_anchor=(.5, y),
               ncol=len(handles), frameon=False, columnspacing=1.6, handletextpad=.45)


def save(fig, stem, title, caption, trace_files, display):
    DEST.mkdir(parents=True, exist_ok=True)
    for ext in ('pdf', 'svg', 'png'):
        options = {'dpi': 280} if ext == 'png' else {}
        if ext == 'pdf':
            options['metadata'] = {'Title': title, 'Subject': caption, 'Author': ''}
        fig.savefig(DEST / f'{stem}.{ext}', bbox_inches='tight', pad_inches=.10, **options)
    meta = {'title': title, 'caption': caption,
            'section': '5.2.5 评分组合与分层选点',
            'sources': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in trace_files},
            'style': '与当前第一问一致：宋体正常字重、STIX数学、白底、细轴框、浅灰网格。',
            'data_provenance': '本次真实执行生产选点程序得到的自建离线算例；不是官方数据。',
            'display': display,
            'notes': '点的坐标不抖动、不平移、不按评分删选。颜色表示首次访问的层。'
                     '程序保留旧候选，收紧的是新增加密网格，不是累计候选集。'
                     '各层优选点采用不同的本层读数评分步长，最终仍需0.1度统一复核。'}
    (DEST / f'{stem}.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    MANIFEST.append({'stem': stem, **meta})
    plt.close(fig)
    print(stem, flush=True)


def square_window(rows, pad=.16):
    p = points(rows)
    low, high = p.min(axis=0), p.max(axis=0)
    width = max(high-low)*(1+2*pad)
    center = (low+high)/2
    return [center[0]-width/2, center[0]+width/2,
            center[1]-width/2, center[1]+width/2]


def progressive(trace, path):
    stages = trace['stages']
    windows = [[-25, 1075, -80, 1020]] + [square_window(subset(s, True)) for s in stages[1:]]
    fig, axes = plt.subplots(1, 3, figsize=(12.3, 5.7))
    fig.subplots_adjust(left=.06, right=.985, bottom=.27, top=.82, wspace=.29)
    details = []
    for i, (ax, stage, win) in enumerate(zip(axes, stages, windows)):
        domain(ax, True)
        old = [r for r in stage['rows'] if not r['is_new'] and r['local_xy_m'][1] > 0]
        if old:
            p = points(old)
            ax.scatter(p[:, 0], p[:, 1], s=20, facecolors='none', edgecolors='#c0c0c0', linewidths=.6, zorder=1)
        rows = subset(stage, True)
        new_dots(ax, rows, i+1, 15 if i == 0 else 22)
        best(ax, stage, False)
        ax.set(xlim=win[:2], ylim=win[2:])
        axes_style(ax)
        ax.xaxis.set_major_locator(MaxNLocator(4))
        ax.yaxis.set_major_locator(MaxNLocator(4))
        fig.text(.5*(ax.get_position().x0+ax.get_position().x1), .94,
                 LABELS[i]+'：'+STEPS[i], color=COLORS[i], ha='center', fontsize=11)
        ax.text(.5, -.29, f'({chr(97+i)}) 新增 {len(rows)} 点（上半域）',
                transform=ax.transAxes, ha='center', fontsize=10.5)
        details.append({'level': i+1, 'drawn_new_ids': [r['candidate_id'] for r in rows],
                        'window_local_m': win, 'new_upper_count': len(rows),
                        'full_new_count': stage['new_candidate_count']})
    fig.canvas.draw()
    for i in range(2):
        x0, x1, y0, y1 = windows[i+1]
        axes[i].add_patch(Rectangle((x0, y0), x1-x0, y1-y0, fill=False,
                                   edgecolor=COLORS[i+1], lw=1, ls='--', zorder=4))
        # Route the zoom leader through the clear strip above the axes,
        # so it never crosses the next panel's y label or tick labels.
        source = fig.transFigure.inverted().transform(axes[i].transData.transform((x1, y1)))
        target_box = axes[i+1].get_position()
        target_x = (target_box.x0+target_box.x1)/2
        route_y = .87
        fig.add_artist(Line2D([source[0], source[0], target_x],
                              [source[1], route_y, route_y], transform=fig.transFigure,
                              color=COLORS[i+1], lw=.85, clip_on=False))
        con = ConnectionPatch((target_x, route_y), (target_x, target_box.y1+.008),
                              coordsA=fig.transFigure, coordsB=fig.transFigure,
                              arrowstyle='->', color=COLORS[i+1], lw=.85,
                              clip_on=False)
        fig.add_artist(con)
    legend(fig, .035)
    save(fig, 'p2_14a_progressive_zoom', '真实三层选点过程与逐级放大',
         '原点自建算例本次真实运行的逐层新增候选。为消除上下镜像重复，图示全部上半域新增点；'
         '下半域实际候选已逐点核验镜像对应，完整记录保存在原始轨迹。虚线框与箭头连接下一幅放大范围，'
         '各图坐标均为原始局部米制坐标且横纵等比例。灰色空心点为保留的旧候选，星号为本层优选点。'
         '各层星号不表示最终推荐点；最终对548个已访问候选以0.1度统一复核，选回第二层产生的'
         '(842.144,546.895)米候选，上界112.3293米。',
         [path], {'type': 'successive_zoom', 'sample_rule': 'b>0, all new points, verified symmetric counterpart',
                  'jitter': False, 'stages': details})


def same_scale(trace, path):
    fig, axes = plt.subplots(1, 3, figsize=(10.9, 6.5))
    fig.subplots_adjust(left=.065, right=.985, bottom=.22, top=.87, wspace=.26)
    details = []
    for i, (ax, stage) in enumerate(zip(axes, trace['stages'])):
        domain(ax)
        rows = subset(stage)
        new_dots(ax, rows, i+1, 12 if i == 0 else 18)
        best(ax, stage, False)
        ax.set(xlim=(-50, 1060), ylim=(-930, 930), xticks=[0, 500, 1000], yticks=[-800, -400, 0, 400, 800])
        axes_style(ax)
        ax.set_title(LABELS[i]+'：'+STEPS[i], color=COLORS[i], pad=14)
        ax.text(.5, -.16, f'({chr(97+i)}) 新增 {len(rows)} 点', transform=ax.transAxes,
                ha='center', fontsize=10.5)
        details.append({'level': i+1, 'drawn_new_ids': [r['candidate_id'] for r in rows],
                        'new_count': len(rows)})
    legend(fig, .045, include_old=False)
    save(fig, 'p2_14b_same_scale_layers', '同尺度下的三层实际新增候选',
         '原点自建算例同一次真实运行，每幅只显示对应层首次访问的全部候选；'
         '三个坐标窗口及比例完全相同，完整保留上下两个分支。'
         '点色分别对应第一至第三层，星号为本层优选点，图中未重复绘制旧候选。',
         [path], {'type': 'same_scale_separate_panels', 'sampling': 'none',
                  'jitter': False, 'window_local_m': [-50, 1060, -930, 930], 'stages': details})


def two_scenes(traces, paths):
    fig, axes = plt.subplots(2, 3, figsize=(11.7, 9.1))
    fig.subplots_adjust(left=.085, right=.985, bottom=.15, top=.91, wspace=.27, hspace=.47)
    details = []
    for scene, trace in enumerate(traces):
        row_data = []
        for i, stage in enumerate(trace['stages']):
            ax = axes[scene, i]
            domain(ax, True)
            rows = subset(stage, True)
            new_dots(ax, rows, i+1, 10 if i == 0 else 16)
            best(ax, stage, False)
            ax.set(xlim=(-25, 1050), ylim=(-25, 950), xticks=[0, 250, 500, 750, 1000],
                   yticks=[0, 250, 500, 750])
            axes_style(ax)
            if scene == 0:
                ax.set_title(LABELS[i]+'：'+STEPS[i], color=COLORS[i], pad=13)
            ax.text(.5, -.25, f'({chr(97+scene*3+i)}) 新增 {len(rows)} 点（上半域）',
                    transform=ax.transAxes, ha='center', fontsize=10.2)
            row_data.append({'level': i+1, 'drawn_new_ids': [r['candidate_id'] for r in rows]})
        details.append(row_data)
    fig.text(.028, .715, r'$S_1=(0,0)$', rotation=90, ha='center', va='center', fontsize=12)
    fig.text(.028, .347, r'$S_1=(1500,0)$', rotation=90, ha='center', va='center', fontsize=12)
    legend(fig, .03, include_old=False)
    save(fig, 'p2_14c_two_scene_layers', '两个自建场景的实际分层选点',
         '两组首点分别为原点和(1500,0)，首次示向均为0度。按同一尺度展示上半域每层全部新增点，'
         '下半域镜像已核验。边界场景除局部加密点外，生产算法仍加入对应方位的安全径向边界点，'
         '因此远端边界点保留可见，不把全部新增候选伪画成单一紧簇。',
         paths, {'type': 'two_scene_same_scale', 'sample_rule': 'b>0, all new points',
                 'jitter': False, 'scenes': details})


def main():
    setup()
    paths = [SOURCE / 'origin.json', SOURCE / 'boundary.json']
    traces = [json.loads(p.read_text(encoding='utf-8')) for p in paths]
    for trace in traces:
        check_trace(trace)
    progressive(traces[0], paths[0])
    same_scale(traces[0], paths[0])
    two_scenes(traces, paths)
    (DEST / 'figure_manifest.json').write_text(json.dumps(MANIFEST, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
