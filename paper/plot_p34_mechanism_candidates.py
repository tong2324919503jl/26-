"""Chinese geometric figure candidates for P3/P4; no simulation results invented.

Run from any working directory. All synthetic mechanism coordinates are recorded
in each figure's JSON, while the P4 station coordinates come from production.
"""
from pathlib import Path
import json
import math
import sys

PAPER = Path(__file__).resolve().parent
ROOT = PAPER.parent
sys.path.insert(0, str(ROOT))

from figure_candidate_style import setup, save, legend, COLORS as C
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Polygon, Rectangle, Wedge, Patch
from problem3.geometry import optical_cover, contains
from problem4.search_layout import TEAMMATE22, STATIONS_SHA256


def hull(points):
    points = sorted(set(map(tuple, points)))
    def cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    lower, upper = [], []
    for p in points:
        while len(lower) > 1 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(points):
        while len(upper) > 1 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def plain(ax, xlim, ylim):
    ax.set(xlim=xlim, ylim=ylim, aspect='equal')
    ax.set_axis_off()


def xy(ax, points, **kwargs):
    return ax.scatter(*zip(*points), **kwargs)


def coverage_layouts():
    cert_path = ROOT / 'problem4/results/coverage_certificate_v4.json'
    cert = json.loads(cert_path.read_text(encoding='utf-8'))
    assert cert['points_sha256'] == STATIONS_SHA256
    assert cert['points'] == [list(p) for p in TEAMMATE22]
    assert cert['certified'] and cert['max_directional_radius_bound_m'] < 1000
    p3 = [(0., 0.)] + [(1.15*math.cos(k*math.pi/3), 1.15*math.sin(k*math.pi/3)) for k in range(6)]
    p3outer = [(0., 0.)] + [(1.7*math.cos(k*math.tau/9), 1.7*math.sin(k*math.tau/9)) for k in range(9)]
    p4 = [(x/1000, y/1000) for x, y in TEAMMATE22]
    cov7 = max(1150/math.sqrt(3), math.sqrt(1800**2+1150**2-2*1800*1150*math.cos(math.pi/6)))
    covann = max(math.sqrt(r*r+1700**2-2*r*1700*math.cos(math.pi/9)) for r in (1000, 1800))
    fig, axes = plt.subplots(1, 3, figsize=(6.65, 3.68))
    fig.subplots_adjust(left=.025, right=.985, top=.85, bottom=.30, wspace=.07)
    titles = ['（a）第三问：常规 7 点', '（b）第三问：条件 10 点', '（c）第四问：认证 22 点']
    subtitles = ['原点＋1150米六点环', '原点无信号 → 1700米九点环', '原点＋7个内点＋14个外点']
    for idx, (ax, points) in enumerate(zip(axes, (p3, p3outer, p4))):
        plain(ax, (-2.09, 2.09), (-2.1, 2.1))
        target = Circle((0, 0), 1.8, facecolor='#F8F9F9', edgecolor=C['ink'], lw=1.05, zorder=4)
        ax.add_patch(target)
        if idx < 2:
            for p in points:
                disk = Circle(p, 1., facecolor=C['blue'], edgecolor=C['blue'], alpha=.15, lw=.7, zorder=2)
                disk.set_clip_path(target)
                ax.add_patch(disk)
            # Keep the target boundary on top without hiding disk fills.
            target.set_facecolor('none')
            if idx == 1:
                ax.add_patch(Circle((0, 0), 1, fc='#F3F1EE', ec=C['gray'], hatch='///', lw=.6, zorder=3))
            ring = points[1:] + points[1:2]
            ax.plot(*zip(*ring), color=C['gray'], lw=.6, ls=(0, (3, 3)), zorder=4)
        else:
            target.set_facecolor('none')
            ax.add_patch(Polygon(hull(points), closed=True, fc=C['green'], ec=C['green'], alpha=.23, lw=1.1, zorder=1))
            inner = points[1:8] + points[1:2]
            ax.plot(*zip(*inner), color=C['gray'], lw=.6, ls=(0, (3, 3)), zorder=3)
        xy(ax, points, s=15, color=C['blue'], edgecolor='white', linewidth=.35, zorder=5)
        xy(ax, [(0, 0)], s=19, color=C['ink'], edgecolor='white', linewidth=.4, zorder=6)
        ax.set_title(titles[idx], fontsize=9.4, pad=22)
        ax.text(.5, 1.04, subtitles[idx], transform=ax.transAxes, ha='center', fontsize=8.0)
        # Common scale, avoiding dense geographic axes in the narrow panels.
        ax.plot([-.5, .5], [-1.99, -1.99], color=C['ink'], lw=1)
        ax.plot([-.5, -.5, .5, .5], [-1.95, -2.03, -2.03, -1.95], color=C['ink'], lw=.6)
        ax.text(0, -2.15, '1000米', ha='center', va='top', fontsize=8)
    footers = [f'整个目标圆覆盖半径\n不超过 {math.ceil(cov7*100)/100:.2f} 米',
               f'无源内盘可由原点反馈排除\n外环最远距离不超过 {covann:.1f} 米',
               f'连续区域认证距离上界\n{cert["max_directional_radius_bound_m"]:.3f} 米 < 1000 米']
    for ax, note in zip(axes, footers):
        ax.text(.5, -.115, note, ha='center', va='top', transform=ax.transAxes, fontsize=8.6, linespacing=1.45)
    handles = [Line2D([], [], color=C['ink'], lw=1),
               Line2D([], [], marker='o', linestyle='', color=C['blue'], markersize=4),
               Patch(fc=C['blue'], ec=C['blue'], alpha=.2),
               Patch(fc=C['green'], ec=C['green'], alpha=.28)]
    legend(fig, handles, ['1800米目标圆', '检测点', '1000米接收圆（左、中）', '检测点凸包（右）'], y=.005, ncol=2, fontsize=8.5)
    save(fig, '08_coverage_layouts', '第三、四问的条件覆盖与认证布局',
         '第三问先在原点扫描：常规分支采用原点加六个1150米环点；原点全频道无信号时，内盘已排除源，采用九个1700米环点覆盖外环。第四问展示生产22点固定坐标及独立连续区域证书。',
         ['paper/sections/p34.tex:eq:p3-points,eq:p3-cover,eq:p3-annular,eq:directional-certificate',
          'problem3/planning.py', 'problem3/lookahead.py', 'problem4/search_layout.py',
          'problem4/results/coverage_certificate_v4.json'],
         recommendation='适合替换正文原覆盖布局图；兼顾第三问条件分支与第四问当前22点布局。',
         notes={'type':'geometry_mechanism', 'not_official_results':True,
                'p3_rotation':'图示相位为0；生产按反馈选择相位并重新核验覆盖。',
                'p3_7_radius_bound_m':cov7, 'p3_annulus_radius_bound_m':covann,
                'p4_coordinate_sha256':STATIONS_SHA256,
                'p4_continuous_certificate_radius_m':cert['max_directional_radius_bound_m'],
                'limits':'右图的凸包轮廓仅展示布局；凸包包含目标圆本身不足以保证定向接收，覆盖依据为独立证书。浅蓝接收圆只用于第三问。'})


