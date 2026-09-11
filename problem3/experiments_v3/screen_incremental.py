from benchmark import *
cases=generate_suite(3,'development_v2',64);results={}
branches={'incremental':IncrementalPolicy,'rotation_incremental':RotatingIncrementalPolicy}
for d in (0,250,500,750):branches[f'scanfirst{d}']=type(f'scanfirst{d}',(ScanFirstPolicy,),dict(clear_distance=d))
for name,cls in branches.items():
    r=run(cls,cases);results[name]=r;print(name,{k:v for k,v in r.items() if k!='rows'},flush=True)
(ROOT/'problem3/results/p3_incremental_v3_screen.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
