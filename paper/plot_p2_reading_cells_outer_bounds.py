"""Build manuscript figure 09: reading cells and circular outer bounds.

The original/ subfolder preserves the preceding figure. This generator owns
the manuscript PDF and keeps the edited vector, raster and evidence files here.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Polygon

from p2_candidate_style import ROOT, PAPER, BLUE, INK, GREY, GOLD, GREEN, LIGHT_BLUE, LIGHT_GREY, axes_style, setup
from plot_p2_scoring_candidates import polygon, diameter

sys.path.insert(0, str(ROOT))
from problem2 import solve as model

BASE = PAPER / 'figures' / 'problem2_candidates'
DEST = BASE / 'p2_09_outer_bounds_trial'
STEM = 'p2_09_reading_cells_outer_bounds'
MANUSCRIPT = PAPER / 'figures' / 'p2_09_reading_cells.pdf'
OUTER = '#9a5850'
SOURCE_PATHS = ['paper/sections/p12.tex', 'problem2/solve.py',
                'problem2/results/selection.json',
                'paper/figures/problem2_candidates/p2_09_reading_cells.json']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def circumscribed_polygon(center, radius, count=360):
    angles = (np.arange(count) + .5) * (2 * np.pi / count)
    return np.asarray(center) + (radius / math.cos(math.pi / count)) * np.c_[np.cos(angles), np.sin(angles)]


def circle_boundary_detail(radius, normal_deg, s):
    """True circle and 360-halfplane envelope in an orthonormal boundary frame.

    s is the tangent coordinate in metres; h is the outward normal coordinate,
    measured from the true circle at angle normal_deg, displayed in millimetres.
    """
    relative = np.radians(np.arange(360) - normal_deg)
    positive = np.cos(relative) > 1e-8
    co, si = np.cos(relative[positive]), np.sin(relative[positive])
    normal_limits = (radius - s[:, None] * si) / co
    outer = (normal_limits.min(axis=1) - radius) * 1000
    true = (np.sqrt(radius**2 - s*s) - radius) * 1000
    assert np.min(outer - true) > -1e-6
    return true, outer


def data():
    plan = json.loads((ROOT / 'problem2/results/selection.json').read_text(encoding='utf-8'))
    baseline = json.loads((DEST / 'original/p2_09_reading_cells.json').read_text(encoding='utf-8'))
    assert plan['first_station_xy_m'] == [0., 0.] and plan['first_bearing_deg'] == 0.
    assert plan['error_deg'] == 1. and plan['circle_sides'] == 360
    q = tuple(plan['selected']['local_xy_m'])
    assert list(q) == baseline['data']['q_local_xy_m']
    prior = model.first_region_outer_local(tuple(plan['first_station_xy_m']),
                plan['first_bearing_deg'], plan['error_deg'], plan['circle_sides'])
    candidate = model.prepare_candidate_region_local(prior, q, plan['error_deg'], 360)
    angles = baseline['data']['cell_centers_deg']
    polys = [model.clip_candidate_observation_local(candidate, a, 1.05) for a in angles]
    expected = baseline['data']['cell_diameters_m']
    assert all(abs(model.polygon_diameter(p) - value) < 1e-8 for p, value in zip(polys, expected))
    assert candidate['polygon_local_xy_m'] == prior
    circles = [{'name': 'target', 'symbol': 'D_0', 'center': (0., 0.), 'radius': 1800.},
               {'name': 'first_distance', 'symbol': 'D_1', 'center': (0., 0.), 'radius': 1500.},
               {'name': 'second_distance', 'symbol': 'D_2', 'center': q,
                'radius': candidate['second_distance_upper_m']}]
    normals = np.c_[np.cos(np.radians(np.arange(360))), np.sin(np.radians(np.arange(360)))]
    for circle in circles:
        outer = circumscribed_polygon(circle['center'], circle['radius'])
        # Each vertex is the intersection of adjacent tangent halfplanes;
        # every other halfplane is satisfied, and radial expansion is exact.
        assert np.max((outer - circle['center']) @ normals.T - circle['radius']) < 1e-8
        expected_expansion = circle['radius'] * (1 / math.cos(math.pi / 360) - 1)
        assert abs(np.max(np.linalg.norm(outer - circle['center'], axis=1)) - circle['radius'] - expected_expansion) < 1e-8
        circle['outer_polygon'] = outer
        circle['max_radial_expansion_m'] = expected_expansion
    # Active first-distance tangent in the third cell, normal 359 degrees.
    n = np.array([math.cos(math.radians(359)), math.sin(math.radians(359))])
    t = np.array([-n[1], n[0]])
    endpoints = [np.array(v) for v in polys[2] if abs(np.dot(n, v) - 1500) < 1e-6]
    endpoints.sort(key=lambda v: np.dot(t, v))
    active = [endpoints[0], endpoints[-1]]
    smax = float(np.dot(t, active[-1]))
    assert 2.37 < smax < 2.39
    sliver = max(float(np.linalg.norm(v) - 1500) for v in polys[2]) * 1000
    assert 1.88 < sliver < 1.89
    return q, candidate, angles, polys, circles, active, smax, sliver


def overview(fig, q, candidate, angles, polys):
    ax = fig.add_axes([.17, .662, .66, .30])
    polygon(ax, candidate['polygon_local_xy_m'], GREY, LIGHT_GREY, label='$Q(q_*)$', lw=1.)
    ax.scatter([0, q[0]], [0, q[1]], c=INK, s=20, zorder=8)
    ax.annotate('$S_1$', (0, 0), xytext=(-12, -15), textcoords='offset points')
    ax.annotate('$S(q_*)$', q, xytext=(8, 2), textcoords='offset points')
    for i, (angle, poly, col) in enumerate(zip(angles, polys, [GREEN, GOLD, BLUE])):
        polygon(ax, poly, col, col, alpha=.8, label=f'$P_{{k_{i+1}}}$')
        d = np.array([math.cos(math.radians(angle)), math.sin(math.radians(angle))])
        target = np.array(q) - q[1] / d[1] * d
        ax.plot([q[0], target[0]], [q[1], target[1]], color=col, lw=1.)
        fraction, offset, alignment = [(.50, (-12, 9), 'right'), (.45, (14, -12), 'left'),
                                        (.55, (10, 9), 'left')][i]
        midpoint = (1 - fraction) * np.array(q) + fraction * target
        ax.annotate(rf'$\psi_{{k_{i+1}}}={angle:.1f}^\circ$', midpoint, xytext=offset,
                    textcoords='offset points', color=col, ha=alignment, va='bottom', fontsize=10.5)
    axes_style(ax)
    ax.set(xlim=(-80, 1570), ylim=(-80, 645))
    ax.legend(loc='upper left', ncol=4, fontsize=8.5, facecolor='none', framealpha=1., edgecolor='#a0a0a0')
    return ax


def cell_panel(fig, left, poly, col, index, candidate, circle, active):
    ax = fig.add_axes([left, .368, .263, .205])
    polygon(ax, candidate['polygon_local_xy_m'], GREY, LIGHT_GREY, lw=.7)
    polygon(ax, poly, col, ['#edf3f2', '#f2eadc', LIGHT_BLUE][index], lw=1.4)
    diameter(ax, poly)
    coords = np.asarray(poly)
    center = (coords.max(axis=0) + coords.min(axis=0)) / 2
    half = max(43, np.ptp(coords[:, 0]) * .66)
    ax.set(xlim=(center[0] - half, center[0] + half), ylim=(-half*.7, half*.7))
    axes_style(ax)
    ax.text(.5, .88, f'$D_{{k_{index+1}}}={model.polygon_diameter(poly):.2f}$ 米',
            transform=ax.transAxes, ha='center', va='center', fontsize=12.5, zorder=12)
    if index < 2:
        ax.text(.97, .055, r'$P_{k_' + str(index+1) + r'}\subset D_0\cap D_1\cap D_2$',
                transform=ax.transAxes, ha='right', va='bottom', color=GREY, fontsize=8.5)
    else:
        # Draw the true active circular boundary, not an invented clipping arc.
        ys = np.linspace(-60, 60, 1200)
        xs = np.sqrt(1500**2 - ys**2)
        ax.plot(xs, ys, color=INK, lw=1.0, ls=(0, (2, 2)), zorder=9)
        exterior = np.asarray(circle['outer_polygon'])
        ax.plot(*np.vstack([exterior, exterior[0]]).T, color=OUTER, lw=.9, zorder=9)
        # Equal data scales keep this highlight circular. Its transparent
        # interior leaves the actual clipping edge and diameter endpoint clear.
        edge_center = np.mean(active, axis=0)
        radius = 4.3
        ax.add_patch(Circle(edge_center, radius, facecolor='none',
                            edgecolor=OUTER, lw=.8, zorder=12))
        ax.annotate(r'$\partial\widehat D_1$', edge_center + [radius*.5, radius*.85], xytext=(1510, -6),
                    ha='center', fontsize=9, color=OUTER,
                    arrowprops=dict(arrowstyle='->', lw=.7, color=OUTER), zorder=13)
    fig.text(left + .263/2, .304, f'({chr(97+index)}) 第 {index+1} 组读数单元',
             ha='center', fontsize=10.5)
    return ax


def boundary_panel(fig, left, index, circle, smax, sliver):
    # The first two representative boundary frames are independent from their
    # cell windows. The third frame is the actual active edge in panel (c).
    if index < 2:
        alpha = .5
        radius = circle['radius']
        limit = radius * math.sin(math.radians(.5)) * 1.18
        s = np.linspace(-limit, limit, 700)
        title = [('目标圆', r'$\widehat D_0$', '1800'),
                 ('第二距离圆', r'$\widehat D_2$', '1000')][index]
        subtitle = ['(d) 目标圆外切边界', '(e) 第二距离圆外切边界'][index]
    else:
        alpha = 359.
        radius = circle['radius']
        s = np.linspace(-.12, smax + .28, 700)
        title = ('第一距离圆', r'$\widehat D_1$', '1500')
        subtitle = '(f) 第一距离圆局部裁边'
    ax = fig.add_axes([left + .018, .082, .23, .138])
    actual, outer = circle_boundary_detail(radius, alpha, s)
    if index < 2:
        ax.fill_between(s, actual, outer, facecolor='#ead3ce', edgecolor='none', alpha=.8)
        ax.plot(s, outer, color=OUTER, lw=1.45)
        ax.plot(s, actual, color=INK, lw=1.1, ls=(0, (3, 2)))
        contact_s = radius * math.sin(math.radians(.5))
        contact_h = (radius * math.cos(math.radians(.5)) - radius) * 1000
        ax.scatter([-contact_s, contact_s], [contact_h, contact_h], s=10, c=INK, zorder=8)
        ax.scatter([0], [circle['max_radial_expansion_m'] * 1000], s=15, c=OUTER, zorder=8)
        ax.set_xlim(s[0], s[-1])
        ax.set_ylim(min(actual)*1.10, circle['max_radial_expansion_m']*1000*1.37)
    else:
        ax.fill_between(s, actual, outer, where=(s >= 0) & (s <= smax),
                        facecolor='#ead3ce', alpha=.85)
        ax.plot(s, outer, color=OUTER, lw=1.45)
        ax.plot(s, actual, color=INK, lw=1.1, ls=(0, (3, 2)))
        ax.plot([smax, smax], [-sliver, 0], color=BLUE, lw=1.0)
        ax.scatter([0, smax], [0, 0], c=BLUE, s=16, zorder=8)
        ax.annotate(f'{sliver:.3f} mm', (smax, -sliver*.5), xytext=(-9, 0),
                    textcoords='offset points', ha='right', va='center', fontsize=8.7, color=BLUE)
        ax.set(xlim=(s[0], s[-1]), ylim=(-2.8, .55))
    axes_style(ax, r'切向 $s$（米）', r'法向 $h$（毫米）', equal=False)
    ax.tick_params(labelsize=8)
    ax.xaxis.label.set_size(8.8)
    ax.yaxis.label.set_size(8.8)
    ax.set_title(f'{title[0]} {title[1]}，$R={title[2]}$ 米', fontsize=9.7, pad=7)
    fig.text(left+.263/2, .028, subtitle, ha='center', fontsize=9.7, color=INK)
    return ax


def main():
    setup()
    DEST.mkdir(parents=True, exist_ok=True)
    protected = [DEST / 'original' / ('p2_09_reading_cells.' + ext)
                 for ext in ('pdf', 'svg', 'png', 'json')]
    before = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    q, candidate, angles, polys, circles, active, smax, sliver = data()
    fig = plt.figure(figsize=(13.6, 11.2))
    overview(fig, q, candidate, angles, polys)
    fig.text(.5, .612, r'$Q(q)=W_1\cap T_1\cap H_1\cap\widehat D_0\cap\widehat D_1\cap\widehat D_2$',
             ha='center', va='center', fontsize=12)
    centers = [.066, .380, .694]
    for i, (left, poly, col) in enumerate(zip(centers, polys, [GREEN, GOLD, BLUE])):
        cell_panel(fig, left, poly, col, i, candidate, circles[1], active)
    fig.legend(handles=[Line2D([0], [0], color=INK, lw=1.1, ls=(0, (3, 2)), label='真实圆弧'),
                        Line2D([0], [0], color=OUTER, lw=1.45, label='360 边形外切边'),
                        Polygon([[0,0],[1,0],[1,1]], facecolor='#ead3ce', edgecolor='none', label='外包增量')],
               loc='center', bbox_to_anchor=(.5, .269), ncol=3, fontsize=9.3,
               frameon=False, columnspacing=3)
    for i, circle in enumerate([circles[0], circles[2], circles[1]]):
        boundary_panel(fig, centers[i], i, circle, smax, sliver)
    caption = ('在原图三个读数及单元直径不变的条件下，显式标出Q由第一扇区、第一条带、有效投影下界与三个圆的360边外包求交。'
               '(a)—(c)为三组读数单元；(d)目标圆外切边界、(e)第二距离圆外切边界展示圆弧与外包折线，'
               '(f)第一距离圆局部裁边对应(c)圆圈内的实际裁边。')
    notes = ('本原点算例中目标圆1800米被第一距离圆1500米包含，第二距离圆1000米未进一步裁切Q；(a)(b)三圆约束均不活跃。'
             '(d)(e)展示各自圆边界的外切几何，不对应(a)(b)单元附近的位置。(c)实际外切边的法向为359度，跨度2.377米，单元顶点最大越出真实圆约1.884毫米。'
             '最下排横轴为切向米，纵轴为法向毫米，采用不同显示比例以分辨外包增量；360边数未减少，原图几何与1.05度评分半角未夸张。')
    for ext in ('pdf', 'svg', 'png'):
        kwargs = {'dpi': 260} if ext == 'png' else {}
        if ext == 'pdf':
            kwargs['metadata'] = {'Title': '同一候选点下的三个读数单元及几何外包', 'Subject': caption, 'Author': ''}
        fig.savefig(DEST / (STEM + '.' + ext), bbox_inches='tight', pad_inches=.08, **kwargs)
    plt.close(fig)
    after = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    assert before == after, 'A preserved original figure changed during rendering.'
    MANUSCRIPT.write_bytes((DEST / (STEM + '.pdf')).read_bytes())
    metadata = {'id': STEM, 'caption': caption, 'notes': notes,
        'original_preserved': before == after, 'original_sha256': before,
        'manuscript_asset': str(MANUSCRIPT.relative_to(ROOT)).replace('\\', '/'),
        'manuscript_sha256': sha(MANUSCRIPT),
        'panel_names': {'a': '第1组读数单元', 'b': '第2组读数单元', 'c': '第3组读数单元',
                        'd': '目标圆外切边界', 'e': '第二距离圆外切边界', 'f': '第一距离圆局部裁边'},
        'source_sha256': {p: sha(ROOT / p) for p in SOURCE_PATHS},
        'q_local_xy_m': q, 'cell_centers_deg': angles,
        'cell_diameters_m': [model.polygon_diameter(p) for p in polys],
        'circle_constraints': [{k: v for k, v in c.items() if k != 'outer_polygon'} for c in circles],
        'active_edge_normal_deg': 359, 'active_edge_endpoints_m': [v.tolist() for v in active],
        'active_edge_length_m': smax, 'max_cell_vertex_outside_true_first_circle_mm': sliver}
    (DEST / (STEM + '.json')).write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (DEST / 'README.md').write_text('# 评分二圆约束外包正文图\n\n'
        '在用户提供的新版图09上微调后，已替换正文插图。目录沿用试版名称，original/保留修改前图稿。\n\n'
        f'- [正文图PNG]({STEM}.png)\n- [正文图PDF]({STEM}.pdf)\n'
        '- [保留原版](original/p2_09_reading_cells.pdf)\n\n' + caption + '\n\n' + notes + '\n\n'
        '记号：D0为目标圆，D1为第一距离上界圆，D2为第二距离上界圆；W1、T1、H1分别为第一扇区、第一条带和有效前向投影约束。'
        '\n\n复现：`python paper/plot_p2_reading_cells_outer_bounds.py`，输出本目录的PDF/SVG/PNG/JSON，并同步`paper/figures/p2_09_reading_cells.pdf`。'
        '旧候选图生成器只更新候选目录，不再覆盖本正文图。\n', encoding='utf-8')
    print(json.dumps({'outputs': str(DEST), 'original_preserved': True,
                      'cell_diameters_m': metadata['cell_diameters_m'],
                      'circle_outer_checks_passed': True}, ensure_ascii=False))


if __name__ == '__main__':
    main()
