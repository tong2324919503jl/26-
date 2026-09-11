"""Assemble the manuscript and freeze its reproducible source-code appendix."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

PAPER = Path(__file__).resolve().parent
ROOT = PAPER.parent


def figure(name: str, caption: str, label: str, width: str = '.88') -> str:
    return (r'\begin{figure}[htbp]' + '\n' + r'\centering' + '\n'
            + rf'\includegraphics[width={width}\textwidth]{{{name}.pdf}}' + '\n'
            + rf'\caption{{{caption}}}\label{{{label}}}' + '\n'
            + r'\end{figure}' + '\n')


def assemble() -> None:
    sec = PAPER / 'sections'
    front = (sec / 'front.tex').read_text(encoding='utf-8')
    p12 = (sec / 'p12.tex').read_text(encoding='utf-8')
    p34 = (sec / 'p34.tex').read_text(encoding='utf-8')
    method, checks = p34.split('% 以下片段建议放入“模型的检验”章节。', 1)
    p12 = p12.replace(r'\subsection{问题二：保证收信的第二检测点选择}',
        figure('p12_geometry', '合法示向观测形成的三角形及两类覆盖圆', 'fig:triangles')
        + r'\subsection{问题二：保证收信的第二检测点选择}')
    p12 += figure('p2_candidates', r'第二检测点安全区域与目标圆条件化选点（灰点为已访问的10\%近优代表点）', 'fig:p2')
    method = method.replace('将圆缺按$V_\\ell^+$的Voronoi区域划分。',
        '将圆缺按$V_\\ell^+$的Voronoi区域划分\\cite{deberg2008}。')
    text = front + '\n' + p12 + '\n' + method
    text += '\n' + r'\section{模型的检验}\label{sec:6}' + '\n' + checks
    discussion = (sec / 'discussion.tex').read_text(encoding='utf-8')
    text += '\n' + discussion.split(r'\begin{appendixx}', 1)[0]
    text += '\n' + r'\end{document}' + '\n'
    (PAPER / 'main.tex').write_text(text, encoding='utf-8', newline='\n')


def freeze_code() -> list[str]:
    paths = []
    for folder in ('problem1', 'problem2', 'problem3', 'problem4'):
        paths += sorted((ROOT / folder).glob('*.py'))
        paths += sorted((ROOT / folder / 'tests').glob('*.py'))
    paths += [p for p in sorted((ROOT / 'scripts').glob('*.py')) if p.name != 'experiment_search.py']
    paths += [PAPER / 'plot_geometry.py', PAPER / 'plot_search_results.py', PAPER / 'build_paper.py', PAPER / 'package_support.py']
    files = []
    hashes = []
    for source in paths:
        if not source.exists():
            raise FileNotFoundError(source)
        name = source.relative_to(ROOT).as_posix()
        target = PAPER / 'code' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        data = target.read_bytes()
        hashes.append({'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        files.append(name)
    (PAPER / 'source_snapshot.json').write_text(json.dumps(hashes, ensure_ascii=False, indent=2), encoding='utf-8')
    source = r'''\documentclass[a4paper,10pt,UTF8,fontset=none]{ctexart}
\usepackage[left=2.5cm,right=2.5cm,top=2.5cm,bottom=2.5cm]{geometry}
\setCJKmainfont[Path=fonts/,FontIndex=0,AutoFakeBold=true]{simsun.ttc}
\setCJKsansfont{FandolHei-Regular.otf}
\setCJKmonofont[Path=fonts/,FontIndex=0,AutoFakeBold=true]{simsun.ttc}
\xeCJKDeclareCharClass{CJK}{"2190 -> "22FF}
\usepackage{fontspec}
\setmonofont{Latin Modern Mono}
\usepackage{fvextra}
\usepackage[hidelinks]{hyperref}
\hypersetup{pdftitle={完整程序附录},pdfauthor={}}
\pagestyle{empty}
\setlength{\parindent}{0pt}
\begin{document}
'''
    for index, name in enumerate(files, 1):
        source += r'\subsection*{程序 ' + str(index) + r'：\texttt{\detokenize{' + name + '}}}\n'
        source += rf'\VerbatimInput[breaklines=true,breakanywhere=true,fontsize=\fontsize{{8}}{{10}}\selectfont,numbers=left,numbersep=5pt]{{code/{name}}}' + '\n'
    source += '\\end{document}\n'
    (PAPER / 'code_appendix.tex').write_text(source, encoding='utf-8', newline='\n')
    return files


if __name__ == '__main__':
    assemble()
    print('Assembled main.tex without appendices, as requested.')
