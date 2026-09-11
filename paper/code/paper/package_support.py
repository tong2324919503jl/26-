"""Package only the sources and evidence used by the current manuscript."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from pathlib import Path
import zipfile

PAPER = Path(__file__).resolve().parent
ROOT = PAPER.parent


def selected_files() -> dict[str, Path]:
    selected = {}
    for item in json.loads((PAPER / 'source_snapshot.json').read_text(encoding='utf-8')):
        selected[item['path']] = PAPER / 'code' / item['path']
    for folder in ('problem1', 'problem2'):
        for sub in ('examples', 'results'):
            for path in (ROOT / folder / sub).rglob('*'):
                if path.is_file() and path.suffix.lower() in {'.json', '.csv', '.md', '.svg', '.txt'}:
                    selected[path.relative_to(ROOT).as_posix()] = path
    for folder in ('problem3', 'problem4'):
        base = ROOT / folder
        for path in (base / 'examples').glob('*.json'):
            if 'v3' not in path.name and 'threshold_lower_bound' not in path.name:
                selected[path.relative_to(ROOT).as_posix()] = path
        for pattern in ('benchmark_*.json', 'benchmark_*.md', 'speed_comparison_v2.*', 'coverage_certificate_v2.json', 'stress_verification.*', 'demo_result.json'):
            for path in (base / 'results').glob(pattern):
                selected[path.relative_to(ROOT).as_posix()] = path
        for path in (base / 'results' / 'online').glob('*'):
            if path.suffix in ('.json', '.jsonl'):
                selected[path.relative_to(ROOT).as_posix()] = path
    for folder in ('problem1', 'problem2', 'problem3', 'problem4'):
        for name in ('README.md', 'model.md', 'references.md'):
            path = ROOT / folder / name
            if path.exists():
                selected[path.relative_to(ROOT).as_posix()] = path
    for name in ('report.md', 'report.json', 'reference_geometry.json', 'problem4_freeze_v2.json', 'search_experiments.md', 'merge_notes.md'):
        path = ROOT / 'validation' / name
        if path.exists():
            selected[path.relative_to(ROOT).as_posix()] = path
    for name in ('simulation_guide.md', 'requirements.txt'):
        selected[name] = ROOT / name
    for path in (ROOT / 'materials' / 'problem_b').rglob('*'):
        if path.is_file():
            selected[path.relative_to(ROOT).as_posix()] = path
    for folder in ('sources', 'sections', 'figures'):
        for path in (PAPER / folder).glob('*'):
            if path.is_file():
                selected[path.relative_to(ROOT).as_posix()] = path
    for name in ('main.tex', 'JXUSTmodeling.cls', 'LICENSE', 'code_appendix.tex', 'ai_usage.tex', 'source_snapshot.json', 'README.md'):
        selected['paper/' + name] = PAPER / name
    selected['AI工具使用详情.pdf'] = PAPER / 'results' / 'AI工具使用详情.pdf'
    return selected


def main() -> None:
    items = selected_files()
    rows = []
    blobs = {}
    for name, source in sorted(items.items()):
        data = source.read_bytes()
        # Remove machine-local paths from textual report copies only. Original
        # code, inputs and repository reports are left untouched.
        if source.suffix in ('.md', '.json', '.jsonl', '.csv') and not name.endswith('.py'):
            text = data.decode('utf-8-sig')
            for prefix in (str(ROOT), str(ROOT).replace('\\', '/'), str(ROOT).replace('\\', '\\\\')):
                text = text.replace(prefix, '<PROJECT>')
            text = re.sub(r'[A-Za-z]:[/\\]+Users[/\\]+[^/\\\s"<>]+', '<USER>', text)
            text = re.sub(r'("robot_id"\s*:\s*)"[^"]*"', r'\1"ANONYMOUS"', text)
            data = text.encode('utf-8')
        rows.append([name, len(data), hashlib.sha256(data).hexdigest()])
        blobs[name] = data
    manifest = io.StringIO(newline='')
    writer = csv.writer(manifest)
    writer.writerow(['relative_path', 'bytes', 'sha256'])
    writer.writerows(rows)
    blobs['manifest.csv'] = manifest.getvalue().encode('utf-8-sig')
    blobs['README.md'] = ('# 支撑材料说明\n\n这是2026年9月11日论文工作稿的可复现支撑包。'
        '保留相对目录，用Python 3.12运行各问题solve.py；统一检查入口为scripts/verify_project.py。'
        'matplotlib用于绘图，pypdf用于资料检查；可选参考核验需要SciPy。\n\n'
        '六次正式测试成绩及原名加密日志尚未纳入；本包不是已完成正式提交的证明。'
        '演练来源说明见paper/sources/p34_evidence.md。'
        '报告副本中的机器绝对路径已替换为通用标记，原仓库文件未修改。'
        '源代码保留实际执行版本，文本报告均为本地结果。\n').encode('utf-8')
    output = PAPER / 'results' / 'supporting_materials.zip'
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(blobs.items()):
            archive.writestr(name, data)
    if output.stat().st_size > 20_000_000:
        raise RuntimeError('Supporting material exceeds 20 MB.')
    print(f'{len(blobs)} files; {output.stat().st_size} bytes; {output}')


if __name__ == '__main__':
    main()
