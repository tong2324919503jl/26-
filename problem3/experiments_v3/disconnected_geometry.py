"""Use exact radial exclusions for integration, retaining all production bounds.

The live region is never changed by this experiment. Ray intervals describe
only the action-score integration domain and may have several disjoint pieces.
"""
from __future__ import annotations
import math
from problem3.geometry import distance,enclosing_circle,polygon_centroid
from problem3.experiments_v3.lookahead import polygon_area
from problem3.experiments_v3.coverage_family_tuning import get_policy

Base=get_policy(9,1700.)


def triangle_quadrature(polygon):
    triangles=[(polygon[0],polygon[i],polygon[i+1]) for i in range(1,len(polygon)-1)]
    for _ in range(2):
        divided=[]
        for a,b,c in triangles:
            ab=((a[0]+b[0])/2,(a[1]+b[1])/2);bc=((b[0]+c[0])/2,(b[1]+c[1])/2);ca=((c[0]+a[0])/2,(c[1]+a[1])/2)
            divided.extend(((a,ab,ca),(ab,b,bc),(ca,bc,c),(ab,bc,ca)))
        triangles=divided
    return [(polygon_area([a,b,c]),((a[0]+b[0]+c[0])/3,(a[1]+b[1]+c[1])/3)) for a,b,c in triangles]


def public_radius_interval(source,positives,negatives):
    low=max([1000.]+[distance(source,p) for p,_ in positives])
    high=min([1500.]+[distance(source,p) for p in negatives])
    return low,high


class GeometryAuditMixin:
    def _probe_point(self,ch,client,probe_index):
        polygon=self.regions[ch]
        if enclosing_circle(polygon)[1]>60.:
            nodes=triangle_quadrature(polygon);total=sum(w for w,_ in nodes)
            positives=self.observations[ch];negatives=getattr(self,'negative_history',{}).get(ch,[])
            excluded=sum(w for w,p in nodes if public_radius_interval(p,positives,negatives)[0]>public_radius_interval(p,positives,negatives)[1])
            fraction=excluded/total if total else 0.
            self.stats['geometry_audit_count']=self.stats.get('geometry_audit_count',0)+1
            self.stats['geometry_audit_gap_total']=self.stats.get('geometry_audit_gap_total',0.)+fraction
            if fraction>.1:self.stats['geometry_gap_above_tenth']=self.stats.get('geometry_gap_above_tenth',0)+1
            if fraction>.5:self.stats['geometry_gap_above_half']=self.stats.get('geometry_gap_above_half',0)+1
            if fraction>self.stats.get('geometry_gap_max',0.):
                self.stats['geometry_gap_max']=fraction
                self.stats['geometry_gap_max_public_state']={'polygon':polygon,'positives':positives,'negatives':negatives}
        return super()._probe_point(ch,client,probe_index)


def disk_interval(anchor,direction,center,radius):
    dx,dy=anchor[0]-center[0],anchor[1]-center[1]
    projection=dx*direction[0]+dy*direction[1]
    discriminant=projection*projection-(dx*dx+dy*dy-radius*radius)
    if discriminant<0:return None
    root=math.sqrt(discriminant)
    return -projection-root,-projection+root


def subtract_interval(intervals,excluded):
    if excluded is None:return intervals
    lo,hi=excluded;out=[]
    for a,b in intervals:
        if b<=lo or a>=hi:out.append((a,b));continue
        if a<lo:out.append((a,min(b,lo)))
        if b>hi:out.append((max(a,hi),b))
    return out


def radial_intervals(polygon,anchor,direction,positives,negatives,failed_clears=()):
    lo,hi=0.,1500.
    for a,b in zip(polygon,polygon[1:]+polygon[:1]):
        x,y=b[1]-a[1],a[0]-b[0]
        slope=x*direction[0]+y*direction[1]
        bound=x*(a[0]-anchor[0])+y*(a[1]-anchor[1])
        if abs(slope)<1e-12:
            if bound < -1e-7:return []
        elif slope>0:hi=min(hi,bound/slope)
        else:lo=max(lo,bound/slope)
    for p,_ in positives:
        interval=disk_interval(anchor,direction,p,1500.)
        if interval is None:return []
        lo=max(lo,interval[0]);hi=min(hi,interval[1])
    if hi-lo<1e-6:return []
    intervals=[(lo,hi)]
    for p in negatives:intervals=subtract_interval(intervals,disk_interval(anchor,direction,p,1000.))
    # A direction response, unlike near, proves distance strictly above 5m.
    for p,_ in positives:intervals=subtract_interval(intervals,disk_interval(anchor,direction,p,5.))
    for p in failed_clears:intervals=subtract_interval(intervals,disk_interval(anchor,direction,p,20.))
    return [(a,b) for a,b in intervals if b-a>1e-6]


