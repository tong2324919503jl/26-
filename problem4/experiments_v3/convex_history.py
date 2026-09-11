"""Use convexity of a source's disk/half-disk receiving footprint."""
from __future__ import annotations
from itertools import combinations
from problem3.geometry import clip_halfplane
from problem4.localization import _convex_hull
from problem4.policy import SearchPolicy as Previous

class ConvexHistoryMixin:
    def _clip_history(self,channel):
        super()._clip_history(channel)
        self._positive_cones(channel)

    def _measure(self,client,point,channel):
        result=super()._measure(client,point,channel)
        if result=='no_signal' and channel in self.regions:
            self._positive_cones(channel)
        return result

    def _positive_cones(self,channel):
        positives=[p for p,_ in self.observations[channel]]
        if len(positives)<2:return
        polygon=self.regions[channel]
        for q in getattr(self,'_negative_history',{}).get(channel,[]):
            for p1,p2 in combinations(positives,2):
                # Q in conv(g,P1,P2) would belong to the source's convex
                # receiving footprint. This contradicts its negative read.
                # Thus exclude g = Q + s(Q-P1)+t(Q-P2), s,t >= 0.
                ax,ay=q[0]-p1[0],q[1]-p1[1]
                bx,by=q[0]-p2[0],q[1]-p2[1]
                cross=ax*by-ay*bx
                if abs(cross)<1e-5:continue
                if cross<0:ax,ay,bx,by=bx,by,ax,ay
                planes=[(ay,-ax,ay*q[0]-ax*q[1]),(-by,bx,-by*q[0]+bx*q[1])]
                if any(min(a*v[0]+b*v[1]-c for v in polygon)>1e-4 for a,b,c in planes):continue
                inside=polygon;retained=[]
                for a,b,c in planes:
                    retained.extend(clip_halfplane(inside,-a,-b,-c))
                    inside=clip_halfplane(inside,a,b,c)
                    if not inside:break
                if not retained:raise RuntimeError('Convex receiving footprint contradiction')
                polygon=_convex_hull(retained)
        self.regions[channel]=polygon

class ConvexHistoryPolicy(ConvexHistoryMixin,Previous):
    pass
