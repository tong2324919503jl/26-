"""Render one solve run, keeping explanations and evidence outside each figure.

Examples (relative paths are resolved against the repository, never the cwd)::

    python paper/plot_balanced_search.py --problem 3 --run-id final_run
    python paper/plot_balanced_search.py --problem4 --run-id preview --allow-partial

The source dataset/run are validated by benchmark_balanced_search.load_run.
No policy is run and no platform connection is made by this module.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

PAPER = Path(__file__).resolve().parent
ROOT = PAPER.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PAPER))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Patch
from matplotlib.ticker import MaxNLocator, MultipleLocator, PercentFormatter
import numpy as np

from figure_candidate_style import COLORS, setup, tidy

SOURCE_COUNTS = tuple(range(10, 17))
GROUP_COLORS = ('#6F91AB', '#7AA7AC', '#90AC9A', '#C1B38A',
                '#D0A184', '#BD9194', '#ADA0B7')
FIGURE_NAMES = ('two_metrics', 'time_distribution', 'time_components',
                'time_ecdf', 'case_route', 'case_progress')
METRIC_TIME = '平均定位清除时间 / (s/源)'


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative_name(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def json_read(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def outside_legend(fig, handles, labels, *, ncol=4, y=0.02):
    if not handles:
        return
    # Matplotlib packs columns first; feed handles so the visible order reads by rows.
    ncol = min(ncol, len(handles))
    nrow = math.ceil(len(handles)/ncol)
    order = [r*ncol+c for c in range(ncol) for r in range(nrow) if r*ncol+c < len(handles)]
    handles, labels = [handles[i] for i in order], [labels[i] for i in order]
    leg = fig.legend(handles, labels, loc='lower center',
                     bbox_to_anchor=(0.5, y), ncol=ncol, frameon=True,
                     borderpad=0.42, columnspacing=1.25, handlelength=1.7,
                     handletextpad=0.55, labelspacing=0.45, fontsize=9)
    leg.get_frame().set_edgecolor('#C4C9CD')
    leg.get_frame().set_linewidth(0.55)


def label_panel(ax, label):
    ax.text(0.006, 1.045, label, transform=ax.transAxes,
            ha='left', va='bottom', fontsize=10.5)


def source_axis(ax):
    ax.set(xlim=(9.45, 16.55), xticks=SOURCE_COUNTS, xlabel='干扰源数量 / 个')


def deterministic_jitter(case_id: str, scale=0.19):
    value = int(hashlib.sha256(case_id.encode('utf-8')).hexdigest()[:12], 16)
    return (value / float(16**12 - 1) - 0.5) * scale * 2


def time_limits(item):
    values = [r['average_clear_time_s'] for r in item.rows if r['average_clear_time_s'] is not None]
    if not values:
        return (0, 1)
    low, high = min(values), max(values)
    padding = max((high-low)*0.085, high*0.01, 1.0)
    return (max(0, low-padding), high+padding)


def is_incomplete(row):
    """A source is missed even when the policy incorrectly claims completion."""
    return row['cleared_count'] < row['source_count']


def is_abnormal(row):
    return bool(row.get('error')) or not row.get('normal_exit', True)


class PlotRun:
    def __init__(self, directory: Path, problem: int, allow_partial: bool):
        from scripts.benchmark_balanced_search import load_run
        self.directory = directory.resolve()
        self.run, self.rows, self.summary = load_run(self.directory, allow_partial=allow_partial)
        if self.run['is_subset'] and not allow_partial:
            raise ValueError('Subset run; use --allow-partial to explicitly render a preview')
        if self.run['problem'] != problem:
            raise ValueError('Requested problem differs from the run metadata')
        if not self.rows:
            raise ValueError('Cannot plot an empty run')
        self.problem = problem
        self.allow_partial = allow_partial
        self.run_id = self.run.get('run_id', directory.name)
        if Path(self.run_id).name != self.run_id or self.run_id in ('.', '..'):
            raise ValueError('run_id must be a directory name')
        self.destination = PAPER / 'figures' / f'problem{problem}' / self.run_id
        self.groups = {n: [r for r in self.rows if r['source_count'] == n]
                       for n in SOURCE_COUNTS}
        # Independent arithmetic checks prevent accidental use of T/N instead of T/Nc.
        for row in self.rows:
            n, nc, total = row['source_count'], row['cleared_count'], row['virtual_time_s']
            if not 0 <= nc <= n or not math.isfinite(total) or total < 0:
                raise ValueError(f'Invalid result arithmetic: {row["case_id"]}')
            if not math.isclose(row['cleared_fraction'], nc/n, abs_tol=1e-10):
                raise ValueError(f'Clearance fraction mismatch: {row["case_id"]}')
            average = row['average_clear_time_s']
            if (nc == 0 and average is not None) or (nc > 0 and
                    (average is None or not math.isclose(average, total/nc, abs_tol=1e-7))):
                raise ValueError(f'Average clear time mismatch: {row["case_id"]}')
        self.statistics = self.metric_statistics()
        self.input_hashes = {name: sha256(directory/name)
                             for name in ('run.json', 'episodes.jsonl', 'summary.json')}
        self.output_records = []
        self.pdf_book = None

    def metric_statistics(self):
        out = {}
        for n, rows in self.groups.items():
            values = [r['average_clear_time_s'] for r in rows
                      if r['average_clear_time_s'] is not None]
            fractions = [r['cleared_fraction'] for r in rows]
            out[str(n)] = dict(
                cases=len(rows), cleared_sources=sum(r['cleared_count'] for r in rows),
                total_sources=sum(r['source_count'] for r in rows),
                mean_clearance_fraction=statistics.mean(fractions) if fractions else None,
                minimum_clearance_fraction=min(fractions) if fractions else None,
                maximum_clearance_fraction=max(fractions) if fractions else None,
                defined_average_clear_time_cases=len(values),
                undefined_average_clear_time_cases=len(rows)-len(values),
                mean_average_clear_time_s=statistics.mean(values) if values else None,
                median_average_clear_time_s=statistics.median(values) if values else None,
                incomplete_cases=sum(is_incomplete(r) for r in rows),
                abnormal_cases=sum(is_abnormal(r) for r in rows),
                certified_complete_cases=sum(bool(r.get('certified_full_clear')) for r in rows))
        return out

    def save(self, fig, name: str, title: str, caption: str, *, details=None, extra_sources=()):
        self.destination.mkdir(parents=True, exist_ok=True)
        record = dict(
            figure=name, title=title, caption=caption,
            problem=self.problem, run_id=self.run_id,
            algorithm_version=self.run['algorithm_version'], strategy=self.run['strategy'],
            provenance=self.run['provenance'], dataset_version=self.run['dataset_version'],
            complete=self.run['complete'], is_subset=self.run['is_subset'],
            rendered_with_allow_partial=self.allow_partial,
            cases=len(self.rows), cases_by_source_count={str(n): len(r) for n,r in self.groups.items()},
            plotted_cases=1 if name in ('case_route', 'case_progress') else len(self.rows),
            expected_cases=self.run['expected_cases'],
            source_directory=relative_name(self.directory), input_sha256=self.input_hashes,
            algorithm_source_sha256=self.run['source_sha256'],
            plotting_source_sha256={relative_name(Path(__file__)): sha256(Path(__file__)),
                                   'paper/figure_candidate_style.py': sha256(PAPER/'figure_candidate_style.py')},
            definitions=dict(clearance_fraction='Nc / N', average_clear_time_s='T / Nc; null when Nc = 0',
                             total_time='End-of-episode virtual time; includes time after the last successful clear',
                             population='Every recorded episode, including incomplete/error results; only undefined T/Nc is omitted'),
            metrics_by_source_count=self.statistics,
            details=details or {},
            extra_source_sha256={relative_name(p): sha256(p) for p in extra_sources})
        output = self.destination / name
        fig.savefig(output.with_suffix('.pdf'), bbox_inches='tight', pad_inches=0.08,
                    metadata={'Title': title, 'Subject': caption, 'Author': ''})
        fig.savefig(output.with_suffix('.svg'), bbox_inches='tight', pad_inches=0.08)
        fig.savefig(output.with_suffix('.png'), bbox_inches='tight', pad_inches=0.08, dpi=240)
        if self.pdf_book is not None:
            self.pdf_book.savefig(fig, bbox_inches='tight', pad_inches=0.08)
        plt.close(fig)
        output.with_suffix('.json').write_text(
            json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
        undefined = sum(s['undefined_average_clear_time_cases'] for s in self.statistics.values())
        incomplete = sum(s['incomplete_cases'] for s in self.statistics.values())
        abnormal = sum(s['abnormal_cases'] for s in self.statistics.values())
        scope = ('局部预览，不能代表完整数据集' if self.run['is_subset'] or not self.run['complete']
                 else '完整均衡集运行')
        text = (f'# {title}\n\n{caption}\n\n'
                f'本地自建样例；非官方正式测试。{scope}。问题{self.problem}，'
                f'运行 `{self.run_id}`，算法 `{self.run["algorithm_version"]}`。\n\n'
                f'本次运行已记录 {len(self.rows)} 例；各源数样例量：'
                + '，'.join(f'{n}源 {len(r)} 例' for n,r in self.groups.items()) + '。\n\n'
                f'清除比例为 Nc/N，平均定位清除时间为结束总虚拟时间 T/Nc。'
                f'所有已记录结果均纳入统计，其中未全清 {incomplete} 例，异常退出 {abnormal} 例；'
                f'Nc=0 导致时间指标无定义的 {undefined} 例仅从时间分布中排除，仍保留在清除比例统计。'
                f'结束总时间包含最后一次清除后的覆盖确认等动作。\n\n'
                f'输入与代码指纹、逐源数统计及图形定义见同名 JSON。\n')
        output.with_suffix('.caption.md').write_text(text, encoding='utf-8')
        self.output_records.append(dict(figure=name, title=title,
                                       files=[relative_name(output.with_suffix(ext))
                                              for ext in ('.pdf', '.svg', '.png', '.json', '.caption.md')]))

    def status_markers(self, ax):
        missed = [r for r in self.rows if is_incomplete(r) and r['average_clear_time_s'] is not None]
        abnormal = [r for r in self.rows if is_abnormal(r) and r['average_clear_time_s'] is not None]
        handles, labels = [], []
        for rows, marker, color, label in ((missed, 'x', COLORS['red'], '未全清'),
                                           (abnormal, 's', COLORS['ink'], '异常退出')):
            if not rows:
                continue
            x = [r['source_count'] + deterministic_jitter(r['case_id']) for r in rows]
            kw = dict(s=23, marker=marker, linewidths=0.85, zorder=5)
            if marker == 'x':
                kw['color'] = color
            else:
                kw.update(facecolors='none', edgecolors=color)
            ax.scatter(x, [r['average_clear_time_s'] for r in rows], **kw)
            handles.append(Line2D([], [], marker=marker, color=color, ls='none',
                                  markersize=5, markerfacecolor='none'))
            labels.append(label)
        return handles, labels


def time_boxes(ax, item: PlotRun, *, colored=False):
    present = [(n, [r['average_clear_time_s'] for r in rows
                    if r['average_clear_time_s'] is not None])
               for n, rows in item.groups.items()]
    present = [(n, values) for n, values in present if values]
    if not present:
        return
    boxes = ax.boxplot([v for _,v in present], positions=[n for n,_ in present],
                       widths=0.52, patch_artist=True, manage_ticks=False,
                       showmeans=True,
                       boxprops=dict(edgecolor='#7D8A93', linewidth=0.8),
                       whiskerprops=dict(color='#82909A', linewidth=0.8),
                       capprops=dict(color='#82909A', linewidth=0.8),
                       medianprops=dict(color=COLORS['ink'], linewidth=1.25),
                       meanprops=dict(marker='D', markersize=4, markerfacecolor='white',
                                      markeredgecolor=COLORS['blue'], markeredgewidth=0.8),
                       flierprops=dict(marker='o', markersize=2.5, alpha=0.4,
                                       markerfacecolor=COLORS['gray'], markeredgewidth=0))
    for patch, (n, _) in zip(boxes['boxes'], present):
        patch.set_facecolor(GROUP_COLORS[n-10] if colored else '#B2C7D4')
        patch.set_alpha(0.8)


def plot_two_metrics(item: PlotRun):
    has_time = any(r['average_clear_time_s'] is not None for r in item.rows)
    if has_time:
        fig = plt.figure(figsize=(7.1, 4.75))
        grid = fig.add_gridspec(2, 1, height_ratios=[0.82, 2.35],
                               left=0.125, right=0.982, top=0.947, bottom=0.185, hspace=0.5)
        rate = fig.add_subplot(grid[0])
        duration = fig.add_subplot(grid[1])
    else:
        fig, rate = plt.subplots(figsize=(7.1, 2.3))
        fig.subplots_adjust(left=0.125, right=0.982, top=0.94, bottom=0.25)
    ns = [n for n in SOURCE_COUNTS if item.groups[n]]
    means = [100*item.statistics[str(n)]['mean_clearance_fraction'] for n in ns]
    low = [100*item.statistics[str(n)]['minimum_clearance_fraction'] for n in ns]
    high = [100*item.statistics[str(n)]['maximum_clearance_fraction'] for n in ns]
    rate.errorbar(ns, means, yerr=[np.maximum(0, np.subtract(means, low)),
                                 np.maximum(0, np.subtract(high, means))],
                  fmt='o-', color=COLORS['blue'], ecolor='#9FB7C7',
                  capsize=3, linewidth=1.6, elinewidth=0.9, markersize=4.8,
                  markeredgecolor='white', markeredgewidth=0.6)
    source_axis(rate)
    rate.set(ylabel='清除比例 / %', ylim=(-3, 107), yticks=(0, 50, 100))
    tidy(rate)
    if has_time:
        rate.set_xlabel('')
        label_panel(rate, '(a)')
        time_boxes(duration, item)
        source_axis(duration)
        duration.set_ylabel(METRIC_TIME)
        duration.set_ylim(*time_limits(item))
        tidy(duration)
        label_panel(duration, '(b)')
        handles = [Line2D([], [], marker='D', ls='none', markerfacecolor='white',
                          markeredgecolor=COLORS['blue'], markersize=5)]
        labels = ['均值']
        status_handles, status_labels = item.status_markers(duration)
        outside_legend(fig, handles + status_handles, labels + status_labels, ncol=3, y=0.025)
    caption = ('按干扰源数量分别统计两项题面指标。上图点线为单例清除比例的均值，误差线为最小值至最大值；'
               '下图为平均定位清除时间的箱线图，箱体为四分位范围，中线为中位数，须线延伸至1.5倍四分位距范围，'
               '空心菱形为均值。两个面板均只含本次 solve 方案。' if has_time else
               '按干扰源数量统计单例清除比例的均值，误差线为最小值至最大值。'
               '本次所有样本的Nc均为0，平均定位清除时间全部无定义，因此省略时间面板。')
    item.save(fig, 'two_metrics', f'问题{item.problem}的两项指标', caption,
              details={'clearance_interval': 'observed minimum to maximum; not a confidence interval',
                       'boxplot_whiskers': '1.5 IQR', 'mean_marker': 'hollow diamond',
                       'time_panel_omitted': not has_time})


def plot_time_distribution(item: PlotRun):
    fig, ax = plt.subplots(figsize=(7.1, 4.15))
    fig.subplots_adjust(left=0.125, right=0.98, top=0.975, bottom=0.225)
    density_groups, sparse_groups, constant_groups = [], [], []
    for n, rows in item.groups.items():
        values = [r['average_clear_time_s'] for r in rows if r['average_clear_time_s'] is not None]
        if not values:
            continue
        color = GROUP_COLORS[n-10]
        if len(values) >= 5 and max(values)-min(values) > 1e-9:
            parts = ax.violinplot(values, positions=[n], widths=0.79,
                                  showextrema=False, bw_method='scott', points=160)
            for body in parts['bodies']:
                body.set(facecolor=color, edgecolor='#7F8C93', linewidth=0.6, alpha=0.67)
            q1, median, q3 = np.quantile(values, [0.25, 0.5, 0.75])
            ax.plot([n,n], [q1,q3], color=COLORS['ink'], linewidth=2.5, solid_capstyle='round')
            ax.scatter([n], [median], s=20, c='white', edgecolors=COLORS['ink'], linewidths=0.6, zorder=4)
            density_groups.append(n)
        else:
            ax.scatter([n+deterministic_jitter(r['case_id']) for r in rows if r['average_clear_time_s'] is not None],
                       values, s=29, color=color, edgecolors='white', linewidths=0.7, zorder=3)
            if max(values)-min(values) <= 1e-9:
                constant_groups.append(n)
            else:
                sparse_groups.append(n)
    handles, labels = item.status_markers(ax)
    if density_groups:
        handles.insert(0, Line2D([], [], color=COLORS['ink'], linewidth=2.5))
        labels.insert(0, '四分位范围')
        handles.insert(1, Line2D([], [], marker='o', ls='none', markersize=5,
                                markerfacecolor='white', markeredgecolor=COLORS['ink']))
        labels.insert(1, '中位数')
    source_axis(ax)
    ax.set_ylabel(METRIC_TIME)
    ax.set_ylim(*time_limits(item))
    tidy(ax)
    if handles:
        outside_legend(fig, handles, labels, ncol=4, y=0.02)
    else:
        fig.subplots_adjust(bottom=0.17)
    item.save(fig, 'time_distribution', f'问题{item.problem}的平均定位清除时间分布',
              '按源数量绘制平均定位清除时间的小提琴分布，宽度表示组内核密度；各组归一化至相同最大宽度。'
              '每组不足5个有效样本或取值恒定时，使用实际样本散点，不拟合密度。'
              '所有有定义的时间指标均纳入，包括未全清与异常退出结果。',
              details={'density_groups': density_groups, 'sparse_scatter_groups': sparse_groups,
                       'constant_scatter_groups': constant_groups,
                       'kde': 'Gaussian, Scott bandwidth, 160 support points, equal maximum width'})


def plot_time_components(item: PlotRun):
    components = (
        ('移动', COLORS['blue'], lambda r: r['movement_m']/5),
        ('测向', COLORS['green'], lambda r: r['measure']*5),
        ('切换频道', COLORS['purple'], lambda r: r['switch']),
        ('成功清除', COLORS['peach'], lambda r: (r['clear']-r['failed_clear'])*5),
        ('失败清除', COLORS['gray'], lambda r: r['failed_clear']*3))
    for row in item.rows:
        if not math.isclose(sum(f(row) for _,_,f in components), row['virtual_time_s'], abs_tol=1e-5):
            raise ValueError(f'Time components do not sum to total: {row["case_id"]}')
    fig, ax = plt.subplots(figsize=(7.1, 4.2))
    fig.subplots_adjust(left=0.12, right=0.985, top=0.975, bottom=0.215)
    ns = [n for n in SOURCE_COUNTS if item.groups[n]]
    bottom = np.zeros(len(ns))
    component_values = {}
    for label, color, get in components:
        values = [statistics.mean(get(r) for r in item.groups[n]) for n in ns]
        ax.bar(ns, values, width=0.61, bottom=bottom, color=color, edgecolor='white', linewidth=0.45)
        bottom += values
        component_values[label] = dict(zip(map(str, ns), values))
    source_axis(ax)
    ax.set_ylabel('平均总耗时 / s')
    ax.set_ylim(bottom=0)
    tidy(ax)
    outside_legend(fig, [Patch(facecolor=c, edgecolor='none') for _,c,_ in components],
                   [name for name,_,_ in components], ncol=5, y=0.02)
    item.save(fig, 'time_components', f'问题{item.problem}的耗时构成',
              '按干扰源数量统计每局结束总虚拟时间的平均分解。移动距离除以5 m/s，'
              '测向每次5 s、切换频道每次1 s、成功清除每次5 s、失败清除每次3 s。'
              '各分量先逐局核对总和，再对该源数全部结果取均值；包括未全清和异常退出结果。',
              details={'mean_component_seconds_by_source_count': component_values})


def plot_time_ecdf(item: PlotRun):
    fig, ax = plt.subplots(figsize=(7.1, 4.35))
    fig.subplots_adjust(left=0.12, right=0.98, top=0.975, bottom=0.265)
    handles, labels = [], []
    n_defined = {}
    low, high = time_limits(item)
    patterns = ('-', '--', '-.', ':', '-', '--', '-.')
    for n, color, ls in zip(SOURCE_COUNTS, GROUP_COLORS, patterns):
        rows = sorted((r for r in item.groups[n] if r['average_clear_time_s'] is not None),
                      key=lambda r: r['average_clear_time_s'])
        n_defined[str(n)] = len(rows)
        if not rows:
            continue
        times = [r['average_clear_time_s'] for r in rows]
        fractions = np.arange(1, len(rows)+1)/len(rows)
        ax.step([low]+times+[high], [0]+list(fractions)+[1], where='post',
                color=color, linestyle=ls, linewidth=1.6)
        missed = [(r['average_clear_time_s'], fractions[i]) for i,r in enumerate(rows) if is_incomplete(r)]
        if missed:
            ax.scatter(*zip(*missed), marker='x', s=19, c=COLORS['red'], linewidths=0.8, zorder=5)
        handles.append(Line2D([], [], color=color, ls=ls, linewidth=1.6))
        labels.append(f'{n}源')
    if any(is_incomplete(r) and r['average_clear_time_s'] is not None for r in item.rows):
        handles.append(Line2D([], [], color=COLORS['red'], marker='x', ls='none', markersize=5))
        labels.append('未全清')
    ax.set(xlabel=METRIC_TIME, ylabel='累计比例 / %', ylim=(-0.025, 1.04))
    ax.set_xlim(low, high)
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=1, symbol=''))
    tidy(ax, 'both')
    outside_legend(fig, handles, labels, ncol=4, y=0.02)
    item.save(fig, 'time_ecdf', f'问题{item.problem}的平均定位清除时间累积分布',
              '各源数组分别使用所有有定义的平均定位清除时间构造经验累积分布函数，'
              '纵轴为该源数组内不超过横轴时间的样本比例。每条曲线的分母为该组有定义的样本量，'
              '未全清结果用叉号标记。Nc=0样本的时间指标不定义，具体数量记录在图外统计中。',
              details={'defined_cases_by_source_count': n_defined, 'ecdf': 'right-continuous empirical CDF'})


def load_trace(item: PlotRun, source_count: int, *, required=False):
    folder = item.directory/'trace_samples'/f'n{source_count}'
    if not folder.exists():
        if required:
            raise ValueError(f'Trace sample is unavailable: {folder}')
        return None
    paths = [folder/'case.json', folder/'result.json', folder/'events.jsonl']
    case, result = json_read(paths[0]), json_read(paths[1])
    events = [json.loads(line) for line in paths[2].read_text(encoding='utf-8').splitlines() if line.strip()]
    by_id = {r['case_id']: r for r in item.rows}
    if case['case_id'] not in by_id or result['case_id'] != case['case_id']:
        raise ValueError('Trace case is not present in the validated run')
    row = by_id[case['case_id']]
    case_digest = hashlib.sha256(
        json.dumps(case, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if case_digest != row['case_sha256']:
        raise ValueError('Trace case fingerprint differs from the validated episode')
    for key in ('algorithm_version', 'source_count', 'cleared_count', 'virtual_time_s',
                'movement_m', 'measure', 'clear', 'failed_clear', 'switch'):
        if result[key] != row[key]:
            raise ValueError(f'Trace result mismatch: {key}')
    if len(case['sources']) != source_count or row['source_count'] != source_count:
        raise ValueError('Trace source count mismatch')
    if case['problem'] != item.problem or case['provenance'] != item.run['provenance']:
        raise ValueError('Trace problem/provenance mismatch')
    position, current_channel, total, movement = (0., 0.), 1, 0., 0.
    counts = Counter()
    route, successes = [position], []
    source_map = {s['channel']: s for s in case['sources']}
    for event in events:
        response = event['response']
        if response.get('accepted') is not True:
            raise ValueError('Rejected trace action cannot be treated as accepted')
        point = tuple(event['position'])
        distance = math.dist(position, point)
        movement += distance
        total += distance/5
        if distance > 1e-8:
            route.append(point)
        position = point
        action, channel = event['action'], event['channel']
        counts[action] += 1
        if action == 'measure':
            switched = int(channel != current_channel)
            counts['switch'] += switched
            current_channel = channel
            total += 5+switched
        elif action == 'clear':
            success = response['clear_result'] == 'success'
            total += 5 if success else 3
            counts['failed_clear'] += int(not success)
            if success:
                source = source_map[channel]
                if math.dist(point, (source['x'], source['y'])) > 20+1e-8:
                    raise ValueError('Trace clear is outside the accepted radius')
                successes.append(event)
        else:
            raise ValueError(f'Unexpected trace action: {action}')
        if not math.isclose(total, response['virtual_time_s'], abs_tol=1.1e-6):
            raise ValueError('Trace virtual-time accounting mismatch')
    for key in ('measure', 'clear', 'failed_clear', 'switch'):
        if counts[key] != row[key]:
            raise ValueError(f'Trace action count mismatch: {key}')
    if (len({e['channel'] for e in successes}) != len(successes)
            or len(successes) != row['cleared_count']
            or not math.isclose(movement, row['movement_m'], abs_tol=1e-7)
            or not math.isclose(total, row['virtual_time_s'], abs_tol=1e-7)):
        raise ValueError('Trace final totals do not match the episode')
    return dict(case=case, row=row, events=events, successes=successes, route=route,
                source_map=source_map, paths=paths)


def plot_case_route(item: PlotRun, trace):
    fig, ax = plt.subplots(figsize=(5.7, 5.4))
    fig.subplots_adjust(left=0.125, right=0.975, top=0.985, bottom=0.185)
    route = np.array(trace['route'])/1000
    sources = trace['case']['sources']
    ax.add_patch(Circle((0,0), 1.8, facecolor='#F7F8F8', edgecolor='#AEB6BC',
                        linewidth=0.85, linestyle=(0,(4,3)), zorder=0))
    ax.plot(route[:,0], route[:,1], color=COLORS['blue'], linewidth=1.05, alpha=0.85, zorder=2)
    points = sorted({tuple(e['position']) for e in trace['events'] if e['action']=='measure'})
    if points:
        points = np.array(points)/1000
        ax.scatter(points[:,0], points[:,1], color=COLORS['blue'], s=8,
                   edgecolors='white', linewidths=0.25, alpha=0.8, zorder=3)
    for directional in (False, True):
        subset = [s for s in sources if (s.get('orientation_deg') is not None) == directional]
        if not subset:
            continue
        ax.scatter([s['x']/1000 for s in subset], [s['y']/1000 for s in subset],
                   s=33, marker='^' if directional else 'o', c=COLORS['peach'],
                   edgecolors='white', linewidths=0.65, zorder=5)
        if directional:
            for s in subset:
                a = math.radians(s['orientation_deg'])
                ax.annotate('', xy=(s['x']/1000+0.16*math.cos(a), s['y']/1000+0.16*math.sin(a)),
                            xytext=(s['x']/1000, s['y']/1000),
                            arrowprops=dict(arrowstyle='-|>', color='#AD8168', linewidth=0.9,
                                            mutation_scale=7), zorder=5)
    cleared = {e['channel'] for e in trace['successes']}
    missed = [s for s in sources if s['channel'] not in cleared]
    if missed:
        ax.scatter([s['x']/1000 for s in missed], [s['y']/1000 for s in missed],
                   s=70, marker='x', color=COLORS['red'], linewidths=1.0, zorder=6)
    ax.scatter(0, 0, s=34, marker='D', color=COLORS['ink'], edgecolors='white', linewidths=0.6, zorder=7)
    ax.scatter(*route[-1], s=54, marker='s', facecolors='none', edgecolors=COLORS['ink'], linewidths=0.9, zorder=7)
    limit = max(2.05, float(np.max(np.abs(route)))+0.16)
    ax.set(xlim=(-limit,limit), ylim=(-limit,limit), aspect='equal',
           xlabel='横坐标 / km', ylabel='纵坐标 / km')
    ax.xaxis.set_major_locator(MultipleLocator(1) if limit < 2.5 else MaxNLocator(nbins=5))
    ax.yaxis.set_major_locator(MultipleLocator(1) if limit < 2.5 else MaxNLocator(nbins=5))
    tidy(ax, 'both')
    handles = [Line2D([], [], color=COLORS['blue'], marker='o', markersize=3, linewidth=1)]
    labels = ['轨迹及测量点']
    if any(s.get('orientation_deg') is None for s in sources):
        handles.append(Line2D([], [], color=COLORS['peach'], marker='o', ls='none', markersize=5))
        labels.append('全向源')
    if any(s.get('orientation_deg') is not None for s in sources):
        handles.append(Line2D([], [], color=COLORS['peach'], marker='^', ls='none', markersize=5))
        labels.append('定向源')
    handles.extend([Line2D([], [], color=COLORS['ink'], marker='D', ls='none', markersize=4),
                    Line2D([], [], color=COLORS['ink'], marker='s', markerfacecolor='none', ls='none', markersize=5)])
    labels.extend(['起点', '结束位置'])
    if missed:
        handles.append(Line2D([], [], color=COLORS['red'], marker='x', ls='none', markersize=5))
        labels.append('未清除源')
    outside_legend(fig, handles, labels, ncol=3, y=0.016)
    row = trace['row']
    item.save(fig, 'case_route', f'问题{item.problem}的样例搜索轨迹',
              '展示预先固定源数组内第一个样例的实际动作轨迹。虚线圆为半径1800 m的源位置约束，'
              '检测点允许位于圆外；源真值仅供事后核验与展示。三角形表示定向源，箭头表示发射方向。'
              '该图为单例执行过程，不代表批量结果。',
              details={'case_id': row['case_id'], 'source_count': row['source_count'],
                       'cleared_count': row['cleared_count'], 'cleared_fraction': row['cleared_fraction'],
                       'virtual_time_s': row['virtual_time_s'], 'average_clear_time_s': row['average_clear_time_s'],
                       'selection': 'first stored episode of the requested source count, independent of performance'},
              extra_sources=trace['paths'])


def plot_case_progress(item: PlotRun, trace):
    fig, ax = plt.subplots(figsize=(7.1, 3.75))
    fig.subplots_adjust(left=0.11, right=0.98, top=0.975, bottom=0.265)
    row = trace['row']
    times = [e['response']['virtual_time_s'] for e in trace['successes']]
    fractions = [100*i/row['source_count'] for i in range(1,len(times)+1)]
    ax.step([0]+times+[row['virtual_time_s']], [0]+fractions+[100*row['cleared_fraction']],
            where='post', color=COLORS['blue'], linewidth=1.7)
    ax.scatter(times, fractions, s=23, c=COLORS['blue'], edgecolors='white', linewidths=0.5, zorder=4)
    ax.scatter(row['virtual_time_s'], 100*row['cleared_fraction'], s=37,
               marker='s', facecolors='white', edgecolors=COLORS['ink'], linewidths=0.9, zorder=5)
    ax.set(xlabel='虚拟时间 / s', ylabel='累计清除比例 / %', ylim=(-3,107), yticks=(0,25,50,75,100))
    ax.set_xlim(left=0, right=max(1, row['virtual_time_s'])*1.025)
    tidy(ax, 'both')
    outside_legend(fig,
                   [Line2D([], [], color=COLORS['blue'], marker='o', markersize=4, linewidth=1.5),
                    Line2D([], [], color=COLORS['ink'], marker='s', markerfacecolor='white', ls='none', markersize=5)],
                   ['成功清除', '任务结束'], ncol=2, y=0.022)
    item.save(fig, 'case_progress', f'问题{item.problem}的样例清除进度',
              '与同次输出的轨迹图使用同一固定样例，按每次成功清除的实际时刻累计清除比例，'
              '空心方形标出本局结束时刻。末次清除之后的时间仍计入最终平均定位清除时间。',
              details={'case_id': row['case_id'], 'source_count': row['source_count'],
                       'success_times_s': times, 'virtual_time_s': row['virtual_time_s'],
                       'average_clear_time_s': row['average_clear_time_s'],
                       'cleared_fraction': row['cleared_fraction'],
                       'after_last_clear_s': row['virtual_time_s']-times[-1] if times else None},
              extra_sources=trace['paths'])


def main(argv=None):
    parser = argparse.ArgumentParser(description='按问题单独绘制当前 solve 方案的均衡本地样例结果')
    problem = parser.add_mutually_exclusive_group(required=True)
    problem.add_argument('--problem', type=int, choices=(3,4))
    problem.add_argument('--problem3', dest='problem', action='store_const', const=3)
    problem.add_argument('--problem4', dest='problem', action='store_const', const=4)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--run-id', help='problemN/results/balanced 下的运行目录名')
    inputs.add_argument('--input-dir', type=Path, help='运行目录；相对路径以仓库根目录为基准')
    parser.add_argument('--allow-partial', action='store_true', help='允许局部预览，范围写入图外元数据')
    parser.add_argument('--figures', nargs='+', choices=FIGURE_NAMES, default=list(FIGURE_NAMES))
    parser.add_argument('--sample-source-count', type=int, choices=SOURCE_COUNTS,
                        help='样例图使用的源数；默认13，缺少其轨迹时跳过样例图')
    args = parser.parse_args(argv)
    if args.run_id:
        if Path(args.run_id).name != args.run_id or args.run_id in ('.','..'):
            parser.error('--run-id must be a directory name')
        directory = ROOT/f'problem{args.problem}'/'results'/'balanced'/args.run_id
    else:
        directory = args.input_dir if args.input_dir.is_absolute() else ROOT/args.input_dir
    item = PlotRun(directory, args.problem, args.allow_partial)
    setup()
    plt.rcParams.update({'axes.labelsize': 10.5, 'font.size': 10,
                         'legend.fontsize': 9, 'figure.dpi': 110})
    operations = {'two_metrics': plot_two_metrics, 'time_distribution': plot_time_distribution,
                  'time_components': plot_time_components, 'time_ecdf': plot_time_ecdf}
    skipped = []
    skipped_undefined_time = []
    has_time = any(r['average_clear_time_s'] is not None for r in item.rows)
    item.destination.mkdir(parents=True, exist_ok=True)
    book_path = item.destination/'figures.pdf'
    book_temporary = item.destination/'figures.tmp.pdf'
    with PdfPages(book_temporary, metadata={'Title': f'问题{item.problem}结果图',
                  'Subject': 'One figure per page; evidence and captions are stored separately',
                  'Author': ''}) as book:
        item.pdf_book = book
        for name in args.figures:
            if name in ('time_distribution', 'time_ecdf') and not has_time:
                skipped_undefined_time.append(name)
                continue
            if name in operations:
                operations[name](item)
        requested_cases = set(args.figures) & {'case_route','case_progress'}
        if requested_cases:
            trace = load_trace(item, args.sample_source_count or 13,
                               required=args.sample_source_count is not None)
            if trace:
                if 'case_route' in requested_cases:
                    plot_case_route(item, trace)
                if 'case_progress' in requested_cases:
                    plot_case_progress(item, trace)
            else:
                skipped.extend(sorted(requested_cases))
        book_pages = book.get_pagecount()
    item.pdf_book = None
    if book_pages:
        book_temporary.replace(book_path)
        book_record = dict(path=relative_name(book_path), sha256=sha256(book_path), pages=book_pages)
    else:
        book_record = None
    catalog = dict(problem=item.problem, run_id=item.run_id, complete=item.run['complete'],
                   is_subset=item.run['is_subset'], cases=len(item.rows), figures=item.output_records,
                   figure_book=book_record,
                   skipped_missing_trace=skipped, skipped_undefined_time=skipped_undefined_time)
    item.destination.mkdir(parents=True, exist_ok=True)
    (item.destination/'catalog.json').write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(output=str(item.destination), figures=len(item.output_records),
                          cases=len(item.rows), skipped=skipped+skipped_undefined_time), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