class DisconnectedQuadratureMixin:
    geometry_ray_count=3
    geometry_radial_count=2
    geometry_failed_clear_exclusion=False
    def _clear(self,client,point,ch):
        success=super()._clear(client,point,ch)
        if not success:
            if not hasattr(self,'_failed_clear_geometry'):self._failed_clear_geometry={}
            attempts=self._failed_clear_geometry.setdefault(ch,[])
            if all(distance(client.position,p)>1e-6 for p in attempts):attempts.append(client.position)
        return success

    def _probe_point(self,ch,client,probe_index):
        self._geometry_channel=ch
        try:return super()._probe_point(ch,client,probe_index)
        finally:self._geometry_channel=None

    def _rollout_nodes(self,polygon,positives,negatives):
        anchor,bearing=positives[-1]
        angles=[(math.atan2(p[1]-anchor[1],p[0]-anchor[0])-math.radians(bearing)+math.pi)%math.tau-math.pi for p in polygon if distance(p,anchor)>1e-5]
        if not angles:return super()._rollout_nodes(polygon,positives,negatives)
        low,high=min(angles),max(angles)
        if high-low>math.pi or high-low<1e-10:return super()._rollout_nodes(polygon,positives,negatives)
        failed=[]
        if self.geometry_failed_clear_exclusion:
            failed=getattr(self,'_failed_clear_geometry',{}).get(getattr(self,'_geometry_channel',None),[])
        nodes=[];maxpieces=0
        for i in range(self.geometry_ray_count):
            angle=math.radians(bearing)+low+(high-low)*(i+.5)/self.geometry_ray_count
            direction=(math.cos(angle),math.sin(angle))
            intervals=radial_intervals(polygon,anchor,direction,positives,negatives,failed)
            maxpieces=max(maxpieces,len(intervals))
            for a,b in intervals:
                area=max(0.,b*b-a*a)
                for j in range(self.geometry_radial_count):
                    radius=math.sqrt(a*a+(b*b-a*a)*(j+.5)/self.geometry_radial_count)
                    p=(anchor[0]+radius*direction[0],anchor[1]+radius*direction[1])
                    rlo,rhi=public_radius_interval(p,positives,negatives)
                    if rlo<=rhi+1e-6:nodes.append((area/self.geometry_radial_count,p,rlo,max(rhi,rlo)))
        self.stats['ray_quadrature_count']=self.stats.get('ray_quadrature_count',0)+1
        if maxpieces>1:self.stats['ray_disconnected_count']=self.stats.get('ray_disconnected_count',0)+1
        if not nodes:return super()._rollout_nodes(polygon,positives,negatives)
        total=sum(w for w,*_ in nodes)
        return [(w/total,p,lo,hi) for w,p,lo,hi in nodes]


class AuditPolicy(GeometryAuditMixin,Base):pass
class DisconnectedPolicy(DisconnectedQuadratureMixin,Base):pass
class FailedClearAwarePolicy(DisconnectedPolicy):geometry_failed_clear_exclusion=True


if __name__=='__main__':
    from problem3.experiments_v3.benchmark import run,generate_suite,ROOT
    import sys,json
    n=int(sys.argv[1]) if len(sys.argv)>1 else 48
    requested=sys.argv[2:]
    classes=(AuditPolicy,DisconnectedPolicy,FailedClearAwarePolicy)
    if requested:classes=tuple(cls for cls in classes if cls.__name__ in requested)
    cases=generate_suite(3,'development_v2',n);results={}
    for cls in classes:
        r=run(cls,cases);results[cls.__name__]=r
        print(cls.__name__,{k:v for k,v in r.items() if k!='rows'},flush=True)
        if cls is AuditPolicy:
            st=[row['policy'] for row in r['rows']]
            print({k:sum(s.get(k,0) for s in st) for k in ('geometry_audit_count','geometry_audit_gap_total','geometry_gap_above_tenth','geometry_gap_above_half')},flush=True)
        suffix=('_'+('_'.join(requested))) if requested else ''
        (ROOT/f'problem3/results/iterations_v3/disconnected_geometry_{n}{suffix}.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
