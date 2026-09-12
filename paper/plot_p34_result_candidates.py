"""Render frozen local results only; no solver runs or platform requests."""
from __future__ import annotations
import hashlib
import json
import math
from statistics import mean
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from figure_candidate_style import (ROOT, DEST, COLORS as C, BRANCH_COLORS as BC,
    BRANCH_LABELS as BL, setup, tidy, legend, save, read)

SPLITS = [('development_v3','开发集',384),('holdout_v3','留出集',512),('stress_v3','压力集',256)]
DATA = {}
AUDIT = {'scope':'冻结的本地自建案例，非平台正式测试；所有源真值仅用于事后统计。','groups':[],'sources':[]}

def branch(p,k):
    return {'original':f'problem{p}.policy:SearchPolicy',
            'selected':f'problem{p}.speed_policy:SearchPolicy',
            'teammate':'teammate',
            'previous':'problem4.experiments_v3.posterior:Shared21Policy'}[k]

def load_data():
    for p in (3,4):
        for split,label,n in SPLITS:
            path=f'validation/speed_v4/p{p}_{split}.json'
            d=read(path)['results'][str(p)]
            DATA[p,split]=d
            AUDIT['sources'].append({'path':path,'sha256':hashlib.sha256((ROOT/path).read_bytes()).hexdigest()})
            reference=None
            for key,result in d.items():
                rows=result['episodes']
                assert len(rows)==n and result['summary']['cases']==n
                identities={r['case_id']:r['case_sha256'] for r in rows}
                if reference is None: reference=identities
                assert reference==identities, 'Branches must contain the exact same cases'
                for r in rows:
                    assert r['cleared_count']>0
                    assert math.isclose(r['cleared_fraction'],r['cleared_count']/r['source_count'],abs_tol=1e-12)
                    assert math.isclose(r['average_clear_time_s'],r['actual_exit_time_s']/r['cleared_count'],abs_tol=1e-8)
                    time=r['movement_m']/5+5*r['measure']+r['switch']+3*r['failed_clear']+5*r['cleared_count']
                    assert math.isclose(time,r['actual_exit_time_s'],abs_tol=1e-6)
                    assert r['certified_full_clear'] and r['independent_public_completion']['certified']
                    assert r['cleared_count']==r['source_count']
                mu=mean(r['average_clear_time_s'] for r in rows)
                assert math.isclose(mu,result['summary']['mean_seconds_per_source'],abs_tol=1e-8)
                AUDIT['groups'].append({'problem':p,'split':split,'branch':key,'cases':n,
                    'cleared_sources':sum(r['cleared_count'] for r in rows),
                    'sources':sum(r['source_count'] for r in rows),'mean_seconds_per_source':mu,
                    'all_cleared_cases':sum(r['cleared_fraction']==1 for r in rows)})

def rows(p,split='holdout_v3',k='selected'):
    return DATA[p,split][branch(p,k)]['episodes']

def source_list(all_splits=True):
    return [f'validation/speed_v4/p{p}_{s}.json' for p in (3,4)
            for s,_,_ in (SPLITS if all_splits else SPLITS[1:2])]

def metric_strip(fig,ax,p):
    ax.axis('off')
    ax.text(0,.95,'指标一：清除比例',va='top',fontsize=10)
    for i,(s,label,n) in enumerate(SPLITS):
        ax.text((i+.5)/3,.4,f'{label}  100%\n{n}/{n}例全清',ha='center',va='center',fontsize=8.7,
            bbox=dict(boxstyle='square,pad=.45',fc='#F0F4F1',ec='#D0D8D2',lw=.55))

