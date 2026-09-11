"""Shared visual style for the Chinese P3/P4 figure candidates."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

PAPER = Path(__file__).resolve().parent
ROOT = PAPER.parent
DEST = PAPER / 'figures' / 'p34_candidates'
COLORS = {'blue':'#6F91AB', 'green':'#90AC9A', 'peach':'#D0A184',
          'purple':'#ADA0B7', 'gray':'#AFB7BC', 'ink':'#414950',
          'light':'#EDF2F5', 'grid':'#E4E7E9', 'red':'#B87973'}
BRANCH_COLORS = {'original':COLORS['gray'], 'previous':COLORS['purple'],
                 'teammate':COLORS['peach'], 'selected':COLORS['blue']}
BRANCH_LABELS = {'original':'原默认方案', 'previous':'上一轮较优方案',
                 'teammate':'队友方案', 'selected':'本文方案'}

def setup():
    DEST.mkdir(parents=True, exist_ok=True)
    font = PAPER / 'fonts' / 'simsun.ttc'
    if not font.exists():
        font = Path('C:/Windows/Fonts/simsun.ttc')
    font_manager.fontManager.addfont(str(font))
    family = font_manager.FontProperties(fname=str(font)).get_name()
    plt.rcParams.update({'font.family':[family,'DejaVu Serif'], 'font.size':10,
        'axes.labelsize':10, 'axes.titlesize':11, 'axes.titleweight':'normal',
        'xtick.labelsize':9, 'ytick.labelsize':9, 'legend.fontsize':9,
        'axes.unicode_minus':False, 'axes.edgecolor':'#9CA4AA',
        'axes.labelcolor':COLORS['ink'], 'text.color':COLORS['ink'],
        'xtick.color':COLORS['ink'], 'ytick.color':COLORS['ink'],
        'axes.linewidth':.6, 'xtick.major.width':.6, 'ytick.major.width':.6,
        'pdf.fonttype':42, 'ps.fonttype':42, 'svg.fonttype':'path',
        'legend.edgecolor':'#C4C9CD', 'legend.facecolor':'white',
        'legend.framealpha':1, 'legend.fancybox':False,
        'savefig.facecolor':'white', 'figure.facecolor':'white',
        'lines.linewidth':1.6, 'mathtext.fontset':'stix'})

def tidy(ax, grid='y'):
    ax.spines[['top','right']].set_visible(False)
    ax.set_axisbelow(True)
    if grid:
        ax.grid(axis=grid,color=COLORS['grid'],lw=.55)
    ax.tick_params(direction='out',length=3)

def legend(fig, handles, labels, y=.035, ncol=3, **kwargs):
    result=fig.legend(handles,labels,loc='lower center',bbox_to_anchor=(.5,y),
             ncol=ncol,frameon=True,borderpad=.55,columnspacing=1.4,
             handlelength=1.9, **kwargs)
    result.get_frame().set_linewidth(.6)
    return result

def save(fig, stem, title, caption, sources, recommendation='', notes=''):
    """Persist editable vector, print PDF, PNG preview and explicit provenance."""
    fig.savefig(DEST/(stem+'.pdf'),bbox_inches='tight',pad_inches=.12,
                metadata={'Title':title,'Subject':caption,'Author':''})
    fig.savefig(DEST/(stem+'.svg'),bbox_inches='tight',pad_inches=.12)
    fig.savefig(DEST/(stem+'.png'),dpi=220,bbox_inches='tight',pad_inches=.12)
    (DEST/(stem+'.json')).write_text(json.dumps({'id':stem,'title':title,
        'caption':caption,'sources':sources,'recommendation':recommendation,
        'notes':notes},ensure_ascii=False,indent=2),encoding='utf-8')
    plt.close(fig)

def read(relative):
    return json.loads((ROOT/relative).read_text(encoding='utf-8'))