def directional_visibility():
    fig, axes = plt.subplots(1, 2, figsize=(6.65, 3.83))
    fig.subplots_adjust(left=.045, right=.975, bottom=.28, top=.87, wspace=.26)
    for ax in axes:
        plain(ax, (-1.20, 1.23), (-1.16, 1.16))
        ax.add_patch(Circle((0, 0), 1, fc='#FAFAFA', ec=C['gray'], lw=.9, ls=(0, (4, 3))))
        ax.add_patch(Wedge((0, 0), 1, -90, 90, fc=C['blue'], ec='none', alpha=.18))
        ax.plot([0, 0], [-1, 1], color=C['blue'], lw=.9, ls=(0, (4, 3)))
        xy(ax, [(0, 0)], color=C['ink'], marker='*', s=60, zorder=8)
        ax.annotate('源 $g$', (0, 0), xytext=(8, -15), textcoords='offset points', ha='left', fontsize=9)
        ax.annotate('', xy=(.66, -.57), xytext=(.12, -.57), arrowprops={'arrowstyle':'->','color':C['blue'],'lw':1.2})
        ax.text(.40, -.71, '发射方向', ha='center', fontsize=8.5, color=C['blue'])
    a, b = axes
    a.set_title('（a）单次无信号不能排除源', fontsize=10, pad=8)
    a.plot([-.64, 0, .63], [.32, 0, .36], color=C['gray'], lw=.8, ls=':')
    xy(a, [(.63, .36)], color=C['green'], marker='o', s=33, edgecolor='white', linewidth=.5, zorder=5)
    xy(a, [(-.64, .32)], color=C['red'], marker='x', s=43, linewidth=1.5, zorder=5)
    a.text(.66, .50, '阳性点 $P$', ha='center', fontsize=8.7)
    a.text(-.69, .50, '阴性点 $Q$', ha='center', fontsize=8.7)
    a.text(-.67, -.40, '接收距离内\n发射背面', ha='center', fontsize=9, linespacing=1.4)
    a.text(.40, .03, '有效\n接收半圆', ha='center', fontsize=9, linespacing=1.3, color=C['blue'])
    a.text(.5, -.085, '$P,Q$ 都在接收圆内，$Q$ 仍可能失收。', ha='center', va='top', transform=a.transAxes, fontsize=9)
    neighbours = [(.82*math.cos(math.radians(t)), .82*math.sin(math.radians(t))) for t in (20,145,260)]
    assert contains(hull(neighbours), (0, 0))
    b.add_patch(Polygon(neighbours, closed=True, facecolor=C['green'], edgecolor=C['green'], alpha=.35, lw=1.1, zorder=2))
    xy(b, neighbours, s=27, color=C['blue'], edgecolor='white', linewidth=.5, zorder=6)
    for i, p in enumerate(neighbours):
        b.annotate(f'$v_{i+1}$', p, xytext=(6 if p[0]>0 else -8, 5 if p[1]>0 else -12), textcoords='offset points', ha='left' if p[0]>0 else 'right', fontsize=9)
    b.set_title('（b）邻点凸包包含源，保证任意朝向', fontsize=10, pad=8)
    b.text(.5, -.085, r'$g\in\operatorname{conv}N(g)$，任意朝向至少一点可见。', ha='center', va='top', transform=b.transAxes, fontsize=9)
    b.text(.5, -.205, '$N(g)$：距源不超过1000米的检测点。', ha='center', va='top', transform=b.transAxes, fontsize=8.6)
    legend(fig,
        [Patch(fc=C['blue'], ec='none', alpha=.22), Patch(fc=C['green'], ec=C['green'], alpha=.35),
         Line2D([], [], color=C['gray'], ls='--', lw=.9)],
        ['有效接收半圆', '半径内检测点的凸包', '接收圆边界'], y=.02, ncol=3, fontsize=8.7)
    save(fig, '09_directional_visibility', '定向接收的阴性歧义与凸包覆盖条件',
         '左图显示阴性点虽处接收距离内仍可因背向而无信号，因此不能直接删除源位置；右图显示当源位于接收半径内邻点的凸包中时，任何发射闭半平面中均存在检测点。',
         ['paper/sections/p34.tex:eq:directional-convex,任意朝向的覆盖条件'],
         recommendation='适合放在第四问任意朝向覆盖条件之前，帮助读者理解为什么需要比全向覆盖更强的证书。',
         notes={'type':'synthetic_geometry_mechanism','not_official_results':True,
                'coordinates':'以最小接收半径1000米归一化，源位于原点，发射方向向右。',
                'neighbours':neighbours,
                'limits':'右侧三点为机制示意，不是第四问全局22点布局；完整证明需要对目标圆每个源位置成立。'})