def local_metrics():
    fig,axes=plt.subplots(1,2,figsize=(8.2,5.3))
    for ax,p in zip(axes,(3,4)):
        samples=[np.array([r['average_clear_time_s'] for r in rows(p,s)]) for s,_,_ in SPLITS]
        parts=ax.violinplot(samples,positions=[1,2,3],widths=.67,showextrema=False)
        for body,col in zip(parts['bodies'],[C['blue'],C['green'],C['peach']]):
            body.set(facecolor=col,edgecolor=col,alpha=.32,linewidth=.6)
        bp=ax.boxplot(samples,positions=[1,2,3],widths=.15,patch_artist=True,showfliers=True,
            boxprops=dict(facecolor='white',edgecolor='#76828B',linewidth=.8),
            medianprops=dict(color='#4A5862',linewidth=1.1),
            whiskerprops=dict(color='#89949B',linewidth=.7),capprops=dict(color='#89949B',linewidth=.7),
            flierprops=dict(marker='.',markersize=2,markerfacecolor='#99A4AC',markeredgecolor='none',alpha=.55))
        ymax=max(max(x) for x in samples)
        for i,x in enumerate(samples,1):
            mu=float(np.mean(x));ax.scatter(i,mu,marker='D',s=25,color=C['blue'],edgecolors='white',lw=.6,zorder=5)
            ax.text(i,ymax*1.05,f'均值 {mu:.2f}',ha='center',fontsize=9)
        ax.set(xticks=[1,2,3],xticklabels=[f'{l}\n{n}例' for _,l,n in SPLITS],
               ylabel='指标二：平均定位清除时间 /（秒/源）',ylim=(0,ymax*1.15),
               title=f'({"a" if p==3 else "b"}) 问题{"三" if p==3 else "四"}：本文方案')
        tidy(ax)
    fig.subplots_adjust(left=.085,right=.985,top=.93,bottom=.37,wspace=.26)
    for p,ax in zip((3,4),axes):
        box=ax.get_position();metric_strip(fig,fig.add_axes([box.x0,.145,box.width,.14]),p)
    legend(fig,[Line2D([],[],marker='D',color=C['blue'],linestyle='',markersize=5),
        Line2D([],[],color='#4A5862',lw=1.2),Patch(facecolor='#D8E2E8',edgecolor='#A6B8C4')],
        ['逐例耗时的均值','箱内横线：中位数','外形：样本分布'],y=.066,ncol=3)
    fig.text(.5,.025,'本地自建测试；清除比例逐例为100%，并通过独立完成核验。箱体为四分位范围。',ha='center',fontsize=8.3)
    save(fig,'01_local_two_metrics','本地测试的两项实际指标',
        '问题三、四本文方案在开发、留出与压力集合中的清除比例和平均定位清除时间分布。各例先计算 T/Nc，图中菱形再对案例取均值；箱体为25%至75%分位，须为1.5倍四分位距内的最远样本，散点为离群值，小提琴仅作平滑分布显示。',
        source_list(),'推荐作为本地实验主结果图；清除比例不另占整张图。',
        '不是正式测试成绩；正式两指标为 Nc/N 和 T/Nc，220/400阈值通过率不是清除比例。')

def branch_comparison():
    fig,axes=plt.subplots(1,2,figsize=(8.2,4.7))
    for ax,p in zip(axes,(3,4)):
        order=['original','teammate','selected'] if p==3 else ['original','previous','teammate','selected']
        w=.74/len(order)
        for j,k in enumerate(order):
            values=[mean(r['average_clear_time_s'] for r in rows(p,s,k)) for s,_,_ in SPLITS]
            x=np.arange(3)+(j-(len(order)-1)/2)*w
            bars=ax.bar(x,values,width=w*.89,color=BC[k],edgecolor='#879098',linewidth=.35)
            if k=='selected':
                for xx,v in zip(x,values):ax.text(xx,v+8,f'{v:.1f}',ha='center',va='bottom',fontsize=8.5)
        threshold=220 if p==3 else 400
        ax.axhline(threshold,color='#A0A6AB',lw=.8,ls=(0,(4,3)))
        ax.text(.02,.98,f'本地目标：{threshold} 秒/源',transform=ax.transAxes,va='top',fontsize=8.5,color='#737C83')
        ax.set(xticks=range(3),xticklabels=[f'{l}\n{n}例' for _,l,n in SPLITS],
            ylabel='平均定位清除时间 /（秒/源）',ylim=(0,390 if p==3 else 650),
            title=f'({"a" if p==3 else "b"}) 问题{"三" if p==3 else "四"}：同案例对照')
        tidy(ax)
        ax.text(.5,-.23,'清除比例：所有图示方案、集合均为 100%',transform=ax.transAxes,
            ha='center',fontsize=9,bbox=dict(fc='#F0F4F1',ec='#CAD3CD',lw=.55,pad=5))
    legend(fig,[Patch(facecolor=BC[k],edgecolor='#9CA4AA',lw=.4) for k in ['original','previous','teammate','selected']],
        [BL[k] for k in ['original','previous','teammate','selected']],ncol=4,y=.068)
    fig.text(.5,.025,'本地自建测试，非官方成绩；虚线是自定速度目标。第三问未单列与本文等价的上一轮实验方案。',ha='center',fontsize=8)
    fig.subplots_adjust(left=.085,right=.985,top=.91,bottom=.32,wspace=.25)
    save(fig,'02_metrics_comparison_bars','两项指标的方案对照：柔和分组柱图',
        '同一模拟器、相同案例和计费规则下的冻结方案比较。所有图示分支清除比例均100%，柱高为逐例T/Nc的均值；220/400秒每源虚线仅为本地优化目标。',
        source_list(),'可替换正文原 search_comparison 图；与01按篇幅二选一，或一张主文一张备选。')

