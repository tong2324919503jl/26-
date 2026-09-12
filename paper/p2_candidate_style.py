"""Shared P1-matched style for independently reviewable P2 figure candidates."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

PAPER = Path(__file__).resolve().parent
ROOT = PAPER.parent
DEST = PAPER / 'figures' / 'problem2_candidates'
BLUE = '#27647b'
INK = '#202020'
GREY = '#737373'
GOLD = '#bc9142'
GREEN = '#2c8070'
LIGHT_BLUE = '#e5eef2'
LIGHT_GREY = '#e8e8e8'


def setup():
    DEST.mkdir(parents=True, exist_ok=True)
    font = PAPER / 'fonts' / 'simsun.ttc'
    font_manager.fontManager.addfont(str(font))
    family = font_manager.FontProperties(fname=str(font)).get_name()
    plt.rcParams.update({
        'font.family': [family, 'DejaVu Serif'], 'font.size': 10,
        'axes.labelsize': 10, 'axes.titlesize': 10.5,
        'axes.titleweight': 'normal', 'font.weight': 'normal',
        'xtick.labelsize': 9, 'ytick.labelsize': 9, 'legend.fontsize': 9,
        'axes.unicode_minus': False, 'axes.edgecolor': INK,
        'axes.labelcolor': INK, 'text.color': INK,
        'xtick.color': INK, 'ytick.color': INK,
        'axes.linewidth': .75, 'xtick.major.width': .75,
        'ytick.major.width': .75, 'lines.linewidth': 1.2,
        'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'path',
        'legend.edgecolor': '#999999', 'legend.facecolor': 'white',
        'legend.framealpha': .97, 'legend.fancybox': False,
        'legend.borderpad': .55, 'savefig.facecolor': 'white',
        'figure.facecolor': 'white', 'mathtext.fontset': 'stix',
        'axes.axisbelow': True,
    })


def axes_style(ax, xlabel='$a$（米）', ylabel='$b$（米）', equal=True):
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(color='#dedede', linewidth=.45)
    ax.set_axisbelow(True)
    ax.tick_params(direction='out', length=3)
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(.75)
    if equal:
        ax.set_aspect('equal', adjustable='box')
    return ax


def panel_label(ax, text):
    ax.text(.5, -.20, text, ha='center', va='top',
            transform=ax.transAxes, fontsize=10.5, fontweight='normal')


def read_json(relative):
    return json.loads((ROOT / relative).read_text(encoding='utf-8'))


def save(fig, stem, title, caption, section, sources, notes='',
         recommendation='', data=None):
    """Save candidate artwork and evidence separately from the paper body."""
    DEST.mkdir(parents=True, exist_ok=True)
    fig.canvas.draw()
    hashes = {}
    for relative in sources:
        path = ROOT / relative
        if path.is_file():
            hashes[str(relative)] = hashlib.sha256(path.read_bytes()).hexdigest()
    for ext in ('pdf', 'svg', 'png'):
        kwargs = {'dpi': 240} if ext == 'png' else {}
        if ext == 'pdf':
            kwargs['metadata'] = {'Title': title, 'Author': '', 'Subject': caption}
        fig.savefig(DEST / f'{stem}.{ext}', bbox_inches='tight', pad_inches=.08, **kwargs)
    metadata = {
        'id': stem, 'title': title, 'caption': caption, 'section': section,
        'sources': list(sources), 'source_sha256': hashes, 'notes': notes,
        'recommendation': recommendation,
        'style_reference': ['paper/figures/p1_orthogonal_bearings.pdf',
                            'paper/figures/p12_geometry.pdf'],
        'provenance': '论文方法几何图或自建离线算例；不是官方数据或正式成绩。',
        'data': data,
    }
    (DEST / f'{stem}.json').write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
        encoding='utf-8')
    plt.close(fig)
    print(stem, title, flush=True)
