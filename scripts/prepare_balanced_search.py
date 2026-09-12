"""Prepare or verify balanced local cases; never execute a solver or platform."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from problem3.balanced_datasets import (
    DEFAULT_PER_COUNT, SOURCE_COUNTS, dataset_directory, prepare_dataset, validate_dataset,
)


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='生成等量覆盖10至16源、构造难度呈正态形状的自建本地样例，不运行算法。')
    parser.add_argument('--problem', choices=('3', '4', 'all'), default='all')
    parser.add_argument('--per-count', type=int, default=DEFAULT_PER_COUNT,
                        help=f'每种源数的样例数，默认{DEFAULT_PER_COUNT}，即每问{DEFAULT_PER_COUNT * len(SOURCE_COUNTS)}例。')
    parser.add_argument('--output-dir', type=Path,
                        help='仅单问可用；相对路径以对应problem目录为基准。')
    parser.add_argument('--verify-only', action='store_true', help='只校验已生成数据。')
    args = parser.parse_args()
    if args.output_dir is not None and args.problem == 'all':
        parser.error('--output-dir requires --problem 3 or 4')
    problems = (3, 4) if args.problem == 'all' else (int(args.problem),)
    for problem in problems:
        try:
            manifest = (validate_dataset(problem, args.output_dir) if args.verify_only else
                        prepare_dataset(problem, args.per_count, args.output_dir))
        except ValueError as exc:
            parser.exit(1, f'问题{problem}数据校验失败：{exc}\n')
        print(f'问题{problem}：{manifest["total_cases"]}例，10至16源各{manifest["per_count"]}例；'
              f'数据版本{manifest["dataset"]}，自建本地数据，完整性检查通过。')
        print(dataset_directory(problem, args.output_dir))


if __name__ == '__main__':
    main()