def paired_results():
    fig,axes=plt.subplots(1,2,figsize=(8.2,4.4))
    pairs={}
    for ax,p in zip(axes,(3,4)):
        old={r['case_id']:r for r in rows(p,k='original')}
        new=rows(p)
        x=np.array([old[r['case_id']]['average_clear_time_s'] for r in new]); y=np.array([r['average_clear_time_s'] for r in new])
        upper=math.ceil(max(max(x),max(y))/50)*50;lower=max(0,math.floor(min(min(x),min(y))/50)*50)
        ax.fill_between([lower,upper],[lower,upper],lower,color='#F1F5F2',zorder=0)
        ax.plot([lower,upper],[lower,upper],color='#A5ABAF',lw=1,ls=(0,(4,3)),zorder=1)
        faster=y<x-1e-8
        ax.scatter(x[faster],y[faster],s=12,c=C['blue'],alpha=.62,edgecolors='white',linewidths=.2)
        ax.scatter(x[~faster],y[~faster],s=14,c=C['peach'],alpha=.85,edgecolors='white',linewidths=.25)
        ax.set(xlim=(lower,upper),ylim=(lower,upper),xlabel='原默认方案 /（秒/源）',ylabel='本文方案 /（秒/源）',
            title=f'({"a" if p==3 else "b"}) 问题{"三" if p==3 else "四"}：留出集512例')
        ax.set_aspect('equal');tidy(ax,'both')
        diff=float(np.mean(x-y)); ratio=diff/float(np.mean(x))*100
        ax.text(.04,.96,f'均值减少 {diff:.2f} 秒/源\n相对减少 {ratio:.2f}%',transform=ax.transAxes,ha='left',va='top',fontsize=9,
            bbox=dict(fc='white',ec='#D2D7DA',lw=.5,pad=5))
        ax.text(.5,-.20,f'{sum(faster)}例更快  ·  {sum(~faster)}例更慢',ha='center',transform=ax.transAxes,fontsize=9.5)
        pairs[str(p)]={'faster':int(sum(faster)),'slower':int(sum(~faster)),'mean_saving':diff}
    legend(fig,[Line2D([],[],marker='o',ls='',color=C['blue'],markersize=5),Line2D([],[],marker='o',ls='',color=C['peach'],markersize=5),Line2D([],[],color='#A5ABAF',ls='--',lw=1)],
        ['本文方案更快','本文方案更慢','两方案耗时相同'],ncol=3,y=.06)
    fig.text(.5,.014,'每个点对应同一个本地案例；浅绿区域表示本文方案更快。两方案均全部清除并通过完成核验。',ha='center',fontsize=8)
    fig.subplots_adjust(left=.09,right=.985,top=.9,bottom=.28,wspace=.28)
    AUDIT['paired_vs_original']=pairs
    save(fig,'03_paired_case_comparison','留出案例的逐例速度比较',
        '两问各512个冻结留出案例的配对耗时。横纵坐标均为每例T/Nc；对角线以下表示本文更快。源真值只用于事后确认全清。',
        source_list(False),'用于解释均值改善不等于每一个案例都改善；不重复放入多张均值图。')

