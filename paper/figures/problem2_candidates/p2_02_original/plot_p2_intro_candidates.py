"""Rebuild six P2 method-introduction candidates from production geometry.

Plots are self-created examples for editorial selection; no solver results or
paper sections are changed. Run from any directory with Python + matplotlib.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, ConnectionPatch, Patch, Polygon, Rectangle

PAPER = Path(__file__).resolve().parent
sys.path.insert(0, str(PAPER.parent))
from problem2.solve import (bearing, clip_polygon, direction_clearance, distance,
    first_region_outer_local, guaranteed_reception, polygon_diameter,
    posterior_outer_polygon, safe_centers, safe_radial_limit)
from p2_candidate_style import (BLUE, GOLD, GREEN, GREY, INK, LIGHT_BLUE,
    LIGHT_GREY, axes_style, panel_label, read_json, save, setup)

SOURCES = ['paper/sections/p12.tex', 'problem2/solve.py']
E = math.radians(1.)


def safe_boundary(n=3601):
    angles = np.linspace(-89., 89., n)
    radii = np.array([safe_radial_limit(float(x)) for x in angles])
    result = np.column_stack((radii*np.cos(np.radians(angles)),
                              radii*np.sin(np.radians(angles))))
    assert all(guaranteed_reception(tuple(p)) for p in result)
    return result


def poly(ax, vertices, face=LIGHT_BLUE, edge=BLUE, alpha=1., **kwargs):
    return ax.add_patch(Polygon(vertices, facecolor=face, edgecolor=edge,
        linewidth=1., alpha=alpha, closed=True, **kwargs))


def point(ax, p, label, offset=(6, 7), color=INK, marker='o', size=20):
    ax.scatter(*p, s=size, marker=marker, color=color, zorder=8)
    ax.annotate(label, p, offset, textcoords='offset points', color=color,
                fontsize=10, zorder=9)


def wedge(ax, station, angle, length, color, alpha=.07):
    angles=np.radians(np.linspace(angle-1., angle+1., 80))
    v=np.column_stack((station[0]+length*np.cos(angles),
                        station[1]+length*np.sin(angles)))
    poly(ax, np.vstack((station,v)), face=color, edge=color, alpha=alpha, zorder=2)
    for t in (angle-1., angle+1.):
        t=math.radians(t)
        ax.plot([station[0],station[0]+length*math.cos(t)],
                [station[1],station[1]+length*math.sin(t)], color=color, lw=.7, alpha=.8)
    t=math.radians(angle)
    ax.plot([station[0],station[0]+length*math.cos(t)],
            [station[1],station[1]+length*math.sin(t)], color=color, lw=.8, alpha=.8)


def contains(poly_vertices, p, tolerance=1e-7):
    crosses=[]
    for a,b in zip(poly_vertices, list(poly_vertices[1:])+[poly_vertices[0]]):
        crosses.append((b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]))
    return min(crosses)>=-tolerance or max(crosses)<=tolerance


def figure01():
    plan=read_json('problem2/results/selection.json')
    cfg=read_json('problem2/examples/synthetic_case.json')
    q=tuple(plan['selected']['local_xy_m'])
    source=tuple(cfg['synthetic_source_xy_m'])
    psi=bearing(source,q)+cfg['synthetic_second_error_deg']
    posterior=posterior_outer_polygon((0.,0.),0.,q,psi,circle_sides=360)
    assert guaranteed_reception(q) and direction_clearance(q)>5
    assert contains(posterior,source)
    assert distance(source,q)<=cfg['synthetic_reception_radius_m']
    verts=np.array(posterior)
    ends=max(((a,b) for a in posterior for b in posterior),key=lambda ab:distance(*ab))
    diam=polygon_diameter(posterior)
    fig,(a,b)=plt.subplots(1,2,figsize=(10.6,4.7))
    fig.subplots_adjust(left=.065,right=.985,bottom=.18,top=.98,wspace=.22)
    boundary=safe_boundary()
    poly(a,boundary,face=LIGHT_GREY,edge=GREY,alpha=.8)
    wedge(a,(0.,0.),0.,1550.,BLUE)
    wedge(a,q,psi,1100.,GOLD)
    poly(a,posterior,face='#f0dfbb',edge=GOLD,zorder=5)
    a.plot([0,q[0]],[0,q[1]],color=INK,lw=.8,ls=(0,(3,4)))
    point(a,(0.,0.),'$S_1$',(-16,-15))
    point(a,q,'$q_*$',(7,6),marker='*',size=75)
    a.text(590,-535,r'$\mathcal{C}_{\rm safe}$',color=GREY,fontsize=12)
    a.set(xlim=(-150,1590),ylim=(-930,870))
    a.set_xticks([0,500,1000,1500]); a.set_yticks([-750,-500,-250,0,250,500,750])
    axes_style(a)
    handles=[Patch(facecolor=LIGHT_GREY,edgecolor=GREY,label='保证收信区域'),
        Line2D([0],[0],color=BLUE,label=r'首示向 $0^\circ\pm1^\circ$'),
        Line2D([0],[0],color=GOLD,label=r'第二示向 $\psi\pm1^\circ$')]
    a.legend(handles=handles,loc='lower right',fontsize=8.5)
    center=verts.mean(axis=0); width=max(np.ptp(verts[:,0]),np.ptp(verts[:,1]))+28
    x0,x1=center[0]-width/2,center[0]+width/2
    y0,y1=center[1]-width/2,center[1]+width/2
    rect=Rectangle((x0,y0),width,width,fill=False,edgecolor=INK,lw=.8,zorder=7)
    a.add_patch(rect)
    wedge(b,(0.,0.),0.,1700.,BLUE,.025)
    wedge(b,q,psi,1500.,GOLD,.03)
    poly(b,posterior,face='#f0dfbb',edge=GOLD,zorder=5)
    b.plot(*np.array(ends).T,color=INK,lw=1.7,zorder=6)
    point(b,source,'$G$',(5,-15),color=GREEN,size=22)
    for i,v in enumerate(posterior):
        b.scatter(*v,color=INK,s=10,zorder=7)
    mid=np.mean(ends,axis=0)
    angle=math.degrees(math.atan2(ends[1][1]-ends[0][1],ends[1][0]-ends[0][0]))
    if abs(angle)>90: angle+=180
    b.text(*mid,fr'$D={diam:.2f}\,\mathrm{{m}}$',fontsize=10,rotation=angle,
           rotation_mode='anchor',ha='center',va='bottom',bbox=dict(fc='white',ec='none',pad=.9),zorder=8)
    b.set(xlim=(x0,x1),ylim=(y0,y1)); axes_style(b)
    for p1,p2 in (((x1,y1),(0,1)),((x1,y0),(0,0))):
        fig.add_artist(ConnectionPatch(p1,p2,coordsA=a.transData,coordsB=b.transAxes,
                                        color=GREY,lw=.6,zorder=1))
    b.legend(handles=[Patch(facecolor='#f0dfbb',edgecolor=GOLD,label=r'后验外包 $\overline{U}(q_*,\psi)$'),
        Line2D([0],[0],color=INK,label='区域直径'),
        Line2D([0],[0],marker='o',color='none',markerfacecolor=GREEN,label='自建真实源')],loc='lower left',fontsize=8.5)
    panel_label(a,'（a）保证收信的第二检测点'); panel_label(b,'（b）第二读数后的定位区域')
    save(fig,'p2_01_method_overview','保证收信选点与二次定位',
         '自建算例中，先在四圆盘安全域内选择第二点，再由两次正常示向更新候选源区域；右图为实际第二读数的后验外包及其直径。',
         '首验信息与最坏直径目标；问题二方法引入',SOURCES+['problem2/results/selection.json','problem2/examples/synthetic_case.json'],
         notes='两次示向均按真实 ±1° 绘制；右图圆约束使用生产实现的 360 边外包。该次后验直径不等于选点评分 C，也不是最坏读数结果。',
         recommendation='优先：与问题一的大图及区域放大结构衔接最直接。',
         data={'q_m':q,'source_m':source,'second_bearing_deg':psi,'posterior_diameter_m':diam,
               'posterior_vertices_m':posterior,'source_contained':True,'guaranteed_reception':True})


def figure02():
    centers=safe_centers()
    fig=plt.figure(figsize=(10.4,5.5))
    a=fig.add_axes([.065,.16,.57,.8]); b=fig.add_axes([.715,.63,.24,.32]); c=fig.add_axes([.715,.17,.24,.32])
    for i,p in enumerate(centers):
        col=BLUE if i<2 else GOLD
        a.add_patch(Circle(p,1000,fill=False,ec=col,lw=1.1,ls='-' if i%2 else (0,(4,2)),alpha=.8))
    poly(a,safe_boundary(),face=LIGHT_GREY,edge=INK,zorder=4)
    for p in centers: a.scatter(*p,s=10,color=INK,zorder=6)
    a.text(500,250,r'$\mathcal{C}_{\rm safe}$',ha='center',fontsize=14,zorder=6)
    a.set(xlim=(-1110,2100),ylim=(-1110,1110)); axes_style(a)
    a.set_xticks([-1000,0,1000,2000]); a.set_yticks([-1000,-500,0,500,1000])
    a.legend(handles=[Line2D([0],[0],color=BLUE,label=r'$B(5u_\pm,1000)$'),
        Line2D([0],[0],color=GOLD,label=r'$B(1000u_\pm,1000)$'),
        Patch(facecolor=LIGHT_GREY,edgecolor=INK,label='四圆盘交集')],loc='lower right',fontsize=9)
    for ax,sub,span,col in ((b,centers[:2],.16,BLUE),(c,centers[2:],31,GOLD)):
        x=sub[0][0]
        for i,p in enumerate(sub):
            point(ax,p,r'$5u_-$' if ax is b and i==0 else r'$5u_+$' if ax is b else r'$1000u_-$' if i==0 else r'$1000u_+$',
                  offset=(5,-11 if i==0 else 5),color=col,size=15)
        ax.plot([x,x],[sub[0][1],sub[1][1]],color=col,ls=':',lw=.8)
        ax.set(xlim=(x-span,x+span),ylim=(-span,span)); axes_style(ax)
        ax.ticklabel_format(style='plain',useOffset=False)
        if ax is b:
            ax.set_xticks([4.9,5.,5.1]);ax.set_yticks([-.1,0,.1])
        else:
            ax.set_xticks([980,1000,1020]);ax.set_yticks([-20,0,20])
    panel_label(a,'（a）四圆盘及其交集')
    b.text(.5,-.32,'（b）5 米端点放大',ha='center',va='top',transform=b.transAxes,fontsize=10.5)
    c.text(.5,-.32,'（c）1000 米端点放大',ha='center',va='top',transform=c.transAxes,fontsize=10.5)
    save(fig,'p2_02_four_disks','四圆盘安全区域与角端点',
         '四个半径 1000 米的圆盘给出保证收信区域，右侧分别放大 5 米与 1000 米径向端点处的两个圆心。',
         '四圆盘安全候选域',SOURCES,
         notes='各面板均等比例；不同面板的放大倍数不同，角误差仍为 ±1°。边界由生产 safe_radial_limit 计算并逐点检查四圆盘包含。',
         recommendation='优先：直接配合四圆盘公式与证明。',
         data={'circle_centers_m':centers,'radius_m':1000,'near_center_separation_m':distance(*centers[:2]),
               'far_center_separation_m':distance(*centers[2:]),'boundary_points_verified':3601})


def figure03():
    boundary=safe_boundary(); a_s,b_s=math.sin(E),math.cos(E)
    upper=clip_polygon([tuple(p) for p in boundary],(a_s,-b_s),-5.)
    lower=clip_polygon([tuple(p) for p in boundary],(a_s,b_s),-5.)
    for vertices in (upper,lower):
        assert all(guaranteed_reception(p) and direction_clearance(p)>=5.-1e-7 for p in vertices)
    fig,(a,b)=plt.subplots(1,2,figsize=(10.5,4.8))
    fig.subplots_adjust(left=.065,right=.985,bottom=.19,top=.97,wspace=.23)
    for ax in (a,b):
        poly(ax,boundary,face=LIGHT_GREY,edge=GREY,zorder=2)
        poly(ax,upper,face=LIGHT_BLUE,edge=BLUE,zorder=3)
        poly(ax,lower,face=LIGHT_BLUE,edge=BLUE,zorder=3)
        xs=np.linspace(0,1500,200)
        ax.fill_between(xs,-xs*math.tan(E),xs*math.tan(E),color=GOLD,alpha=.35,zorder=4)
        ax.plot(xs,xs*math.tan(E),color=GOLD,lw=.9,zorder=5)
        ax.plot(xs,-xs*math.tan(E),color=GOLD,lw=.9,zorder=5)
        axes_style(ax)
    a.set(xlim=(-80,1120),ylim=(-940,940)); a.set_xticks([0,500,1000]);a.set_yticks([-750,-500,-250,0,250,500,750])
    point(a,(0,0),'$S_1$',(5,11))
    a.text(540,460,r'$\mathcal{F}$',fontsize=17,color=BLUE)
    a.text(540,-490,r'$\mathcal{F}$',fontsize=17,color=BLUE)
    a.add_patch(Rectangle((460,-40),80,80,fill=False,edgecolor=INK,lw=.8,zorder=8))
    a.legend(handles=[Patch(facecolor=LIGHT_BLUE,edgecolor=BLUE,label='正常测向可行域'),
        Patch(facecolor=LIGHT_GREY,edgecolor=GREY,label='近区保守排除带'),
        Patch(facecolor=GOLD,alpha=.35,label='首示向扇区')],loc='lower right',fontsize=8.5)
    b.set(xlim=(460,540),ylim=(-40,40));b.set_xticks([460,480,500,520,540]);b.set_yticks([-40,-20,0,20,40])
    p=np.array([492.,(492*a_s+5)/b_s]); u=np.array([b_s,a_s]); foot=np.dot(p,u)*u
    b.annotate('',xy=p,xytext=foot,arrowprops=dict(arrowstyle='<->',color=INK,lw=.9),zorder=8)
    b.text(p[0]-4,p[1]+3,'5 米',ha='right',fontsize=9,zorder=9)
    b.text(515,26,r'$\mathcal{F}$',color=BLUE,fontsize=13)
    b.text(515,-29,r'$\mathcal{F}$',color=BLUE,fontsize=13)
    b.text(517,0,r'$U_1$',color=GOLD,fontsize=13)
    for p1,p2 in (((540,40),(0,1)),((540,-40),(0,0))):
        fig.add_artist(ConnectionPatch(p1,p2,coordsA=a.transData,coordsB=b.transAxes,color=GREY,lw=.6,zorder=1))
    panel_label(a,'（a）安全域中的正常测向可行域');panel_label(b,'（b）首扇区及 5 米排除带放大')
    save(fig,'p2_03_feasible_direction','从保证收信到保证正常测向',
         '在四圆盘安全域中，进一步排除到首扇区距离不超过 5 米的保守带；右侧以真实比例放大这一局部条件。',
         '四圆盘安全候选域',SOURCES,
         notes='图示蓝域为严格可行域的闭包，边界等号不属于正常测向保证条件。移动预算 L=1100 米在此不激活。灰色带是保守排除范围，并不代表所有相应点必然产生近区反馈。',
         recommendation='补充：适合正文解释最后一个可行性约束。',
         data={'error_deg':1.,'near_threshold_m':5.,'move_budget_m':1100.,'perpendicular_gap_verified_m':float(np.linalg.norm(p-foot)),
               'safe_and_clearance_checks_passed':True})


def figure04():
    source=(1000.,0.); q_bad=(0.,200.); q_good=(80.,200.)
    assert distance(source,(0,0))==1000 and distance(source,q_bad)>1000
    assert guaranteed_reception(q_good) and direction_clearance(q_good)>5
    fig,(a,b)=plt.subplots(1,2,figsize=(10.5,4.8),gridspec_kw={'width_ratios':[1.2,1.]})
    fig.subplots_adjust(left=.065,right=.985,bottom=.18,top=.97,wspace=.24)
    for ax in (a,b):
        ax.add_patch(Circle(source,1000,facecolor=LIGHT_BLUE,edgecolor=BLUE,lw=1.3,zorder=1))
        ax.plot([0,q_bad[0]],[0,q_bad[1]],color=GOLD,lw=1.3,zorder=5)
        axes_style(ax)
    a.plot([0,1000],[0,0],color=BLUE,lw=.8)
    a.plot([q_bad[0],1000],[q_bad[1],0],color=GOLD,lw=1.,ls='--')
    point(a,source,'$G$',(7,7));point(a,(0,0),'$S_1$',(-17,-14));point(a,q_bad,r'$q_\perp$',(-21,7),color=GOLD,marker='x',size=28)
    a.text(1050,-580,'$R=1000$ 米',color=BLUE,fontsize=10)
    a.text(530,60,fr'$d_2={distance(source,q_bad):.2f}$ 米',rotation=-11,ha='center',fontsize=9,color=GOLD)
    a.set(xlim=(-170,2180),ylim=(-1100,1100));a.set_xticks([0,500,1000,1500,2000]);a.set_yticks([-1000,-500,0,500,1000])
    a.add_patch(Rectangle((-35,-35),280,280,fill=False,edgecolor=INK,lw=.8,zorder=7))
    point(b,(0,0),'$S_1$',(-20,-14));point(b,q_bad,r'$q_\perp$',(-21,7),color=GOLD,marker='x',size=30)
    point(b,q_good,'$q$',(7,7),color=GREEN,size=24)
    b.plot([0,80],[0,200],color=GREEN,lw=1.,ls=(0,(4,3)))
    b.set(xlim=(-35,245),ylim=(-35,245));b.set_xticks([0,50,100,150,200]);b.set_yticks([0,50,100,150,200])
    b.legend(handles=[Patch(facecolor=LIGHT_BLUE,edgecolor=BLUE,label='真实接收圆'),
         Line2D([0],[0],marker='x',color=GOLD,label='纯横移后失收'),
         Line2D([0],[0],marker='o',color=GREEN,label='安全域内候选点')],loc='lower right',fontsize=8.5)
    for p1,p2 in (((245,245),(0,1)),((245,-35),(0,0))):
        fig.add_artist(ConnectionPatch(p1,p2,coordsA=a.transData,coordsB=b.transAxes,color=GREY,lw=.6,zorder=1))
    panel_label(a,'（a）首点恰在真实接收圆上');panel_label(b,'（b）纯横移与安全选点放大')
    save(fig,'p2_04_lateral_loss','纯横向移动失收的合法反例',
         '取自建源 G=(1000,0) 米及接收半径 1000 米。纯横移至 (0,200) 米后失收；(80,200) 米则同时满足四圆盘安全约束与正常测向条件。',
         '四圆盘安全候选域；方法引入的动机',SOURCES,
         notes='真实源位于首示向中心线，首示向误差为 0°，符合 ±1° 限制。接收圆是这个反例的真实圆，不是普遍已知圆。',
         recommendation='优先：直观说明为什么不能只追求横向交会角。',
         data={'source_m':source,'radius_m':1000.,'bad_q_m':q_bad,'bad_distance_m':distance(source,q_bad),
               'good_q_m':q_good,'good_distance_m':distance(source,q_good),'good_q_all_sources_safe':True})


def figure05():
    fig=plt.figure(figsize=(10.4,6.7))
    top=[fig.add_axes([.07,.40,.405,.57]),fig.add_axes([.555,.40,.405,.57])]
    zoom=[fig.add_axes([.15,.09,.245,.235]),fig.add_axes([.635,.09,.245,.235])]
    rows=[]
    for i,(ax,z,station) in enumerate(zip(top,zoom,((0.,0.),(1500.,0.)))):
        prior=first_region_outer_local(station,0.,circle_sides=360)
        rows.append({'first_station_m':station,'prior_max_a_m':max(p[0] for p in prior),'prior_vertices_m':prior})
        poly(ax,safe_boundary(),face=LIGHT_GREY,edge=GREY)
        poly(ax,prior,face='#c0d4df',edge=BLUE,zorder=5)
        if i:
            ax.add_patch(Circle((-1500,0),1800,fill=False,ec=GOLD,lw=1.2,zorder=3))
        point(ax,(0,0),'$S_1$',(-17,-14))
        ax.text(630,-540,r'$\mathcal{C}_{\rm safe}$',color=GREY,fontsize=12)
        ax.annotate(r'$\overline{U}_1$',xy=(160 if i else 1230,0),xytext=(770,290),
            arrowprops=dict(arrowstyle='->',color=BLUE,lw=.8),color=BLUE,fontsize=12)
        ax.set(xlim=(-80,1580),ylim=(-940,940));axes_style(ax)
        ax.set_xticks([0,500,1000,1500]);ax.set_yticks([-750,-500,-250,0,250,500,750])
        if i: ax.legend(handles=[Line2D([0],[0],color=GOLD,label='目标圆边界')],loc='upper right',fontsize=9)
        poly(z,prior,face='#c0d4df',edge=BLUE,zorder=4)
        if i:
            z.add_patch(Circle((-1500,0),1800,fill=False,ec=GOLD,lw=1.2,zorder=5));z.set(xlim=(275,315),ylim=(-20,20));z.set_xticks([280,300]);z.set_yticks([-20,0,20])
        else:
            z.add_patch(Circle((0,0),1500,fill=False,ec=GOLD,lw=1.2,zorder=5));z.set(xlim=(1460,1520),ylim=(-30,30));z.set_xticks([1460,1480,1500,1520]);z.set_yticks([-20,0,20])
        axes_style(z)
        fig.text(.275 if i==0 else .760,-.025,fr'（{"a" if i==0 else "b"}）$S_1=({int(station[0])},0)$ 米',ha='center',va='top',fontsize=10.5)
    save(fig,'p2_05_target_conditioning','已知首点位置如何收紧候选源区域',
         '首示向均为 0° 时，首点在原点的候选源可延伸至约 1500 米；首点在 (1500,0) 米时，1800 米目标圆将朝外的候选源截短至约 300 米。下方分别放大径向远端。',
         '首验信息与最坏直径目标；几何外包上界',SOURCES,
         notes='使用同一 360 边外切几何模型；下方左图金线为首距离上界圆，下方右图及上方右图金线为目标圆。四圆盘安全域保持一致，它是保守充分区域，并不意味着两个场景的最大安全域相同。',
         recommendation='优先：解释评分二为何可以利用目标圆，及边界场景的评分为何明显更紧。',
         data={'scenarios':rows,'circle_sides':360,'error_deg':1.})


def figure06():
    q=(400.,650.)
    assert guaranteed_reception(q)
    r=np.linspace(5,1500,1000)
    fig,(a,b)=plt.subplots(1,2,figsize=(10.5,4.6))
    fig.subplots_adjust(left=.07,right=.985,bottom=.19,top=.96,wspace=.28)
    wedge(a,(0,0),0,1500,BLUE)
    point(a,(0,0),'$S_1$',(-17,-15));point(a,q,'$q$',(6,7),color=GREEN)
    for rv,lab in ((5,'5'),(1000,'1000'),(1500,'1500')):
        p=(rv*math.cos(E),-rv*math.sin(E))
        a.plot([q[0],p[0]],[q[1],p[1]],lw=.8,color=GOLD if rv==1500 else BLUE,ls='--' if rv==1500 else '-')
        a.scatter(*p,s=16,color=GOLD if rv==1500 else BLUE,zorder=6)
        a.annotate(fr'$r={lab}$',p,(-40,-22) if rv==1500 else (9,-15 if rv==5 else -22),textcoords='offset points',fontsize=9)
    a.set(xlim=(-130,1650),ylim=(-300,1000));axes_style(a);a.set_xticks([0,500,1000,1500]);a.set_yticks([0,250,500,750,1000])
    a.legend(handles=[Line2D([0],[0],color=BLUE,label='5、1000 米端点约束'),Line2D([0],[0],color=GOLD,ls='--',label='1500 米源位置')],loc='upper right',fontsize=8.5)
    vals=[]
    for s,col,ls,label in ((-1,BLUE,'-',r'$\phi=-1^\circ$'),(1,GOLD,'--',r'$\phi=+1^\circ$')):
        ys=np.hypot(q[0]-r*math.cos(E),q[1]-s*r*math.sin(E))/np.maximum(1000,r)
        vals.append(float(ys.max()))
        b.plot(r,ys,color=col,ls=ls,lw=1.4,label=label)
        for rv in (5.,1000.,1500.):
            y=distance(q,(rv*math.cos(E),s*rv*math.sin(E)))/max(1000,rv)
            b.scatter(rv,y,s=22,marker='o',color=col,zorder=5)
    b.axhline(1.,color=INK,lw=1.,ls=(0,(4,3)),label='保证收信边界')
    b.axvline(1000,color=GREY,lw=.8,ls=':')
    b.set(xlim=(-25,1530),ylim=(.58,1.035));b.set_xticks([5,500,1000,1500]);b.set_yticks([.6,.7,.8,.9,1.])
    axes_style(b,xlabel='$r$（米）',ylabel=r'$d_2 / R_{\min}(r)$',equal=False)
    b.legend(loc='lower right',fontsize=9)
    b.text(310,.99,r'$R_{\min}=1000$',ha='center',va='top',fontsize=10)
    b.text(1285,.99,r'$R_{\min}=r$',ha='center',va='top',fontsize=10)
    fig.text(.27,.035,'（a）径向端点与第二检测点',ha='center',va='top',fontsize=10.5)
    fig.text(.785,.035,'（b）距离相对于最小相容半径',ha='center',va='top',fontsize=10.5)
    assert max(vals)<1
    save(fig,'p2_06_radial_endpoints','径向端点约束与首次收信信息',
         '自建安全点 q=(400,650) 米。首次收信提供 R≥r，故第二次距离须与 max(1000,r) 比较；图中两条角端点曲线始终低于 1。',
         '四圆盘安全候选域；径向端点归约证明',SOURCES,
         notes='左侧使用真实 ±1° 示向扇区；5 米处取闭包端点。右侧是距离函数示意，不以有限采样代替四圆盘解析安全证明。',
         recommendation='补充：适合解释为何不用半径 1000 米去约束所有 1500 米源位置。',
         data={'q_m':q,'safe_centers_m':safe_centers(),'guaranteed_reception':True,
               'sample_max_normalized_distances':vals,'sample_count_per_endpoint':len(r)})


def main():
    setup()
    for make in (figure01,figure02,figure03,figure04,figure05,figure06):
        make()


if __name__=='__main__':
    main()
