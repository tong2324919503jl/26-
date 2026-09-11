from benchmark import *
cases=generate_suite(3,'development_v2',64);results={}
for radius in (1130,1150,1200,1300):
    def init(self,radius=radius):RotatingPolicy.__init__(self,config={'ring_radius':radius})
    cls=type(f'rotating_r{radius}',(RotatingPolicy,),{'__init__':init})
    r=run(cls,cases);results[cls.__name__]=r
    print(cls.__name__,{k:v for k,v in r.items() if k!='rows'},flush=True)
(ROOT/'problem3/results/p3_rotation_v3_screen.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
