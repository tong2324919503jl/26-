"""Plot existing local P3/P4 cases; never execute a policy or contact the platform."""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Patch

from figure_candidate_style import COLORS, ROOT, legend, read, save, setup, tidy


def load_case(problem: int) -> dict:
    prefix = f'problem{problem}'
    case = read(f'{prefix}/examples/demo_case.json')
    result = read(f'{prefix}/results/demo_result.json')
    trace_path = ROOT / prefix / 'results' / 'demo_trace.jsonl'
    events = [json.loads(line) for line in trace_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    assert case['case_id'] == result['case_id']
    assert case['provenance'] == 'self_constructed_not_official'
    assert result['algorithm_version'] == f'problem{problem}_v4'
    assert case['family'] == result['family'] == 'outward'
    assert result['error'] is None
    source_by_channel = {s['channel']: s for s in case['sources']}
    position, current_channel = (0., 0.), 1
    movement, total = 0., 0.
    successes = []
    route = [position]
    counts = dict(measure=0, clear=0, failed_clear=0, switch=0, no_signal=0)
    for event in events:
        response = event['response']
        assert response['accepted'] is True
        next_position = tuple(event['position'])
        distance = math.dist(position, next_position)
        movement += distance
        total += distance / 5.
        if distance > 1e-8:
            route.append(next_position)
        position = next_position
        channel = event['channel']
        counts[event['action']] += 1
        if event['action'] == 'measure':
            switched = channel != current_channel
            current_channel = channel
            counts['switch'] += int(switched)
            counts['no_signal'] += int(response['measure_result'] == 'no_signal')
            total += 5 + int(switched)
        elif event['action'] == 'clear':
            success = response['clear_result'] == 'success'
            total += 5 if success else 3
            counts['failed_clear'] += int(not success)
            if success:
                source = source_by_channel[channel]
                assert math.dist(position, (source['x'], source['y'])) <= 20 + 1e-8
                successes.append(event)
        else:
            raise AssertionError(f'Unexpected event action: {event["action"]}')
        assert math.isclose(total, response['virtual_time_s'], abs_tol=1.1e-6)
    assert len(events) == result['actions']
    assert len(successes) == len({e['channel'] for e in successes}) == result['cleared_count']
    assert len(case['sources']) == result['source_count']
    for key, value in counts.items():
        assert value == result[key], (key, value, result[key])
    assert math.isclose(movement, result['movement_m'], abs_tol=1e-7)
    assert math.isclose(total, result['virtual_time_s'], abs_tol=1e-7)
    assert math.isclose(successes[-1]['response']['virtual_time_s'], result['last_clear_time_s'], abs_tol=1.1e-6)
    assert math.isclose(len(successes) / len(case['sources']), result['cleared_fraction'])
    assert math.isclose(total / len(successes), result['average_clear_time_s'])
    return dict(problem=problem, case=case, result=result, events=events,
                successes=successes, route=route, source_by_channel=source_by_channel,
                color=COLORS['blue'] if problem == 3 else COLORS['green'])


def sources(cases):
    files = []
    for item in cases:
        prefix = f'problem{item["problem"]}'
        files.extend([f'{prefix}/examples/demo_case.json', f'{prefix}/results/demo_result.json',
                      f'{prefix}/results/demo_trace.jsonl'])
    return files + ['problem3/simulator.py']


def provenance(cases):
    return dict(
        evidence='仅使用已存本地自建案例与动作记录；非正式测试，非批量平均。',
        ground_truth='源位置和源数仅供事后绘图与核验，策略不读取真值。',
        timing='按相邻动作距离/5、测量5秒、换频道1秒、成功清除5秒、失败清除3秒逐条核对。总时间与结果文件一致。动作日志不含enter/exit行；本地exit不增加虚拟时间。',
        checks=[dict(case_id=c['case']['case_id'], algorithm_version=c['result']['algorithm_version'],
                     source_count=c['result']['source_count'], cleared_count=c['result']['cleared_count'],
                     virtual_time_s=c['result']['virtual_time_s'],
                     average_clear_time_s=c['result']['average_clear_time_s'],
                     after_last_clear_s=c['result']['virtual_time_s']-c['result']['last_clear_time_s'],
                     verified_action_count=len(c['events'])) for c in cases])


def route_candidates(cases):
    fig = plt.figure(figsize=(8.0, 5.30))
    grid = fig.add_gridspec(2, 2, height_ratios=[3.5, 1.12], hspace=.29, wspace=.27,
                           left=.085, right=.975, top=.93, bottom=.165)
    for col, item in enumerate(cases):
        ax = fig.add_subplot(grid[0, col])
        result, route, color = item['result'], item['route'], item['color']
        ax.add_patch(Circle((0, 0), 1.8, facecolor='#F7F8F8', edgecolor='#B8BEC2',
                            linewidth=.8, linestyle=(0, (4, 3)), zorder=0))
        ax.plot([p[0]/1000 for p in route], [p[1]/1000 for p in route], color=color,
                linewidth=1.35, alpha=.93, zorder=2)
        measure_points = sorted({tuple(e['position']) for e in item['events'] if e['action']=='measure'})
        ax.scatter([p[0]/1000 for p in measure_points], [p[1]/1000 for p in measure_points],
                   s=8, c=color, alpha=.8, edgecolor='white', linewidth=.2, zorder=3)
        for rank, event in enumerate(item['successes'], start=1):
            source = item['source_by_channel'][event['channel']]
            x, y = source['x']/1000, source['y']/1000
            ax.scatter(x, y, s=30, facecolor=COLORS['peach'], edgecolor='white', linewidth=.65, zorder=5)
            # All sources belong to an outer-rim case: radial labels avoid the route.
            norm = math.hypot(x, y)
            offset = .22 if rank == len(item['successes']) else .17
            tx, ty = x + offset*x/norm, y + offset*y/norm
            ax.text(tx, ty, str(rank), fontsize=8.7, ha='center', va='center', color=COLORS['ink'],
                    bbox=dict(boxstyle='circle,pad=.08', fc='white', ec='none', alpha=.92), zorder=6)
        ax.scatter(0, 0, marker='D', s=33, facecolor=COLORS['ink'], edgecolor='white', linewidth=.65, zorder=6)
        # The open square remains legible where the final position is close to a source.
        ax.scatter(route[-1][0]/1000, route[-1][1]/1000, marker='s', s=67,
                   facecolor='none', edgecolor=COLORS['ink'], linewidth=.95, zorder=7)
        ax.set(xlim=(-2.25, 2.25), ylim=(-2.2, 2.2), aspect='equal',
               xticks=[-2, -1, 0, 1, 2], yticks=[-2, -1, 0, 1, 2],
               xlabel='横坐标 / 千米', ylabel='纵坐标 / 千米')
        tidy(ax, 'both')
        ax.set_title(f'（{"a" if col == 0 else "b"}）问题{"三" if col == 0 else "四"}：外缘本地示例', pad=8)
        info = fig.add_subplot(grid[1, col])
        info.set_axis_off()
        rows = [
            ('清除比例', f'{result["cleared_fraction"]:.0%}（{result["cleared_count"]}/{result["source_count"]}）'),
            ('平均清除时间', f'{result["average_clear_time_s"]:.2f} 秒/源'),
            ('结束总虚拟时间', f'{result["virtual_time_s"]:.2f} 秒'),
        ]
        for row, (label, value) in enumerate(rows):
            y = .88 - row*.36
            info.text(.03, y, label, transform=info.transAxes, ha='left', va='center', fontsize=9.5)
            info.text(.97, y, value, transform=info.transAxes, ha='right', va='center', fontsize=10.2,
                      color=color if row < 2 else COLORS['ink'])
            if row < 2:
                info.plot([.03, .97], [y-.17, y-.17], transform=info.transAxes, color=COLORS['grid'], lw=.6)
    handles = [Line2D([], [], color=COLORS['blue'], lw=1.4, marker='o', markersize=3),
               Line2D([], [], color=COLORS['peach'], marker='o', linestyle='none', markersize=5),
               Line2D([], [], color=COLORS['ink'], marker='D', linestyle='none', markersize=4),
               Line2D([], [], color=COLORS['ink'], marker='s', markerfacecolor='white', linestyle='none', markersize=5)]
    legend(fig, handles, ['轨迹及测量位置', '源真值及清除顺序', '起点', '结束位置'], y=.035, ncol=4,
           fontsize=8.8)
    fig.text(.5, .012, '本地示例，非正式测试；虚线圆约束源位置，数字表示清除次序，真值仅作事后展示。',
             ha='center', va='bottom', fontsize=8.6, color='#697178')
    save(fig, '06_case_routes', '本地外缘示例的搜索轨迹与两项指标',
         '第三、四问已存本地外缘示例的执行轨迹。底图叠加事后获知的源位置，数字为实际成功清除次序，虚线为半径1800米的源位置约束圆，机器人检测点可在圆外。两例清除比例均为100%，平均清除时间分别为252.36和527.80秒/源。时间按结束总虚拟时间除以实际清除数计算，包含最后清除后的覆盖确认。仅用于阐释案例，不代表批量平均或正式成绩。',
         sources(cases), recommendation='适合案例分析中的执行过程图；与07配套时可减少本图指标重复。',
         notes=provenance(cases))


def progress_candidates(cases):
    fig = plt.figure(figsize=(8.0, 5.45))
    grid = fig.add_gridspec(2, 1, height_ratios=[2.5, 1.25], hspace=.66,
                           left=.125, right=.97, top=.92, bottom=.18)
    ax = fig.add_subplot(grid[0])
    for item in cases:
        result, color = item['result'], item['color']
        times = [0] + [e['response']['virtual_time_s'] for e in item['successes']] + [result['virtual_time_s']]
        fractions = [0] + [100*i/result['source_count'] for i in range(1, result['cleared_count']+1)] + [100*result['cleared_fraction']]
        ax.step(times, fractions, where='post', color=color, lw=1.9, zorder=3)
        ax.scatter(times[1:-1], fractions[1:-1], s=12, color=color, edgecolor='white', linewidth=.3, zorder=4)
        ax.scatter(result['virtual_time_s'], 100*result['cleared_fraction'], s=45, marker='s',
                   facecolor='white', edgecolor=color, linewidth=1.1, zorder=5)
    ax.annotate('问题三：14/14\n结束 3533.04 秒', xy=(3533.035762,100), xytext=(3400, 64),
                fontsize=9.0, color=COLORS['blue'], ha='center', va='center',
                arrowprops=dict(arrowstyle='-', color=COLORS['blue'], lw=.7,
                                connectionstyle='angle,angleA=90,angleB=0,rad=0'))
    ax.annotate('问题四：11/11\n末次清除 5713.07 秒\n结束 5805.78 秒',
                xy=(5805.783884,100), xytext=(4620, 34), fontsize=9.0,
                color='#657D6C', ha='center', va='center',
                arrowprops=dict(arrowstyle='-', color=COLORS['green'], lw=.7,
                                connectionstyle='angle,angleA=0,angleB=90,rad=0'))
    ax.set(xlim=(0, 6150), ylim=(0, 106), xticks=list(range(0,6001,1000)),
           yticks=[0,25,50,75,100], ylabel='累计清除比例 / %', xlabel='虚拟时间 / 秒')
    ax.set_title('（a）清除进度：按每次成功清除时刻累积', pad=8)
    tidy(ax, 'both')

    bar = fig.add_subplot(grid[1])
    for row, item in enumerate(cases):
        result, color = item['result'], item['color']
        total, n = result['virtual_time_s'], result['cleared_count']
        last, confirmation = result['last_clear_time_s'], total-result['last_clear_time_s']
        core, tail = last/n, confirmation/n
        bar.barh(row, core, height=.47, color=color, edgecolor='white', linewidth=.7)
        if tail > 1e-5:
            bar.barh(row, tail, left=core, height=.47, color='#DCE1E4',
                     edgecolor='#8E979E', linewidth=.6, hatch='///')
        bar.text(total/n+9, row, f'{total/n:.2f}', ha='left', va='center', fontsize=10.5, color=COLORS['ink'])
        bar.text(12, row, f'{total:.2f} ÷ {n}', ha='left', va='center', fontsize=9.0,
                 color='white' if row==0 else '#34423A')
    bar.set(yticks=[0,1], yticklabels=['问题三', '问题四'], xlim=(0, 610),
            xticks=[0,100,200,300,400,500,600], ylim=(1.48,-.55),
            xlabel='平均清除时间：结束总虚拟时间 / 已清除数（秒/源）')
    bar.set_title('（b）平均清除时间：保留末次清除后的确认耗时', pad=11)
    tidy(bar, 'x')
    handles = [Line2D([], [], color=COLORS['blue'], lw=1.9),
               Line2D([], [], color=COLORS['green'], lw=1.9),
               Patch(facecolor='#DCE1E4', edgecolor='#8E979E', hatch='///', linewidth=.6)]
    legend(fig, handles, ['问题三', '问题四', '末次清除后的确认时间 / 已清除数'],
           y=.045, ncol=3, fontsize=8.8)
    fig.text(.5, .014, '本地示例，非正式测试；问题四末次清除后确认覆盖耗时92.72秒，折合8.43秒/源；问题三为0。',
             ha='center', va='bottom', fontsize=8.6, color='#697178')
    save(fig, '07_case_progress', '本地外缘示例的清除进度与平均清除时间',
         '与轨迹图相同的两例本地外缘场景。上图按动作日志中每次成功清除时刻绘制清除比例阶梯，空心方块标记任务结束；下图使用结束总虚拟时间T除以实际清除数Nc。第三问T/Nc=3533.04/14=252.36秒/源；第四问T/Nc=5805.78/11=527.80秒/源。第四问最后清除至任务结束的92.72秒仍计入T，对平均时间贡献8.43秒/源。真实源数仅事后计算清除比例，两例不能代表批量平均或正式测试。',
         sources(cases), recommendation='适合说明清除比例与平均清除时间的统计口径，特别是末次清除与结束时间的区别。',
         notes=provenance(cases))


def main():
    setup()
    cases = [load_case(3), load_case(4)]
    route_candidates(cases)
    progress_candidates(cases)
    print(json.dumps(provenance(cases), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
