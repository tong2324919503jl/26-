"""One local command: verify balanced cases, run current solve, plot each problem."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
import re
import os
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from problem3.balanced_datasets import DEFAULT_PER_COUNT,SOURCE_COUNTS


def execute(script,*arguments):
    subprocess.run([sys.executable,str(ROOT/script),*map(str,arguments)],cwd=ROOT,check=True,
        env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8'))


def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    cases_per_problem=DEFAULT_PER_COUNT*len(SOURCE_COUNTS)
    parser=argparse.ArgumentParser(description='构造难度呈正态形状的本地均衡样例：当前solve测试与分问绘图，不连接平台。')
    parser.add_argument('--problem',choices=('3','4','all'),default='all')
    parser.add_argument('--run-id',help='本次结果名称；默认自动创建唯一名称')
    parser.add_argument('--limit-per-count',type=int,help=f'仅用于流程预览，例如2表示每问{2*len(SOURCE_COUNTS)}例；默认每问全部{cases_per_problem}例')
    parser.add_argument('--resume',action='store_true',help='同一版本和数据下继续已有run-id')
    parser.add_argument('--plot-only',action='store_true',help='只重新绘制已有批次')
    parser.add_argument('--prepare-only',action='store_true',help=f'仅准备并校验样例；每问{cases_per_problem}例，两问共{2*cases_per_problem}例')
    parser.add_argument('--jobs',type=int,choices=(1,2),default=2,help='两问同时运行或依次运行；每问内部串行')
    parser.add_argument('--skip-mechanisms',action='store_true',help='不重建与当前配置对应的机制图')
    args=parser.parse_args()
    if args.limit_per_count is not None and args.limit_per_count<=0:
        parser.error('--limit-per-count must be positive')
    if args.prepare_only and (args.plot_only or args.resume or args.limit_per_count):
        parser.error('--prepare-only cannot be combined with run controls')
    if (args.resume or args.plot_only) and not args.run_id:
        parser.error('--resume and --plot-only require --run-id')
    run_id=args.run_id or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8]
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,95}',run_id):
        parser.error('run-id must use 1..96 letters, digits, underscore, dot or hyphen')
    if args.prepare_only:
        execute('scripts/prepare_balanced_search.py','--problem',args.problem)
        return 0
    # Fail early if plotting dependencies are unavailable, before a long batch.
    import matplotlib,numpy  # noqa: F401
    problems=(3,4) if args.problem=='all' else (int(args.problem),)
    def one(problem):
        if not args.plot_only:
            execute('scripts/prepare_balanced_search.py','--problem',problem)
            batch=['--problem',problem,'--run-id',run_id]
            if args.limit_per_count is not None:batch+=['--limit-per-count',args.limit_per_count]
            if args.resume:batch+=['--resume']
            execute('scripts/benchmark_balanced_search.py',*batch)
        chart=['--problem',problem,'--run-id',run_id]
        if args.limit_per_count is not None:chart+=['--allow-partial']
        execute('paper/plot_balanced_search.py',*chart)
        if not args.skip_mechanisms:
            execute('paper/plot_search_mechanisms.py','--problem',problem)
        return problem
    with ThreadPoolExecutor(max_workers=min(args.jobs,len(problems))) as pool:
        # Consume every future so neither problem's failure can disappear.
        futures=[pool.submit(one,p) for p in problems]
        errors=[]
        for future in futures:
            try:future.result()
            except Exception as exc:errors.append(str(exc))
    if errors:
        for error in errors:print(error,file=sys.stderr)
        return 1
    print(f'本地运行与绘图完成：{run_id}')
    for p in problems:
        print(ROOT/f'problem{p}/results/balanced'/run_id)
        print(ROOT/'paper/figures'/f'problem{p}'/run_id)
    return 0


if __name__=='__main__':raise SystemExit(main())
