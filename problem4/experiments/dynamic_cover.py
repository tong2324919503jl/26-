"""Experimental opportunistic scan replacement with a triangulation certificate."""
from __future__ import annotations

import math
from collections import Counter
from itertools import combinations
from problem3.geometry import distance
from problem4.legacy_policy import SearchPolicy as Legacy


def cross(a,b,c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def hull(points):
    points=sorted(set(points))
    lower=[]; upper=[]
    for p in points:
        while len(lower)>1 and cross(lower[-2],lower[-1],p)<=0:
            lower.pop()
        lower.append(p)
    for p in reversed(points):
        while len(upper)>1 and cross(upper[-2],upper[-1],p)<=0:
            upper.pop()
        upper.append(p)
    return lower[:-1]+upper[:-1]


def triangulate(points):
    """Bowyer-Watson; certificate separately verifies mesh boundaries and area."""
    points=sorted(set(points))
    big=max(1,max(abs(v) for p in points for v in p))*32
    vertices=points+[(-big,-big),(big,-big),(0,big)]
    n=len(points)
    triangles=[(n,n+1,n+2)]
    for i,p in enumerate(points):
        bad=[]
        for t in triangles:
            ax,ay=vertices[t[0]][0]-p[0],vertices[t[0]][1]-p[1]
            bx,by=vertices[t[1]][0]-p[0],vertices[t[1]][1]-p[1]
            cx,cy=vertices[t[2]][0]-p[0],vertices[t[2]][1]-p[1]
            det=(ax*ax+ay*ay)*(bx*cy-by*cx)-(bx*bx+by*by)*(ax*cy-ay*cx)+(cx*cx+cy*cy)*(ax*by-ay*bx)
            if det > -1e-5:
                bad.append(t)
        edges=Counter(tuple(sorted((t[j],t[(j+1)%3]))) for t in bad for j in range(3))
        bad=set(bad); triangles=[t for t in triangles if t not in bad]
        for (a,b),count in edges.items():
            if count!=1: continue
            area=cross(vertices[a],vertices[b],p)
            if area>1e-8: triangles.append((a,b,i))
            elif area < -1e-8: triangles.append((b,a,i))
    return [tuple(vertices[i] for i in t) for t in triangles if all(i<n for i in t)]


def certified(points):
    """A sufficient condition for every source/beam, never a sampled score.

    Mesh covers its convex hull. Hull contains target circle. Every simplex
    has diameter <1000, hence each source is surrounded by in-range scans.
    """
    if len(set(points))<3: return False
    boundary=hull(points)
    if len(boundary)<3: return False
    for a,b in zip(boundary,boundary[1:]+boundary[:1]):
        if cross(a,b,(0,0))/distance(a,b) < 1800.0001:
            return False
    triangles=triangulate(points)
    if not triangles: return False
    if any(max(distance(a,b) for a,b in combinations(t,2)) >= 999.999 for t in triangles):
        return False
    # Consistent oriented boundary cancels every interior edge; the remaining
    # chain must be exactly the convex hull. Positive faces plus matching area
    # guard against accidental gaps/overlaps in incremental triangulation.
    edges=Counter((t[j],t[(j+1)%3]) for t in triangles for j in range(3))
    for a,b in list(edges):
        k=min(edges[a,b],edges[b,a]); edges[a,b]-=k; edges[b,a]-=k
    remaining={k:v for k,v in edges.items() if v}
    expected={(a,b):1 for a,b in zip(boundary,boundary[1:]+boundary[:1])}
    if remaining!=expected: return False
    area=sum(cross(*t) for t in triangles)
    hull_area=sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(boundary,boundary[1:]+boundary[:1]))
    return abs(area-hull_area)<1e-6


class DynamicPolicy(Legacy):
    """Scan at a clearance stop only if it can replace a planned scan vertex."""
    replacement_distance=400

    def coverage_certificate(self,points):
        return certified(points)

    def run(self,client):
        pending=self.coverage_points()
        while pending or any(ch not in self.cleared for ch in self.regions):
            client.check_budget()
            if len(set(self.regions)|self.cleared)==16:
                pending=[]
            if not pending and not any(ch not in self.cleared for ch in self.regions): break
            _,action,identifier=self._route_goal(client,pending)
            if action=='scan':
                self._scan(client,pending.pop(identifier))
            else:
                self._localize(identifier,client)
                # Candidate vertex replaces one scheduled node if the remaining
                # full scan set still certifies every possible source/heading.
                close=sorted((distance(client.position,p),i) for i,p in enumerate(pending)
                             if distance(client.position,p)<self.replacement_distance)
                for d,i in close:
                    remaining=pending[:i]+pending[i+1:]
                    if self.coverage_certificate(self.coverage_visited+remaining+[client.position]):
                        self._scan(client,client.position)
                        pending=remaining
                        self.stats['replaced_scan_points']=self.stats.get('replaced_scan_points',0)+1
                        break
            self._update_neighbors(client)
            if len(self.cleared)==16:
                return self._result('maximum_source_count_cleared',False)
        return self._result('certified_coverage_and_all_detected_cleared',True)


class StrongDynamicPolicy(DynamicPolicy):
    replacement_distance=700

    def coverage_certificate(self,points):
        from problem4.experiments.coverage import halfplane_certificate
        return halfplane_certificate(points)['certified']
