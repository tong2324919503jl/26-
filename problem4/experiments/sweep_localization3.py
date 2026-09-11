from sweep_localization import *
cases=generate_suite(4,sys.argv[1] if len(sys.argv)>1 else 'development')
results={}
branches={}
for q in (.2,.35,.5):
    for slices in (1,4,12):
        name=f'historyq{q}slices{slices}'
        branches[name]=type(name,(SearchPolicy,),dict(localization_quantile=q,localization_width_fraction=.04,localization_width_min=15,localization_enforce_range=True,localization_history=True,localization_history_slices=slices))
for name,cls in branches.items():
    r=run(cls,cases);results[name]=r
    print(name,{k:v for k,v in r.items() if k!='rows'},flush=True)
out=ROOT/'problem4/results/localization_development_sweep3.json'
out.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
