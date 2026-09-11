from benchmark import *
cases=generate_suite(3,'development_v2',64)
results={}
for base in (LegacyPolicy,GlobalNegativePolicy,CombinedPolicy,DynamicPolicy):
    for radius in (1300,1450,1600,1720):
        def init(self,radius=radius,base=base):base.__init__(self,config={'ring_radius':radius})
        cls=type(f'{base.__name__}{radius}',(base,),{'__init__':init})
        r=run(cls,cases);results[cls.__name__]=r
        print(cls.__name__,{k:v for k,v in r.items() if k!='rows'},flush=True)
(ROOT/'problem3/results/p3_radius_v3_screen.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
