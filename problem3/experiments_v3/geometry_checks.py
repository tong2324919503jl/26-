"""External synthetic-truth audit; never imported by a search policy."""
import json,math,random,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from problem3.geometry import certified_covering_radius,contains,initial_region
from problem3.experiments_v3.negative_disks import AnnularNegativePolicy,outside_inner_disk
from problem3.scenarios import generate_suite
from problem3.simulator import LocalSimulator,ObservationClient


def main():
    maximum=0.
    for k in range(97):
        a=math.tau*k/97
        points=[(0.,0.)]+[(1650*math.cos(a+i*math.tau/7),1650*math.sin(a+i*math.tau/7)) for i in range(7)]
        bound=certified_covering_radius(points);maximum=max(maximum,bound)
        assert bound<1000
    rng=random.Random(672331);edge_checks=0
    for _ in range(100):
        q=(rng.uniform(-1000,1000),rng.uniform(-1000,1000))
        polygon=initial_region()
        retained=outside_inner_disk(polygon,q)
        for i in range(72):
            angle=math.tau*i/72
            point=(q[0]+1000.000001*math.cos(angle),q[1]+1000.000001*math.sin(angle))
            if math.hypot(*point)<1800:
                assert contains(retained,point)
                edge_checks+=1
    checks=episodes=0
    for case in generate_suite(3,'development_v3',384):
        sim=LocalSimulator(case);sim.enter()
        class AuditedPolicy(AnnularNegativePolicy):
            def _measure(self,client,point,ch):
                nonlocal checks
                result=super()._measure(client,point,ch)
                if ch in self.regions and ch not in self.cleared:
                    source=sim.sources[ch]
                    assert contains(self.regions[ch],(source['x'],source['y'])),case['case_id']
                    checks+=1
                return result
        result=AuditedPolicy().run(ObservationClient(sim));sim.exit()
        assert result['completion_certified'] and len(sim.cleared)==len(sim.sources)
        episodes+=1
    report={'scope':'external synthetic development audit only; no truth exposed to policy',
            'annular_rotation_certificates':97,'worst_covering_radius_m':maximum,
            'negative_disk_boundary_retention_checks':edge_checks,
            'end_to_end_episodes':episodes,'source_retention_checks':checks,'violations':0}
    (ROOT/'problem3/results/iterations_v3/geometry_checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))

if __name__=='__main__':main()
