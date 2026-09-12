"""Minimal, separate P3/P4 mechanism figures driven by current solve settings.

Only instantiate the default policy and inspect geometry; never run a policy.
Explanations and evidence live beside figures, not inside the plotting canvas.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

PAPER=Path(__file__).resolve().parent
ROOT=PAPER.parent
sys.path.insert(0,str(ROOT))
from figure_candidate_style import setup,tidy,COLORS as C
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle,Polygon,Rectangle,Wedge,Patch
from scripts.benchmark_search import get_policy,get_algorithm_version,source_fingerprint
from problem3.geometry import certified_covering_radius,optical_cover,contains
from problem4.coverage import directional_cover_certificate
from problem4.localization import _convex_hull


def outside_legend(fig,handles,labels,ncol=3,y=.025):
    leg=fig.legend(handles,labels,loc='lower center',bbox_to_anchor=(.5,y),ncol=ncol,
        frameon=True,fontsize=8.5,handlelength=1.7,columnspacing=1.3,borderpad=.5)
    leg.get_frame().set_linewidth(.6)


def save(fig,problem,name,caption,extra):
    dest=PAPER/'figures'/f'problem{problem}'/'mechanisms'
    dest.mkdir(parents=True,exist_ok=True)
    version=get_algorithm_version(problem)
    plotting_sources=(Path(__file__),PAPER/'figure_candidate_style.py')
    record=dict(problem=problem,algorithm_version=version,scope='geometry_mechanism_not_test_result',
        caption=caption,source_sha256=source_fingerprint(),
        plotting_source_sha256={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in plotting_sources},**extra)
    for ext in ('pdf','svg','png'):
        kwargs={'dpi':240} if ext=='png' else {}
        if ext=='pdf':kwargs['metadata']={'Title':name,'Subject':caption,'Author':''}
        fig.savefig(dest/f'{name}.{ext}',bbox_inches='tight',pad_inches=.09,**kwargs)
    (dest/f'{name}.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (dest/f'{name}_caption.md').write_text(caption+'\n\n算法版本：'+version+'。这是机制图，不是正式测试结果。\n',encoding='utf-8')
    plt.close(fig)


def coverage(problem):
    policy=get_policy(problem,'adaptive')
    base=[tuple(p) for p in policy.coverage_points()]
    layouts=[base]
    if problem==3 and hasattr(policy,'annular_count') and hasattr(policy,'annular_radius'):
        n,r=policy.annular_count,policy.annular_radius
        layouts.append([(0.,0.)]+[(r*math.cos(math.tau*k/n),r*math.sin(math.tau*k/n)) for k in range(n)])
    proofs=[]
    for points in layouts:
        if problem==3:
            radius=certified_covering_radius(points)
            proof={'certified':radius<1000,'radius_bound_m':radius}
        else:
            proof=directional_cover_certificate(points,early_exit=False)
        if not proof['certified']:raise ValueError('Current solve coverage layout did not pass the independent geometry check')
        proofs.append(proof)
    fig,axs=plt.subplots(1,len(layouts),figsize=(7.0 if len(layouts)>1 else 4.4,3.6),squeeze=False)
    for i,(ax,points) in enumerate(zip(axs[0],layouts)):
        pp=[(x/1000,y/1000) for x,y in points]
        boundary=Circle((0,0),1.8,fc='none',ec='#6D777F',lw=.9,zorder=4);ax.add_patch(boundary)
        if problem==3:
            for q in pp:
                disk=Circle(q,1.,fc=C['blue'],ec=C['blue'],alpha=.15,lw=.6,zorder=1)
                ax.add_patch(disk);disk.set_clip_path(boundary)
            if i:
                ax.add_patch(Circle((0,0),1.,fc='#F2F1ED',ec='#BFC5C8',lw=.5,hatch='///',zorder=2))
        else:
            ax.add_patch(Polygon(_convex_hull(pp),fc=C['green'],ec=C['green'],alpha=.22,lw=.7))
        ax.scatter(*zip(*pp),s=22,c=C['blue'],edgecolors='white',lw=.5,zorder=5)
        ax.scatter(0,0,s=27,c=C['ink'],marker='D',edgecolors='white',lw=.5,zorder=6)
        limit=max(2.05,max(math.hypot(*p) for p in pp)*1.08)
        ax.set(xlim=(-limit,limit),ylim=(-limit,limit),aspect='equal',xlabel='横坐标 / 千米',ylabel='纵坐标 / 千米')
        ax.set_xticks([-2,-1,0,1,2]);ax.set_yticks([-2,-1,0,1,2]);tidy(ax,'both')
        if len(layouts)>1:ax.text(.025,.96,f'({chr(97+i)})',transform=ax.transAxes,va='top',fontsize=10)
    handles=[Line2D([],[],c='#6D777F',lw=.9),Line2D([],[],marker='o',ls='',c=C['blue'],ms=4),
             Patch(fc=C['blue'] if problem==3 else C['green'],alpha=.24,ec='#ABB7BE')]
    labels=['目标圆','检测点','接收圆盘' if problem==3 else '检测点凸包']
    if len(layouts)>1:
        handles.append(Patch(fc='#F2F1ED',ec='#BFC5C8',hatch='///'));labels.append('已排除区域')
    outside_legend(fig,handles,labels,ncol=4 if len(layouts)>1 else 3)
    fig.subplots_adjust(left=.09 if len(layouts)>1 else .16,right=.98,top=.98,bottom=.22,wspace=.30)
    caption=(f'问题{problem}当前solve默认方案的覆盖布局。检测点直接读取当前策略，'
        '每个布局重新进行连续区域几何核验；图不包含运行轨迹或测试成绩。')
    if len(layouts)>1:
        caption+=' (a)常规布局；(b)原点全频道无收信时采用的条件外环。相位仅作示意，实际按公开观测选择。'
    if problem==4:caption+=' 凸包包含目标圆仅展示几何结构，定向覆盖结论还依赖独立邻域覆盖证书。'
    save(fig,problem,'coverage_layout',caption,dict(layouts=layouts,geometry_certificates=proofs))


def directional():
    fig,axs=plt.subplots(1,2,figsize=(6.6,3.25))
    neighbours=[(.82*math.cos(math.radians(t)),.82*math.sin(math.radians(t))) for t in (20,145,260)]
    for i,ax in enumerate(axs):
        ax.set(xlim=(-1.14,1.14),ylim=(-1.12,1.12),aspect='equal');ax.set_axis_off()
        ax.add_patch(Circle((0,0),1,fc='none',ec='#A8B1B7',lw=.9,ls='--'))
        ax.add_patch(Wedge((0,0),1,-90,90,fc=C['blue'],alpha=.2,ec='none'))
        ax.plot([0,0],[-1,1],color=C['blue'],ls='--',lw=.8)
        ax.scatter(0,0,c=C['ink'],marker='*',s=50,zorder=5)
        ax.annotate('$g$',(0,0),xytext=(7,-12),textcoords='offset points',fontsize=10)
        ax.annotate('$d$',xy=(.68,-.58),xytext=(.12,-.58),va='center',fontsize=10,
            arrowprops=dict(arrowstyle='->',color=C['blue'],lw=1))
        ax.text(.02,.97,f'({chr(97+i)})',transform=ax.transAxes,va='top',fontsize=10)
    a,b=axs
    a.scatter(.63,.36,c=C['green'],s=30,ec='white',lw=.5,zorder=4)
    a.scatter(-.64,.32,c=C['red'],s=35,marker='x',lw=1.2,zorder=4)
    for label,q in [('P',(.63,.36)),('Q',(-.64,.32))]:
        a.annotate(f'${label}$',q,xytext=(0,9),textcoords='offset points',ha='center')
    b.add_patch(Polygon(neighbours,fc=C['green'],ec=C['green'],alpha=.32,lw=.8))
    b.scatter(*zip(*neighbours),c=C['blue'],s=28,ec='white',lw=.6,zorder=4)
    for j,q in enumerate(neighbours):b.annotate(f'$v_{j+1}$',q,xytext=(8 if q[0]>0 else -8,8 if q[1]>0 else -10),
        textcoords='offset points',ha='left' if q[0]>0 else 'right',fontsize=9)
    outside_legend(fig,[Patch(fc=C['blue'],alpha=.2),Patch(fc=C['green'],alpha=.32),
        Line2D([],[],marker='o',ls='',c=C['green'],ms=4),Line2D([],[],marker='x',ls='',c=C['red'],ms=5)],
        ['有效接收半圆','邻点凸包','阳性观测','阴性观测'],ncol=4)
    fig.subplots_adjust(left=.03,right=.98,top=.98,bottom=.16,wspace=.16)
    save(fig,4,'directional_visibility',
        '定向接收机制示意。(a)同在接收距离内的P收信，Q处于背面仍可能无信号。(b)源g在距源不超过1000米的检测点凸包内，任意发射闭半平面都至少包含一个检测点。d为发射方向；三点为构造示意，不是全局布局。',
        dict(neighbours=neighbours,coordinate_unit='1000 m'))


def optical(problem):
    policy=get_policy(problem,'adaptive');radius=policy.config.clear_guarantee_radius_m
    step=policy.config.optical_spacing_m
    if not 0<radius<20 or step/math.sqrt(2)>radius:raise ValueError('Current optical settings do not support this coverage illustration')
    region=[(-45.,0.),(-24.,-21.),(22.,-19.),(45.,0.),(25.,23.),(-20.,22.)]
    pts=optical_cover(region,step)
    fig,ax=plt.subplots(figsize=(4.8,3.3))
    for x,y in pts:
        ax.add_patch(Rectangle((x-step/2,y-step/2),step,step,fc='#F7F8F9',ec='#B7C0C6',lw=.6))
    ax.add_patch(Polygon(region,fc=C['peach'],ec=C['peach'],alpha=.35,lw=.9))
    for x,y in pts:ax.add_patch(Circle((x,y),radius,fc='none',ec=C['blue'],alpha=.6,lw=.7))
    for inside,marker,col in [(True,'o',C['blue']),(False,'s',C['purple'])]:
        pp=[p for p in pts if contains(region,p)==inside]
        if pp:ax.scatter(*zip(*pp),c=col,marker=marker,s=25,ec='white',lw=.5,zorder=4)
    xlim=(min(p[0] for p in pts)-radius-3,max(p[0] for p in pts)+radius+3)
    ylim=(min(p[1] for p in pts)-radius-3,max(p[1] for p in pts)+radius+3)
    ax.set(aspect='equal',xlim=xlim,ylim=ylim,xlabel='横坐标 / 米',ylabel='纵坐标 / 米');tidy(ax,False)
    outside_legend(fig,[Patch(fc=C['peach'],alpha=.35),Line2D([],[],c=C['blue'],lw=.8),
        Line2D([],[],ls='',marker='o',c=C['blue'],ms=4),Line2D([],[],ls='',marker='s',c=C['purple'],ms=4)],
        ['候选区域','清除圆盘','内部中心','外部中心'],ncol=4,y=.01)
    fig.subplots_adjust(left=.13,right=.98,top=.97,bottom=.22)
    save(fig,problem,'optical_grid',
        f'问题{problem}光学网格机制示意。方格边长读取当前策略配置为{step:g}米，清除圆盘半径为{radius:g}米。与候选区域相交的格中心全部保留，包括区域外中心。候选多边形为构造示意，不是实际测量结果。',
        dict(polygon=region,clear_points=pts,grid_spacing_m=step,clear_radius_m=radius))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--problem',choices=('3','4','all'),default='all')
    args=parser.parse_args();setup()
    for problem in ((3,4) if args.problem=='all' else (int(args.problem),)):
        coverage(problem);optical(problem)
        if problem==4:directional()
        print(f'problem{problem}: separate mechanism figures exported')

if __name__=='__main__':main()