def optical_cover_figure():
    fig, axes = plt.subplots(1, 2, figsize=(6.65, 3.85))
    fig.subplots_adjust(left=.035, right=.98, top=.86, bottom=.29, wspace=.19)
    a, b = axes
    plain(a, (-11, 105), (-39, 44))
    plain(b, (-60, 60), (-43, 43))
    a.set_title('（a）窄带：少量清除点覆盖整条带', fontsize=9.5, pad=8)
    b.set_title('（b）兜底：保留所有相交方格', fontsize=9.5, pad=8)
    length, halfwidth, radius = 90., 8., 19.99
    count = math.ceil(length/(2*math.sqrt(radius**2-halfwidth**2)))
    centers = [((i+.5)*length/count, 0.) for i in range(count)]
    assert math.hypot(length/(2*count), halfwidth) <= radius
    for center in centers:
        a.add_patch(Circle(center, radius, fc=C['blue'], ec=C['blue'], alpha=.20, lw=.8))
    a.add_patch(Rectangle((0, -halfwidth), length, 2*halfwidth, fc=C['peach'], ec=C['peach'], alpha=.32, lw=1.2))
    for x in (30, 60):
        a.plot([x, x], [-halfwidth, halfwidth], color=C['gray'], lw=.7, ls=(0, (3, 3)))
    xy(a, centers, s=24, color=C['blue'], edgecolor='white', linewidth=.4, zorder=4)
    a.plot([15, 30], [0, 8], color=C['ink'], lw=.9, ls=':')
    xy(a, [(30,8)], s=12, color=C['ink'], zorder=5)
    a.annotate('最远角点也在圆内', (30, 8), xytext=(8, 31), fontsize=8.6,
               arrowprops={'arrowstyle':'-','color':C['gray'],'lw':.7})
    a.annotate('', (90, -29), (0, -29), arrowprops={'arrowstyle':'<->','color':C['ink'],'lw':.8})
    a.text(45, -34, r'$\ell=90$ 米，等分为 3 段', ha='center', va='top', fontsize=8.5)
    a.annotate('', (98, halfwidth), (98, -halfwidth), arrowprops={'arrowstyle':'<->','color':C['ink'],'lw':.8})
    a.text(97, 14, '$2b=16$ 米', ha='right', fontsize=8.4)
    region = [(-45., 0.), (-24., -21.), (22., -19.), (45., 0.), (25., 23.), (-20., 22.)]
    fallback = optical_cover(region, 26.)
    # For this symmetric longest-chord illustration the production rotation is
    # pi or zero. Each returned center therefore has an axis-aligned 26 m cell.
    assert len(fallback) == 8
    external = [p for p in fallback if not contains(region, p)]
    internal = [p for p in fallback if contains(region, p)]
    for p in fallback:
        b.add_patch(Rectangle((p[0]-13, p[1]-13), 26, 26, facecolor='#F8F9FA', edgecolor=C['gray'], lw=.6))
    b.add_patch(Polygon(region, closed=True, fc=C['peach'], ec=C['peach'], alpha=.38, lw=1.3))
    for p in fallback:
        b.add_patch(Circle(p, 19.99, fc='none', ec=C['blue'], alpha=.55, lw=.65))
    xy(b, internal, s=23, color=C['blue'], edgecolor='white', linewidth=.4, zorder=5)
    xy(b, external, s=27, marker='s', color=C['purple'], edgecolor='white', linewidth=.4, zorder=5)
    chosen = (39.,13.)
    assert chosen in external
    b.plot([39, 52], [13, 26], color=C['ink'], lw=.85, ls=':')
    b.annotate('区域外的边界格中心\n仍须保留', chosen, xytext=(-12, 34), fontsize=8.4, ha='center', linespacing=1.3,
               arrowprops={'arrowstyle':'-','color':C['gray'],'lw':.75})
    b.annotate('', (-52,-34), (-26,-34), arrowprops={'arrowstyle':'<->','color':C['ink'],'lw':.8})
    b.text(-39, -39, '$h=26$ 米', ha='center', va='top', fontsize=8.5)
    # Compact proof statements live beneath each panel, away from geometry.
    a.text(.5, -.14, r'$n\geq\ell\,/\,\left(2\sqrt{19.99^2-b^2}\right)$', transform=a.transAxes,
           ha='center', va='top', fontsize=10)
    b.text(.5, -.14, r'$d_{\max}\leq h/\sqrt{2}\approx18.385<20$ 米', transform=b.transAxes,
           ha='center', va='top', fontsize=10)
    legend(fig,
        [Patch(fc=C['peach'], ec=C['peach'], alpha=.38), Line2D([], [], color=C['blue'], lw=.9),
         Line2D([], [], marker='o', color=C['blue'], ls='', markersize=4),
         Line2D([], [], marker='s', color=C['purple'], ls='', markersize=4)],
        ['候选区域', '19.99米清除圆盘', '清除点', '区域外的必要清除点'], y=.008, ncol=2, fontsize=8.5)
    save(fig, '10_optical_cover', '窄带光学清除与完整网格兜底',
         '左侧按纵向分段，利用最远角点到段中心的距离约束，使19.99米圆盘覆盖整个窄带；右侧保留所有与候选区相交的26米方格的中心，包括位于区域外的中心，保证任意格内点距离中心不超过18.385米。',
         ['paper/sections/p34.tex:eq:optical-band,eq:optical-cover', 'problem3/lookahead.py', 'problem3/geometry.py:optical_cover'],
         recommendation='适合解释第三问清除环节和第三、四问共用的有限兜底；两图几何尺度分别独立。',
         notes={'type':'synthetic_geometry_mechanism', 'not_official_results':True,
                'strip':{'length_m':length,'halfwidth_m':halfwidth,'centers':centers,'radius_m':radius},
                'grid':{'candidate_polygon':region,'spacing_m':26,'centers_from_production_function':fallback,'external_centers':external},
                'limits':'只是构造的机制示例，不含正式测试场景、实际轨迹或耗时结果；左图展示保证覆盖的整套点，并不要求成功清除后继续访问。'})


if __name__ == '__main__':
    setup()
    coverage_layouts()
    directional_visibility()
    optical_cover_figure()
    print('Created 08_coverage_layouts, 09_directional_visibility, 10_optical_cover (PDF/SVG/PNG/JSON).')
