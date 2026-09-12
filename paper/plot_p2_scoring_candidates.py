"""问题二评分机制候选图；所有评分和裁剪均复用当前生产求解函数。"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
from matplotlib import pyplot as plt
from matplotlib.patches import Arc, ConnectionPatch, Polygon, Rectangle
from matplotlib.lines import Line2D

from p2_candidate_style import (ROOT, PAPER, DEST, BLUE, INK, GREY, GOLD, GREEN,
                                LIGHT_BLUE, LIGHT_GREY, setup, save, axes_style,
                                panel_label, read_json)

sys.path.insert(0, str(ROOT))
from problem2 import solve as model

SOURCES = ['paper/sections/p12.tex', 'problem2/solve.py',
           'problem2/results/selection.json']


def polygon(ax, vertices, color=BLUE, fill=LIGHT_BLUE, label=None, lw=1.25,
            alpha=1., zorder=3, linestyle='-'):
    if len(vertices) < 3:
        return None
    patch = Polygon(vertices, closed=True, edgecolor=color, facecolor=fill,
                    linewidth=lw, label=label, alpha=alpha, zorder=zorder,
                    linestyle=linestyle)
    ax.add_patch(patch)
    return patch


def diameter(ax, vertices, color=INK, text=None, offset=(0, 8), fontsize=10):
    p, q = max(((a,b) for a in vertices for b in vertices),
               key=lambda ab: model.distance(*ab))
    ax.plot([p[0],q[0]], [p[1],q[1]], color=color, lw=1.7, zorder=7)
    ax.scatter([p[0],q[0]], [p[1],q[1]], s=16, c=color, zorder=8)
    if text:
        mid = ((p[0]+q[0])/2, (p[1]+q[1])/2)
        ax.annotate(text, mid, xytext=offset, textcoords='offset points',
                    ha='center', va='bottom', color=color, fontsize=fontsize,
                    bbox=dict(facecolor='white', edgecolor='none', pad=1.5),zorder=12)
    return p,q


def strip_polygon(beta, w1, w2):
    bound = 2000.
    vs = [(-bound,-bound),(bound,-bound),(bound,bound),(-bound,bound)]
    n = (-math.sin(beta),math.cos(beta))
    for normal, off in (((0,1),w1),((0,-1),w1),(n,w2),((-n[0],-n[1]),w2)):
        vs = model.clip_polygon(vs, normal, off)
    return vs


def strip_background(ax, beta, w1, w2, extent=200, legends=True):
    xs = np.array([-extent,extent])
    ax.fill_between(xs, -w1, w1, color=LIGHT_BLUE, alpha=.75, zorder=1,
                    label='第一示向条带' if legends else None)
    ax.plot(xs,[w1,w1],color=BLUE,alpha=.45,lw=.8)
    ax.plot(xs,[-w1,-w1],color=BLUE,alpha=.45,lw=.8)
    d = np.array([math.cos(beta),math.sin(beta)])
    n = np.array([-math.sin(beta),math.cos(beta)])
    rect = [-extent*d-w2*n, extent*d-w2*n, extent*d+w2*n, -extent*d+w2*n]
    polygon(ax, rect, color=GOLD, fill='#f5eee1', alpha=.7, zorder=1,
            lw=.6, label='第二示向条带' if legends else None)
    # Keep both full centre lines above the filled intersection.
    ax.plot(xs,[0,0], '--',color=BLUE,lw=.8,zorder=5)
    ax.plot([-extent*d[0],extent*d[0]],[-extent*d[1],extent*d[1]],
            '--',color=GOLD,lw=.8,zorder=5)


def build_data():
    plan = read_json('problem2/results/selection.json')
    q = tuple(plan['selected']['local_xy_m'])
    first = tuple(plan['first_station_xy_m'])
    error = plan['error_deg']
    e = math.radians(error)
    prior = model.first_region_outer_local(first,plan['first_bearing_deg'],error,
                                            plan['circle_sides'])
    candidate = model.prepare_candidate_region_local(prior,q,error,plan['circle_sides'])
    evaluator = model.ContinuousDiameterEvaluator(prior,error,
                    plan['final_angle_step_deg'],plan['circle_sides'])
    full = evaluator.evaluate(q,analytic_cap_m=model.diameter_bound(q,error),early_stop=False)
    curve = []
    for angle,_ in evaluator.normals:
        poly = model.clip_candidate_observation_local(candidate,angle,evaluator.widened_error)
        curve.append([angle,model.polygon_diameter(poly),bool(poly)])
    assert full['geometric_scan_complete'] and full['scanned_cells']==3600
    assert abs(full['geometric_diameter_upper_bound_m']-max(row[1] for row in curve))<1e-7
    assert abs(full['geometric_diameter_upper_bound_m']-
               plan['selected']['geometric_diameter_upper_bound_m'])<1e-7
    w1 = 1500*math.sin(e)
    r2max = max(model.distance(q,(r*math.cos(e),s*r*math.sin(e)))
                for r in (5.,1500.) for s in (-1,1))
    w2 = r2max*math.sin(e)
    h0 = abs(q[1])-w1
    k0 = max(abs(q[0]-5*math.cos(e)),abs(q[0]-1500))
    beta0 = math.atan2(h0,k0)-e
    payload = dict(q_local_xy_m=list(q), error_deg=error, circle_sides=plan['circle_sides'],
        full_scan=full, scan_curve_angle_deg_diameter_m_nonempty=curve,
        w1_m=w1,w2_m=w2,r2max_m=r2max,h0_m=h0,k0_m=k0,beta0_deg=math.degrees(beta0),
        source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES})
    (DEST/'p2_07_13_scoring_data.json').write_text(
        json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return plan,q,candidate,evaluator,full,np.asarray(curve),w1,w2,beta0


def fig07(d):
    plan,q,candidate,evaluator,full,curve,w1,w2,beta0 = d
    e = math.radians(plan['error_deg'])
    arc = np.linspace(-e,e,100)
    ring = np.c_[1500*np.cos(arc),1500*np.sin(arc)]
    sector = np.vstack(([5*math.cos(e),-5*math.sin(e)],ring,
                        [5*math.cos(e),5*math.sin(e)]))
    fig = plt.figure(figsize=(13.2,5.0))
    gs=fig.add_gridspec(1,2,width_ratios=[2.35,1],wspace=.25)
    left,right=fig.add_subplot(gs[0]),fig.add_subplot(gs[1])
    for ax in (left,right):
        ax.axhspan(-w1,w1,facecolor=LIGHT_GREY,zorder=1,label='条带外包')
        ax.axhline(w1,color=INK,linestyle='--',lw=1)
        ax.axhline(-w1,color=INK,linestyle='--',lw=1)
        polygon(ax,sector,color=BLUE,fill=LIGHT_BLUE,label='首扇区（距离不超过 1500 米）')
        ax.axhline(0,color=GREY,lw=.7,ls=':')
        axes_style(ax)
    left.scatter([0],[0],color=INK,s=22,zorder=6)
    left.annotate('$S_1$',(0,0),xytext=(-8,-20),textcoords='offset points',ha='right')
    left.annotate('',(1500,0),(0,0),arrowprops=dict(arrowstyle='->',color=BLUE,lw=.9))
    left.text(700,60,r'$\varepsilon=1^\circ$',color=BLUE,ha='center')
    left.annotate('',(800,0),(800,w1),arrowprops=dict(arrowstyle='<->',color=INK,lw=.8))
    left.annotate('$w_1$',(800,w1/2),xytext=(8,0),textcoords='offset points',va='center')
    left.set_xlim(-75,1590);left.set_ylim(-235,235)
    left.legend(loc='lower left',fontsize=8.4)
    rect=Rectangle((1465,-39),65,78,fill=False,color=GREY,lw=.7,zorder=8)
    left.add_patch(rect)
    right.set_xlim(1465,1530);right.set_ylim(-39,39)
    right.set_xticks([1475,1500,1525]);right.set_yticks([-25,0,25])
    right.annotate(r'$w_1=1500\sin\varepsilon$',(1490,w1),xytext=(1471,33.2),
                   fontsize=9,color=INK)
    right.annotate('',(1510,0),(1510,w1),
                   arrowprops=dict(arrowstyle='<->',color=INK,lw=.7))
    right.annotate(r'$26.179\ \mathrm{m}$',(1513,w1/2),rotation=90,va='center',fontsize=9)
    for ya,yb in [(39,39),(-39,-39)]:
        con=ConnectionPatch((1530,ya),(1465,yb),coordsA=left.transData,
                    coordsB=right.transData,color='#a0a0a0',lw=.6,zorder=15)
        fig.add_artist(con)
    panel_label(left,'(a) 首示向扇区与等宽条带')
    left.texts[-1].set_position((.5,-.38))
    panel_label(right,'(b) 距离上界处放大')
    save(fig,'p2_07_sector_to_strip','评分一：从扇区到条带',
         '将首示向扇区及1500米距离上界放松为半宽w₁=1500sin1°的条带。右图保持等比例坐标，放大距离上界处的包络关系。',
         '评分方法一：解析条带上界',SOURCES,
         notes='原始扇区仍为±1°。条带向前后无限延伸，绘图仅截取窗口；图中未把条带视为精确首验集U₁。',
         recommendation='适合在评分方法一引入时使用。',data={'w1_m':w1,'error_deg':1.,'distance_upper_m':1500.})


def fig08(d):
    plan,q,candidate,evaluator,full,curve,w1,w2,beta0=d
    poly=strip_polygon(beta0,w1,w2)
    value=model.polygon_diameter(poly)
    assert abs(value-model.diameter_bound(q))<1e-6
    fig,ax=plt.subplots(figsize=(9.8,6.6))
    strip_background(ax,beta0,w1,w2,extent=170)
    polygon(ax,poly,color=INK,fill='#dce7e8',label='保守条带交集',lw=1.35)
    # The two arrowheads mark the endpoints of the longest diagonal itself.
    ends = sorted(max(((a,b) for a in poly for b in poly),
                      key=lambda ab: model.distance(*ab)), key=lambda p:p[0])
    start,end = (np.asarray(p) for p in ends)
    diagonal_direction = (end-start)/value
    diagonal_normal = np.array([-diagonal_direction[1],diagonal_direction[0]])
    dimension_start,dimension_end = start,end
    ax.annotate('',dimension_end,dimension_start,
                arrowprops=dict(arrowstyle='<->',color=INK,lw=1.,
                                shrinkA=0,shrinkB=0),zorder=8)
    label_position = start+.18*(end-start)-4*diagonal_normal
    ax.text(*label_position,r'$A(q)$',ha='center',va='center',fontsize=12,
            rotation=math.degrees(math.atan2(diagonal_direction[1],diagonal_direction[0])),
            rotation_mode='anchor',color=INK,zorder=10)
    ax.scatter([0],[0],c=INK,s=15,zorder=7)
    ax.annotate('$O$',(0,0),xytext=(-10,-15),textcoords='offset points')
    angle_radius = 24.
    ax.add_patch(Arc((0,0),2*angle_radius,2*angle_radius,theta1=0,
                    theta2=math.degrees(beta0),color=GOLD,lw=1.4,zorder=9))
    angle_marker = angle_radius*np.array([math.cos(beta0*.2),math.sin(beta0*.2)])
    ax.annotate(r'$\beta_0$',angle_marker,xytext=(68,5),fontsize=15,
                textcoords='data',color=GOLD,ha='center',va='center',
                arrowprops=dict(arrowstyle='->',color=GOLD,lw=.9,
                                shrinkA=4,shrinkB=2),zorder=10)
    ax.annotate('',(-112,0),(-112,w1),arrowprops=dict(arrowstyle='<->',color=BLUE,lw=.9))
    ax.text(-116,w1/2,'$w_1$',ha='right',va='center',color=BLUE)
    direction=np.array([math.cos(beta0),math.sin(beta0)])
    normal=np.array([-math.sin(beta0),math.cos(beta0)])
    p=-90*direction
    ax.annotate('',p,p+normal*w2,arrowprops=dict(arrowstyle='<->',color=GOLD,lw=.9))
    ax.annotate('$w_2$',p+normal*w2/2,xytext=(-16,-4),textcoords='offset points',color=GOLD)
    for i,v in enumerate(poly):
        ax.scatter(*v,c=INK,s=12,zorder=6)
        ax.annotate(f'$V_{i+1}$',v,xytext=(5,5 if v[1]>0 else -14),textcoords='offset points')
    axes_style(ax,r'$\xi$（米）',r'$\eta$（米）')
    ax.set_xlim(-130,130);ax.set_ylim(-87,87)
    ax.legend(loc='upper left',facecolor='none',framealpha=1.,edgecolor='#a0a0a0')
    save(fig,'p2_08_strip_intersection','评分一：条带交集与解析直径',
         '第一、第二示向分别外包为半宽w₁、w₂的条带。将中心线锐交会角取为保守下界β₀，交集为平行四边形；图中双向尺寸箭头标示长对角线长度，即解析直径上界A(q)。',
         '评分方法一：解析条带上界',SOURCES,
         notes='ξ、η是两条带中心线交点O处的平移示意坐标；夹角取保守下界β₀，图形不是某次实际读数的后验区域，也不是几何外包B的最坏单元。',
         recommendation='最适合解释解析公式分子、分母及直径的几何含义。',
         data={'q_local_xy_m':list(q),'w1_m':w1,'w2_m':w2,'beta0_deg':math.degrees(beta0),
               'analytic_bound_m':value,'strip_polygon_centered_xy_m':poly,
               'long_diagonal_endpoints_xy_m':[p.tolist() for p in (start,end)],
               'dimension_arrow_endpoints_xy_m':[p.tolist() for p in (dimension_start,dimension_end)]})
    # Keep the selected manuscript asset synchronized with its editable candidate.
    (PAPER/'figures'/'p2_08_strip_intersection.pdf').write_bytes(
        (DEST/'p2_08_strip_intersection.pdf').read_bytes())


def fig09(d):
    plan,q,candidate,evaluator,full,curve,w1,w2,beta0=d
    angles=[round(model.bearing((x,0),q),1) for x in (400,900,1450)]
    polys=[model.clip_candidate_observation_local(candidate,a,evaluator.widened_error) for a in angles]
    colors=[GREEN,GOLD,BLUE]
    fig=plt.figure(figsize=(12.8,8.2))
    gs=fig.add_gridspec(2,3,height_ratios=[1.25,1],hspace=.24,wspace=.27)
    ax=fig.add_subplot(gs[0,:])
    polygon(ax,candidate['polygon_local_xy_m'],GREY,LIGHT_GREY,label='$Q(q_*)$',lw=1.)
    ax.scatter([0,q[0]],[0,q[1]],c=INK,s=20,zorder=8)
    ax.annotate('$S_1$',(0,0),xytext=(-12,-15),textcoords='offset points')
    ax.annotate('$S(q_*)$',q,xytext=(8,2),textcoords='offset points')
    for i,(angle,poly,col) in enumerate(zip(angles,polys,colors)):
        polygon(ax,poly,col,col,alpha=.8,label=f'$P_{{k_{i+1}}}$')
        direction=np.array([math.cos(math.radians(angle)),math.sin(math.radians(angle))])
        target=np.array(q)-q[1]/direction[1]*direction
        ax.plot([q[0],target[0]],[q[1],target[1]],color=col,lw=1.)
        # Keep the numeric readings clear of their centre lines and each other.
        fraction,offset,alignment=[(.50,(-12,9),'right'),
                                   (.45,(14,-12),'left'),
                                   (.55,(10,9),'left')][i]
        midpoint=(1-fraction)*np.array(q)+fraction*target
        ax.annotate(rf'$\psi_{{k_{i+1}}}={angle:.1f}^\circ$',midpoint,
                    xytext=offset,textcoords='offset points',color=col,
                    ha=alignment,va='bottom',fontsize=10.5)
    axes_style(ax)
    ax.set_xlim(-80,1570);ax.set_ylim(-80,645)
    ax.legend(loc='upper left',ncol=4,fontsize=8.5,
              facecolor='none',framealpha=1.,edgecolor='#a0a0a0')
    for i,(poly,col) in enumerate(zip(polys,colors)):
        zoom=fig.add_subplot(gs[1,i]);coords=np.array(poly)
        polygon(zoom,candidate['polygon_local_xy_m'],GREY,LIGHT_GREY,lw=.7)
        polygon(zoom,poly,col,'#edf3f2' if i==0 else '#f2eadc' if i==1 else LIGHT_BLUE,lw=1.4)
        diameter(zoom,poly)
        zoom.text(.5,.89,f'$D_{{k_{i+1}}}={model.polygon_diameter(poly):.2f}$ 米',
                  transform=zoom.transAxes,ha='center',va='center',
                  fontsize=12.5,fontweight='normal',color=INK,zorder=12)
        center=(coords.max(axis=0)+coords.min(axis=0))/2
        half=max(43,(coords[:,0].max()-coords[:,0].min())*.66)
        zoom.set_xlim(center[0]-half,center[0]+half)
        zoom.set_ylim(-half*.7,half*.7)
        axes_style(zoom)
        panel_label(zoom,f'({chr(97+i)}) 第 {i+1} 组读数单元')
        zoom.texts[-1].set_position((.5,-.31))
    save(fig,'p2_09_reading_cells','评分二：同一候选点的读数单元',
         '对固定推荐点，先构造与第二读数无关的外包Q(q*)，再用不同格中心的增宽约束裁出Pₖ；下方放大三组单元外包及其直径。',
         '评分方法二：几何外包上界',SOURCES,
         notes='圆外切360边、读数步长0.1°、评分半角1.05°。示例三格不是全部单元，不能以其最大直径代替完整B。所有图中多边形均为外包，不是精确U。',
         recommendation='适合首次解释第二读数分格、Q与Pₖ的关系。',
         data={'q_local_xy_m':list(q),'cell_centers_deg':angles,'cell_polygons':polys,
               'cell_diameters_m':[model.polygon_diameter(p) for p in polys]})
    # Manuscript figure 09 is generated by plot_p2_reading_cells_outer_bounds.py.
    # Keep this earlier three-cell layout as a candidate without replacing it.


def fig10(d):
    plan,q,candidate,evaluator,full,curve,w1,w2,beta0=d
    base=plan['error_deg'];wide=evaluator.widened_error
    width0,near0=model._observation_limits(candidate,base)
    width1,near1=model._observation_limits(candidate,wide)
    fig,axs=plt.subplots(1,3,figsize=(13.2,4.6))
    # ξ is the coordinate along a cell centre; these show individual moving constraints.
    xx=np.linspace(695,705,200)
    for ax in axs:
        ax.set_axisbelow(True)
    a=axs[0]
    y0=xx*np.tan(math.radians(base));y1=xx*np.tan(math.radians(wide))
    a.fill_between(xx,8,y1,facecolor=LIGHT_GREY,zorder=1)
    a.fill_between(xx,8,y0,facecolor=LIGHT_BLUE,zorder=2)
    a.plot(xx,y1,color=GOLD,lw=1.4,label=rf'$1.05^\circ$')
    a.plot(xx,y0,color=BLUE,lw=1.4,label=rf'$1^\circ$')
    a.set_xlim(695,705);a.set_ylim(8,18)
    a.annotate('',(700,float(700*np.tan(math.radians(base)))),
                (700,float(700*np.tan(math.radians(wide)))),
                arrowprops=dict(arrowstyle='<->',color=INK,lw=.7))
    a.legend(loc='upper left')
    axes_style(a,r'$\xi$（米）',r'$\eta$（米）')
    panel_label(a,'(a) 扇区半角')
    a=axs[1]
    a.axhspan(13,width1,facecolor=LIGHT_GREY,zorder=1)
    a.axhspan(13,width0,facecolor=LIGHT_BLUE,zorder=2)
    a.axhline(width1,color=GOLD,lw=1.4,label=f'增宽后 {width1:.3f} 米')
    a.axhline(width0,color=BLUE,lw=1.4,label=f'原半宽 {width0:.3f} 米')
    a.set_xlim(695,705);a.set_ylim(13,23)
    a.annotate('',(700,width0),(700,width1),arrowprops=dict(arrowstyle='<->',color=INK,lw=.7))
    a.legend(loc='upper left')
    axes_style(a,r'$\xi$（米）',r'$\eta$（米）')
    panel_label(a,'(b) 条带半宽')
    a=axs[2]
    v0=(near0-5)*1000;v1=(near1-5)*1000
    a.axvspan(v1,-.66,facecolor=LIGHT_GREY,zorder=1)
    a.axvspan(v0,-.66,facecolor=LIGHT_BLUE,zorder=2)
    a.axvline(v1,color=GOLD,lw=1.4,label=rf'$5\cos1.05^\circ$')
    a.axvline(v0,color=BLUE,lw=1.4,label=rf'$5\cos1^\circ$')
    a.set_xlim(-.96,-.66);a.set_ylim(-.15,.15)
    a.annotate('',(v1,-.07),(v0,-.07),arrowprops=dict(arrowstyle='<->',color=INK,lw=.7))
    a.legend(loc='upper left',fontsize=8.8)
    axes_style(a,r'$(\xi-5\,\mathrm{m})$（毫米）',r'$\eta$（毫米）')
    panel_label(a,'(c) 前向投影下界')
    fig.subplots_adjust(wspace=.32,bottom=.25)
    save(fig,'p2_10_synchronous_widening','评分二：三类约束同步增宽',
         '读数步长0.1°对应半步δ=0.05°。在格中心方向的局部坐标中，分别放大扇区上边界、条带上边界和5米近区的前向投影下界；蓝色为原约束保留侧，浅灰为同步放松的增量。',
         '评分方法二：几何外包上界',SOURCES,
         notes='这是三个独立约束的局部示意，不是三个后验多边形；扇区和条带另一侧同样增宽。ξ沿格中心、η为垂直方向，右图使用毫米单位。数值使用当前推荐点的R₂、Rout；实际读数后的误差半角仍为1°。',
         recommendation='适合说明为什么仅扫描未增宽的有限读数不够。',
         data={'base_error_deg':base,'cell_half_error_deg':wide,
               'strip_half_width_original_m':width0,'strip_half_width_widened_m':width1,
               'near_projection_original_m':near0,'near_projection_widened_m':near1,
               'second_distance_upper_m':candidate['second_distance_upper_m'],
               'outer_distance_upper_m':candidate['outer_distance_upper_m']})


def fig11(d):
    plan,q,candidate,evaluator,full,curve,w1,w2,beta0=d
    fig=plt.figure(figsize=(12.4,5.6))
    gs=fig.add_gridspec(1,2,width_ratios=[2.1,1],wspace=.28)
    ax=fig.add_subplot(gs[0]);zoom=fig.add_subplot(gs[1])
    b=full['geometric_diameter_upper_bound_m'];angle=full['worst_cell_center_local_deg']
    for a in (ax,zoom):
        a.plot(curve[:,0],curve[:,1],color=BLUE,lw=1.4,label=r'$D_k=\mathrm{diam}\,P_k$')
        a.axhline(b,color=INK,lw=1.,ls='--',label=r'$B=\max_k D_k$')
        a.scatter([angle],[b],s=26,c=GOLD,edgecolor='white',lw=.4,zorder=5)
        axes_style(a,r'第二读数格中心 $\psi_k$（度）','单元外包直径 $D_k$（米）',equal=False)
    ax.set_xlim(0,360);ax.set_ylim(-3,124);ax.set_xticks(range(0,361,60))
    ax.legend(loc='upper left')
    ax.annotate(f'$B={b:.3f}$ 米',(angle,b),xytext=(187,115),
                arrowprops=dict(arrowstyle='-',lw=.7,color=GREY),fontsize=10)
    zoom.set_xlim(angle-4,angle+2);zoom.set_ylim(90,116)
    zoom.set_xticks([314,316,318,320])
    zoom.annotate(rf'$\psi_{{k_*}}={angle:.1f}^\circ$',(angle,b),
                xytext=(314.2,114),arrowprops=dict(arrowstyle='-',lw=.7,color=GREY),fontsize=9)
    panel_label(ax,'(a) 全部 3600 个单元的完整扫描')
    panel_label(zoom,'(b) 最坏单元附近放大')
    fig.subplots_adjust(bottom=.25)
    save(fig,'p2_11_worst_reading_scan','评分二：完整扫描与最坏单元',
         f'固定推荐点q*，完整扫描3600个增宽单元；最大直径B={b:.4f}米，发生于格中心{angle:.1f}°。右图放大最大值附近。',
         '评分方法二：几何外包上界',SOURCES,
         notes='空单元按求解器惯例记0；无提前停止，B不是部分最大值bₜ，不是真实未知最坏值J。图示是外包直径随格中心的曲线，不是源位置或读数的概率分布。',
         recommendation='两种评分展示中优先选择，可直接支撑B=max diam(Pₖ)。',
         data={'q_local_xy_m':list(q),'full_scan_cells':full['scanned_cells'],
               'B_m':b,'worst_cell_center_deg':angle,
               'curve_file':'p2_07_13_scoring_data.json'})


def fig12(d):
    plan,q,candidate,evaluator,full,curve,w1,w2,beta0=d
    def a(beta):
        return 2*np.sqrt(w1*w1+w2*w2+2*w1*w2*np.cos(beta))/np.sin(beta)
    fig=plt.figure(figsize=(11.6,7.2))
    gs=fig.add_gridspec(2,3,height_ratios=[1.55,1],hspace=.32,wspace=.25)
    ax=fig.add_subplot(gs[0,:])
    degrees=np.linspace(10,90,400)
    ax.plot(degrees,a(np.radians(degrees)),color=BLUE,lw=1.7)
    samples=[math.degrees(beta0),60.,90.]
    colors=[BLUE,GOLD,GREEN]
    for i,(deg,col) in enumerate(zip(samples,colors)):
        value=float(a(math.radians(deg)))
        ax.scatter([deg],[value],c=col,s=28,zorder=5)
        ax.plot([deg,deg],[0,value],':',lw=.8,color=col)
        offset=(-8,17) if i==0 else (-5,13) if i==1 else (-8,15)
        ax.annotate(f'{deg:.2f}°，{value:.2f} 米',(deg,value),xytext=offset,
                    textcoords='offset points',color=col,fontsize=9,
                    ha='right' if i==2 else 'left')
    axes_style(ax,r'锐交会角 $\beta$（度）','固定半宽的解析上界（米）',equal=False)
    ax.set_xlim(10,93);ax.set_ylim(0,520)
    ax.text(.97,.94,rf'$w_1={w1:.3f}\ \mathrm{{m}},\quad w_2={w2:.3f}\ \mathrm{{m}}$',
            transform=ax.transAxes,ha='right',va='top',fontsize=10)
    for i,(deg,col) in enumerate(zip(samples,colors)):
        mini=fig.add_subplot(gs[1,i]);beta=math.radians(deg)
        poly=strip_polygon(beta,w1,w2)
        polygon(mini,poly,col,LIGHT_BLUE if i==0 else '#f5eddf' if i==1 else '#e7f1ed')
        diameter(mini,poly,color=col)
        mini.axhline(0,lw=.6,ls=':',color=GREY)
        axes_style(mini,r'$\xi$（米）',r'$\eta$（米）')
        mini.set_xlim(-95,95);mini.set_ylim(-47.5,47.5)
        mini.set_xticks([-75,0,75]);mini.set_yticks([-25,0,25])
        panel_label(mini,rf'({chr(97+i)}) $\beta={deg:.2f}^\circ$')
        mini.texts[-1].set_position((.5,-.36))
    save(fig,'p2_12_crossing_angle','评分一：交会夹角对条带直径的影响',
         '固定推荐点对应的两条带半宽，仅改变中心线锐交会角，解析直径随夹角增大而减小。下方以相同坐标尺度比较夹角下界β₀、60°、90°三组条带交集。',
         '评分方法一：解析条带上界',SOURCES,
         notes='固定w₁、w₂的参数敏感性图，不是不同第二点q的实际评分曲线，也不宣称60°或90°构型在安全域内必可达。下方均为条带中心交点处的局部示意坐标。',
         recommendation='作为图08的替代或补充，解释改善交会角的动机。',
         data={'w1_m':w1,'w2_m':w2,'angles_deg':samples,
               'diameters_m':[float(a(math.radians(v))) for v in samples]})


def fig13(d):
    plan,q,candidate,evaluator,full,curve,w1,w2,beta0=d
    angle=full['worst_cell_center_local_deg']
    outer=model.clip_candidate_observation_local(candidate,angle,evaluator.widened_error)
    inner=model.clip_candidate_observation_local(candidate,angle,plan['error_deg'])
    # Verify legal illustrative source and containment under the shared clipping model.
    source=(1450.,0.)
    assert abs(model.angular_error(angle,model.bearing(source,q)))<plan['error_deg']
    assert model.distance(source,q)<=1500 and model.distance(source,(0,0))<=1500
    assert model.polygon_diameter(inner)<=model.polygon_diameter(outer)+1e-8
    for a,b in zip(outer,outer[1:]+outer[:1]):
        assert all((b[0]-a[0])*(v[1]-a[1])-(b[1]-a[1])*(v[0]-a[0])>=-1e-6
                   for v in inner)
    fig=plt.figure(figsize=(12.5,5.7))
    gs=fig.add_gridspec(1,2,width_ratios=[1.7,1],wspace=.27)
    ax=fig.add_subplot(gs[0]);zoom=fig.add_subplot(gs[1])
    for a in (ax,zoom):
        polygon(a,outer,GOLD,'#f3e9d6',label=r'评分单元外包 $P_{k_*}$（$1.05^\circ$）')
        polygon(a,inner,BLUE,LIGHT_BLUE,label=r'同中心读数外包（$1^\circ$）')
        axes_style(a)
    value=model.polygon_diameter(outer)
    diameter(ax,outer,color=GOLD,text=f'$D(P_{{k_*}})={value:.3f}$ 米',offset=(0,-28),fontsize=9.5)
    diameter(ax,inner,color=BLUE,text=f'$D={model.polygon_diameter(inner):.3f}$ 米',
             offset=(0,12),fontsize=9.5)
    ax.set_xlim(1388,1515);ax.set_ylim(-50,50)
    ax.legend(loc='upper left',fontsize=8.7)
    # The upper-left vertex is where 0.05° widening is visible without geometric exaggeration.
    left=min(outer,key=lambda p:p[0])
    bounds=(left[0]-1.5,left[0]+4.,left[1]-2.,left[1]+3.5)
    zoom.set_xlim(bounds[0],bounds[1]);zoom.set_ylim(bounds[2],bounds[3])
    zoom.ticklabel_format(useOffset=False,style='plain',axis='x')
    zoom.set_xticks([1400,1402]);zoom.set_yticks([23,25,27])
    ax.add_patch(Rectangle((bounds[0],bounds[2]),bounds[1]-bounds[0],bounds[3]-bounds[2],
                          fill=False,edgecolor=GREY,lw=.7,zorder=9))
    for ya,yb in [(bounds[3],bounds[3])]:
        fig.add_artist(ConnectionPatch((bounds[1],ya),(bounds[0],yb),
            coordsA=ax.transData,coordsB=zoom.transData,color='#a0a0a0',lw=.6,zorder=15))
    panel_label(ax,rf'(a) 固定读数 $\psi={angle:.1f}^\circ$')
    panel_label(zoom,'(b) 单元边界局部放大')
    save(fig,'p2_13_cell_and_observation','评分外包与正常读数外包',
         f'在完整扫描的最坏格中心{angle:.1f}°处，对比1.05°评分单元外包与同中心1°正常读数外包；右图放大外包边界差异。',
         '评分方法二：几何外包上界',SOURCES,
         notes='同中心读数是固定合法读数的几何演示，可由自建源(1450,0)米、接收半径1500米产生；不是selection.json所保存的304.332489°自建观测。两者都是共享模型外包，均不等于精确U；图中的单次外包直径不是J。',
         recommendation='适合放在半步增宽公式之后，直观区分评分阶段与获得正常读数之后。',
         data={'q_local_xy_m':list(q),'cell_center_and_fixed_reading_deg':angle,
               'cell_polygon':outer,'fixed_reading_polygon':inner,
               'cell_diameter_m':value,'fixed_reading_outer_diameter_m':model.polygon_diameter(inner),
               'illustrative_legal_source_xy_m':list(source),'illustrative_radius_m':1500.})


def main():
    setup()
    data=build_data()
    for plot in (fig07,fig08,fig09,fig10,fig11,fig12,fig13):
        plot(data)


if __name__=='__main__':
    main()
