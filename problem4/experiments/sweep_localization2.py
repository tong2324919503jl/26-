from sweep_localization import *
cases=generate_suite(4,sys.argv[1] if len(sys.argv)>1 else 'development')
branches={}
for near in (False,True):
    for ls in (False,True):
        for exploratory in (55,100,150,250):
            name=f'near{near}ls{ls}clear{exploratory}'
            branches[name]=type(name,(SearchPolicy,),dict(localization_quantile=.35,localization_width_fraction=.08,localization_nearest_clear=near,localization_ls=ls,localization_exploratory_radius=exploratory))
for q in (.2,.35,.5):
    for minimum in (15,25):
        name=f'q{q}min{minimum}'
        branches[name]=type(name,(SearchPolicy,),dict(localization_quantile=q,localization_width_fraction=.04,localization_width_min=minimum,localization_enforce_range=True))
results={}
for name,cls in branches.items():
    r=run(cls,cases);results[name]=r
    print(name,{k:v for k,v in r.items() if k!='rows'},flush=True)
out=ROOT/'problem4/results/localization_development_sweep2.json'
out.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
