"""Add unseen-source travel to adaptive site selection's soft cost model."""
import math,random
from problem3.geometry import distance
from problem3.experiments_v3.adaptive_setcover import AdaptiveSetCoverPolicy
from problem3.experiments_v3.omni_discovery import expected_remaining_sources


def radical_inverse(i,base):
    result=0.;factor=1.
    while i:
        factor/=base;i,digit=divmod(i,base);result+=digit*factor
    return result


PRIOR=[((1800*math.sqrt(radical_inverse(i,2))*math.cos(math.tau*radical_inverse(i,3)),
         1800*math.sqrt(radical_inverse(i,2))*math.sin(math.tau*radical_inverse(i,3))),
         1000+500*radical_inverse(i,5)) for i in range(1,2049)]


class AnticipatoryCoverPolicy(AdaptiveSetCoverPolicy):
    def _cover_worlds(self,known,centers):
        unseen=[p for p,r in PRIOR if all(distance(p,q)>r for q in self.coverage_visited)]
        if not unseen:return [centers]
        count=round(expected_remaining_sources(len(known),len(unseen)/len(PRIOR)))
        rng=random.Random(80812+len(self.coverage_visited))
        return [centers+[rng.choice(unseen) for _ in range(count)] for _ in range(5)]


class GlobalAnticipatoryPolicy(AnticipatoryCoverPolicy):setcover_only_empty=False
