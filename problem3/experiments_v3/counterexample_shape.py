"""Untuned misleading-ring counterexamples, including identical forced prefixes."""
from benchmark import *
import random
from problem3.experiments_v3.shape_prior import AnnularShapePolicy,AnnularNegativePolicy

def cases():
    answer=[]
    for index in range(96):
        rng=random.Random(9807000+index)
        family=('outer_then_inner','outer_then_second_ring','outer_then_offset_cluster')[index%3]
        sources=[];rotation=rng.uniform(0.,math.tau)
        for j in range(12):
            if j<4:
                angle=rotation+(-.2+j*.13);radius=1650+rng.uniform(-20.,20.)
                x,y=radius*math.cos(angle),radius*math.sin(angle)
            elif family=='outer_then_inner':
                angle=rotation+math.pi+rng.uniform(-1.2,1.2);radius=rng.uniform(1030.,1450.)
                x,y=radius*math.cos(angle),radius*math.sin(angle)
            elif family=='outer_then_second_ring':
                angle=rotation+math.pi+(j-7.5)*.2;radius=1130+rng.uniform(-20.,20.)
                x,y=radius*math.cos(angle),radius*math.sin(angle)
            else:
                angle=rotation+math.pi
                x=1050*math.cos(angle)+rng.uniform(-220.,220.)
                y=1050*math.sin(angle)+rng.uniform(-220.,220.)
            sources.append(dict(channel=j+1,x=x,y=y,radius=1000.,orientation_deg=None))
        answer.append(dict(case_id=f'p3_shape_counter_{index:03d}',problem=3,seed=9807000+index,split='shape_counterexample',family=family,noise=('hash_uniform','spatial','extreme','bias')[(index//3)%4],sources=sources,provenance='self_constructed_not_official'))
    return answer

data=cases();output={}
for forced in (False,True):
    for name,cls in [('without_shape',AnnularNegativePolicy),('with_shape',AnnularShapePolicy)]:
        if not forced:result=run(cls,data)
        else:
            rows=[]
            for case in data:
                sim=LocalSimulator(case);sim.enter();client=ObservationClient(sim);policy=cls()
                # Test driver creates the same misleading, successful public
                # prefix for both policies. This is not a deployment policy.
                for source in case['sources'][:4]:policy._clear(client,(source['x'],source['y']),source['channel'])
                error=None
                try:r=policy.run(client)
                except Exception as exc:error=str(exc);r={}
                stats=sim.statistics();full=stats['cleared_count']==12 and r.get('completion_certified') and not error
                rows.append(dict(id=case['case_id'],average=stats['average_clear_time_s'],full=bool(full),error=error,sim=stats,policy=r))
            result=dict(mean=statistics.mean(row['average'] for row in rows),full=sum(row['full'] for row in rows),rows=rows)
        key=f'{name}_forced{forced}';output[key]=result
        print(key,{k:v for k,v in result.items() if k!='rows'},flush=True)
(ROOT/'problem3/results/p3_shape_counterexamples_v3.json').write_text(json.dumps(dict(cases=data,results=output),ensure_ascii=False,indent=2),encoding='utf8')
