"""Use feasible-region lookahead instead of a center/parallax approximation."""
import math
from problem3.geometry import distance,enclosing_circle,intersect_bearing,polygon_centroid
from problem3.experiments_v3.journey import EnrouteMixin,ClearRegionMixin
from problem3.experiments_v3.negative_disks import AnnularNegativePolicy


class GeometryEnrouteMixin(EnrouteMixin):
    enroute_min_gain=30.
    enroute_compare_destination=False
    enroute_min_radius=80.
    def _prediction(self,polygon,anchor,point):
        center,radius=enclosing_circle(polygon)
        a,b=max(((a,b) for a in polygon for b in polygon),key=lambda pair:distance(*pair))
        hypotheses=[(a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])) for t in (.2,.5,.8)]
        estimates=[]
        for hypothesis in hypotheses:
            dist=distance(point,hypothesis)
            probability=max(0.,min(1.,(1500-dist)/500))
            if dist<=5.:estimate=5.
            else:
                angle=math.degrees(math.atan2(hypothesis[1]-point[1],hypothesis[0]-point[0]))
                possible=intersect_bearing(polygon,point,angle,error_deg=self.config.bearing_error_deg)
                estimate=enclosing_circle(possible)[1] if possible else radius
            estimates.append(estimate*probability+radius*(1-probability))
        return sum(estimates)/len(estimates),1.


class GeometryEnroutePolicy(GeometryEnrouteMixin,ClearRegionMixin,AnnularNegativePolicy):pass
