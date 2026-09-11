from benchmark import *
cases=generate_suite(3,'development_v2',64);results={}
for upper in (1100,1250,1500):
    for width in (.04,.12):
        cls=type(f'posterior{upper}_w{width}',(PosteriorPolicy,),dict(posterior_prior_max=upper,probe_fraction=width))
        r=run(cls,cases);results[cls.__name__]=r;print(cls.__name__,{k:v for k,v in r.items() if k!='rows'},flush=True)
(ROOT/'problem3/results/p3_posterior_v3_screen.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