def source_count_results():
    fig,axes=plt.subplots(1,2,figsize=(8.2,4.2))
    for ax,p in zip(axes,(3,4)):
        all_rows=rows(p)
        groups=[[r['average_clear_time_s'] for r in all_rows if r['source_count']==n] for n in range(10,17)]
        bp=ax.boxplot(groups,positions=range(10,17),widths=.52,patch_artist=True,showfliers=True,
            boxprops=dict(fc='#DDE7EC',ec='#879FAF',lw=.7),medianprops=dict(color='#5F7585',lw=1),
            whiskerprops=dict(color='#9DAAB2',lw=.6),capprops=dict(color='#9DAAB2',lw=.6),
            flierprops=dict(marker='.',markersize=3,markerfacecolor='#B8C3CA',markeredgecolor='none'))
        mus=[mean(g) for g in groups]
        ax.plot(range(10,17),mus,'o-',color=C['blue'],ms=4,mec='white',mew=.5,lw=1.3)
        ax.set(xticks=range(10,17),xticklabels=[f'{n}\n({len(g)}例)' for n,g in zip(range(10,17),groups)],
            xlabel='本地案例源总数 / 个（仅用于事后分组）',ylabel='平均定位清除时间 /（秒/源）',
            title=f'({"a" if p==3 else "b"}) 问题{"三" if p==3 else "四"}：留出集')
        ax.set_ylim(0,ax.get_ylim()[1]*1.08);tidy(ax)
        for i in (0,6):ax.annotate(f'{mus[i]:.2f}',(10+i,mus[i]),xytext=(4 if i==0 else -4,10),
            ha='left' if i==0 else 'right',textcoords='offset points',fontsize=8.5)
    legend(fig,[Line2D([],[],marker='o',color=C['blue'],lw=1.3,markersize=4),Patch(fc='#DDE7EC',ec='#879FAF',lw=.7)],
        ['各源数组的平均耗时','箱体：25%至75%分位'],ncol=2,y=.075)
    fig.text(.5,.025,'全部案例清除比例均100%；不同源数组由不同案例组成，图示为相关性，不能解释为单一因素的因果效应。',ha='center',fontsize=7.8)
    fig.subplots_adjust(left=.085,right=.985,top=.91,bottom=.30,wspace=.26)
    save(fig,'04_time_by_source_count','源数量与每源耗时的关系',
        '冻结留出案例按真实源总数事后分组，展示逐例T/Nc的分布与组均值。图示与固定搜索成本被更多源分摊的机制一致，但不控制其他场景差异，不能作因果结论。',
        source_list(False),'用于本地结果分析，解释少源场景为何每源用时更高。')

def time_budget():
    names=['移动','检测','切换频道','失败清除','成功清除']
    colors=[C['blue'],C['green'],C['peach'],C['purple'],C['gray']]
    fig,axes=plt.subplots(1,2,figsize=(8.2,4.15))
    for ax,p in zip(axes,(3,4)):
        order=['original','teammate','selected'] if p==3 else ['original','previous','teammate','selected']
        comps=[]
        for k in order:
            rr=rows(p,k=k)
            vals=[mean(v for v in vv) for vv in zip(*[(r['movement_m']/5/r['cleared_count'],r['measure']*5/r['cleared_count'],
                r['switch']/r['cleared_count'],r['failed_clear']*3/r['cleared_count'],5.) for r in rr])]
            assert math.isclose(sum(vals),mean(r['average_clear_time_s'] for r in rr),abs_tol=1e-8)
            comps.append(vals)
        y=np.arange(len(order));left=np.zeros(len(order))
        for j,(name,col) in enumerate(zip(names,colors)):
            widths=np.array([v[j] for v in comps]);ax.barh(y,widths,left=left,height=.52,color=col,edgecolor='white',lw=.55)
            if j<2:
                for yy,l,w in zip(y,left,widths):ax.text(l+w/2,yy,f'{w:.1f}',ha='center',va='center',fontsize=9,color='#35434D')
            left+=widths
        for yy,total in zip(y,left):ax.text(total+5,yy,f'{total:.2f}',va='center',fontsize=9)
        ax.set(yticks=y,yticklabels=[BL[k] for k in order],xlabel='平均定位清除时间 /（秒/源）',xlim=(0,max(left)*1.19),
            title=f'({"a" if p==3 else "b"}) 问题{"三" if p==3 else "四"}：留出集512例')
        ax.invert_yaxis();tidy(ax,'x')
        selected=comps[-1]
        ax.text(.5,-.30,f'本文：移动占 {selected[0]/sum(selected)*100:.1f}%  ·  检测占 {selected[1]/sum(selected)*100:.1f}%',
            ha='center',transform=ax.transAxes,fontsize=9)
    legend(fig,[Patch(fc=c,ec='#ADB4B9',lw=.35) for c in colors],names,ncol=5,y=.078)
    fig.text(.5,.025,'各分项先除以该例清除数，再对案例取均值；包含最后一次清除后的覆盖确认时间。本地结果，非官方成绩。',ha='center',fontsize=7.8)
    fig.subplots_adjust(left=.135,right=.985,top=.90,bottom=.34,wspace=.40)
    save(fig,'05_time_cost_breakdown','平均定位清除时间的构成',
        '留出集各方案的计费时间分解：移动L/5、检测5Nm、切频Ns、失败清除3Nf及成功清除5Nc。每项先除Nc再对案例取均值，分项之和与退出总时间对应的均值严格一致。',
        source_list(False),'推荐用于解释时间瓶颈；比额外一张阈值通过率图更有分析价值。')

def main():
    setup();load_data()
    local_metrics();branch_comparison();paired_results();source_count_results();time_budget()
    (DEST/'data_audit.json').write_text(json.dumps(AUDIT,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Generated 01–05. Verified case identity, two metrics, completion evidence and time decomposition for every plotted episode.')

if __name__=='__main__':main()
