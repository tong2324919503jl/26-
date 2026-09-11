"""Finite-certificate screen of symmetric rings with 13--18 outer stops."""
from __future__ import annotations
import json
import math
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from problem4.coverage import directional_cover_certificate


def screen():
    rows=[]
    for outer_count in range(13,19):
        outer_radius=1802/math.cos(math.pi/outer_count)
        best=None
        for inner_count in range(6,min(12,25-outer_count)):
            for radius in (850.,925.,1000.,1075.,1150.):
                for phase in (0.,.25,.5):
                    points=[(0.,0.)]+[(outer_radius*math.cos(i*math.tau/outer_count),
                                      outer_radius*math.sin(i*math.tau/outer_count))
                                     for i in range(outer_count)]
                    points += [(radius*math.cos((i+phase)*math.tau/inner_count),
                                radius*math.sin((i+phase)*math.tau/inner_count))
                               for i in range(inner_count)]
                    report=directional_cover_certificate(points,early_exit=False)
                    row={'outer_count':outer_count,'outer_radius':outer_radius,
                         'inner_count':inner_count,'inner_radius':radius,'phase':phase,
                         'certificate':report}
                    rows.append(row)
                    if best is None or report['max_directional_radius_bound_m'] < best['certificate']['max_directional_radius_bound_m']:
                        best=row
        print(json.dumps(best),flush=True)
    folder=ROOT/'problem4'/'results'/'iterations_v3'
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'coverage_more_outer_rings.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
    return rows


if __name__=='__main__':screen()
