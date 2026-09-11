"""Development-only global routing experiments; no source truth is consumed."""
from __future__ import annotations
import math
from problem4.legacy_policy import SearchPolicy as LegacyPolicy
from problem3.geometry import distance, polygon_centroid, enclosing_circle


def nearest_route(position, goals, iterations=100):
    remaining=list(goals); route=[]; origin=position
    while remaining:
        i=min(range(len(remaining)), key=lambda j: distance(origin, remaining[j][0]))
        route.append(remaining.pop(i)); origin=route[-1][0]
    for _ in range(iterations):
        best=None; delta=-.01
        for i in range(len(route)-1):
            a=position if i == 0 else route[i-1][0]; b=route[i][0]
            for j in range(i+1,len(route)):
                c=route[j][0]; d=route[j+1][0] if j+1<len(route) else None
                change=distance(a,c)+ (distance(b,d) if d else 0) - distance(a,b) -(distance(c,d) if d else 0)
                if change<delta: best=(i,j); delta=change
        if best is None: break
        i,j=best; route[i:j+1]=reversed(route[i:j+1])
    return route

class RoutePolicy(LegacyPolicy):
    mode='mixed'
    delay_distance=700
    insert_detour=300
    min_radius=120
    neighbors=None
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if self.neighbors:
            self.config.neighbor_min_parallax_deg,self.config.neighbor_max_distance_m=self.neighbors
    def _route_goal(self,client,pending):
        scans=[(p,'scan',i) for i,p in enumerate(pending)]
        targets=[(polygon_centroid(p),'clear',ch) for ch,p in self.regions.items() if ch not in self.cleared]
        if not scans:return nearest_route(client.position,targets)[0]
        if not targets:return nearest_route(client.position,scans)[0]
        if self.mode=='mixed':return nearest_route(client.position,scans+targets)[0]
        scanroute=nearest_route(client.position,scans)
        if self.mode in ('insertion','sweep'):
            nxt=scanroute[0]
            candidates=[]
            for t in targets:
                detour=distance(client.position,t[0])+distance(t[0],nxt[0])-distance(client.position,nxt[0])
                radius=enclosing_circle(self.regions[t[2]])[1]
                score=detour + (0.5*radius if self.mode=='sweep' else 0)
                candidates.append((score,t))
            best=min(candidates,key=lambda t:t[0])
            return best[1] if best[0]<self.insert_detour else nxt
        route=nearest_route(client.position,scans+targets)
        first=route[0]
        if first[1]=='scan':return first
        poly=self.regions[first[2]]; center,radius=enclosing_circle(poly)
        if radius<self.min_radius:return first
        anchor,_=self.observations[first[2]][-1]
        candidates=[]
        for scan in scans:
            point=scan[0]
            a=(anchor[0]-center[0],anchor[1]-center[1]);b=(point[0]-center[0],point[1]-center[1])
            den=math.hypot(*a)*math.hypot(*b)
            sine=abs(a[0]*b[1]-a[1]*b[0])/den if den else 0
            detour=distance(client.position,point)+distance(point,center)-distance(client.position,center)
            if sine>.2 and distance(point,center)<1400 and detour<self.delay_distance:
                candidates.append((detour,scan))
        return min(candidates,key=lambda p:p[0])[1] if candidates else first


def policy_factory(name):
    cls=type(name,(RoutePolicy,),{})
    if name=='legacy':return LegacyPolicy
    if name=='mixed':return cls
    if name.startswith('delay'):
        cls.mode='delay';cls.delay_distance=float(name[5:])
    elif name.startswith('insertion'):
        cls.mode='insertion';cls.insert_detour=float(name[9:])
    elif name.startswith('sweep'):
        cls.mode='sweep';cls.insert_detour=float(name[5:])
    elif name.startswith('neighbor'):
        cls.neighbors=(float(name[8:]),1600)
    else:raise ValueError(name)
    return cls


class SweepPolicy(RoutePolicy):
    ordering='outer'
    insert_detour=400
    stop_discovery=True
    def _route_goal(self,client,pending):
        known=set(self.regions)|self.cleared
        if self.stop_discovery and len(known)==16:
            pending = []
        targets=[(polygon_centroid(p),'clear',ch) for ch,p in self.regions.items() if ch not in self.cleared]
        scans=[(p,'scan',i) for i,p in enumerate(pending)]
        if not scans:return nearest_route(client.position,targets)[0]
        origin_scan=[s for s in scans if distance((0,0),s[0])<1]
        if origin_scan:return origin_scan[0]
        if not hasattr(self,'scan_order'):
            outer=sorted([s[0] for s in scans if math.hypot(*s[0])>1500],key=lambda p:math.atan2(p[1],p[0]))
            inner=sorted([s[0] for s in scans if math.hypot(*s[0])<1500],key=lambda p:math.atan2(p[1],p[0]))
            first,second=(outer,inner) if self.ordering=='outer' else (inner,outer)
            start=min(range(len(first)),key=lambda i:distance(client.position,first[i]))
            first=first[start:]+first[:start]
            start=min(range(len(second)),key=lambda i:distance(first[-1],second[i]))
            second=second[start:]+second[:start]
            self.scan_order=first+second
        nxt=min(scans,key=lambda s:self.scan_order.index(s[0]))
        if not targets:return nxt
        candidates=[]
        for t in targets:
            detour=distance(client.position,t[0])+distance(t[0],nxt[0])-distance(client.position,nxt[0])
            candidates.append((detour,t))
        best=min(candidates,key=lambda t:t[0])
        return best[1] if best[0]<self.insert_detour else nxt

class DetectedStopPolicy(LegacyPolicy):
    def _route_goal(self,client,pending):
        if len(set(self.regions)|self.cleared)==16:pending = []
        return super()._route_goal(client,pending)

class InformationRoutingMixin:
    """Expected discovery-cost tour. Particle prior affects ordering only."""
    info_weight=1.0
    samples=None
    mask_cache={}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.scanned_mask=0
        if type(self).samples is None:
            pts=[(x,y) for x in range(-1800,1801,300) for y in range(-1800,1801,300) if math.hypot(x,y)<=1800]
            type(self).samples=[(p,r,a) for p in pts for r in (1000,1250,1500) for a in [None]*8+[i*math.tau/8 for i in range(8)]]
    def _mask(self,p):
        key=tuple(round(v,5) for v in p)
        if key not in self.mask_cache:
            mask=0
            for i,(q,r,a) in enumerate(self.samples):
                dx,dy=p[0]-q[0],p[1]-q[1]
                if math.hypot(dx,dy)<=r and (a is None or dx*math.cos(a)+dy*math.sin(a)>=-1e-8):mask|=1<<i
            self.mask_cache[key]=mask
        return self.mask_cache[key]
    def _scan(self,client,point):
        super()._scan(client,point);self.scanned_mask|=self._mask(point)
    def _route_goal(self,client,pending):
        known=set(self.regions)|self.cleared
        if len(known)==16:pending = []
        goals=[(p,'scan',i) for i,p in enumerate(pending)]+[(polygon_centroid(p),'clear',ch) for ch,p in self.regions.items() if ch not in self.cleared]
        route=nearest_route(client.position,goals,40)
        if len(pending)<2:return route[0]
        start_covered=self.scanned_mask.bit_count();total=len(self.samples);unseen=total-start_covered
        if unseen==0:return route[0]
        unknown=20-len(known);posterior=.65*unseen/(.35*total+.65*unseen)
        masks={i:self._mask(p) for i,p in enumerate(pending)}
        def objective(route):
            travel=sum(distance(client.position if i==0 else route[i-1][0],g[0]) for i,g in enumerate(route))/5
            covered=self.scanned_mask;reading=0
            for point,kind,ident in route:
                if kind=='scan':
                    reading+=6*unknown*((1-posterior)+posterior*(total-covered.bit_count())/unseen)
                    covered|=masks[ident]
            return travel+self.info_weight*reading
        best=objective(route)
        for _ in range(20):
            changed=False
            for i in range(len(route)-1):
                for j in range(i+1,len(route)):
                    candidate=route[:i]+list(reversed(route[i:j+1]))+route[j+1:]
                    score=objective(candidate)
                    if score<best-.01:
                        route=candidate;best=score;changed=True;break
                if changed:break
            if not changed:break
        return route[0]

class InformationPolicy(InformationRoutingMixin, LegacyPolicy):
    pass

class _ProbeYield(Exception):pass
class InterleavePolicy(LegacyPolicy):
    def _route_goal(self,client,pending):
        if len(set(self.regions)|self.cleared)==16:pending = []
        return super()._route_goal(client,pending)
    def _measure(self,client,point,channel):
        result=super()._measure(client,point,channel)
        if getattr(self,'_in_localize',False) and result=='direction':
            self.stats['paired_probe_actions']=self.stats.get('paired_probe_actions',0)+1
            raise _ProbeYield()
        return result
    def _localize(self,channel,client):
        self._in_localize=True
        try:return super()._localize(channel,client)
        except _ProbeYield:return False
        finally:self._in_localize=False

class EntryPolicy(LegacyPolicy):
    def _route_goal(self,client,pending):
        if len(set(self.regions)|self.cleared)==16:pending = []
        goals=[(p,'scan',i) for i,p in enumerate(pending)]+[(polygon_centroid(p),'clear',ch) for ch,p in self.regions.items() if ch not in self.cleared]
        entries=[]
        for point,kind,ident in goals:
            probes=[point]
            if kind=='clear' and enclosing_circle(self.regions[ident])[1]>55:
                anchor,bearing=self.observations[ident][-1];theta=math.radians(bearing);forward=(math.cos(theta),math.sin(theta));side=(-forward[1],forward[0])
                longitudinal=[(p[0]-anchor[0])*forward[0]+(p[1]-anchor[1])*forward[1] for p in self.regions[ident]]
                step=(min(longitudinal)+max(longitudinal))/2;width=max(35.,min(140.,.18*step));width=max(width,step*math.tan(math.radians(self.config.bearing_error_deg))+.01)
                mid=(anchor[0]+step*forward[0],anchor[1]+step*forward[1]);probes=[(mid[0]+s*width*side[0],mid[1]+s*width*side[1]) for s in (-1,1)]
            entries.append(probes)
        matrix=[[min(distance(prev,p)+distance(p,goals[j][0]) for p in entries[j]) for j in range(len(goals))] for prev in [g[0] for g in goals]+[client.position]]
        route=[];remaining=set(range(len(goals)));last=len(goals)
        while remaining:
            nxt=min(remaining,key=lambda j:matrix[last][j]);route.append(nxt);remaining.remove(nxt);last=nxt
        def cost(r):return sum(matrix[len(goals) if i==0 else r[i-1]][j] for i,j in enumerate(r))
        best=cost(route)
        for _ in range(40):
            changed=False
            for i in range(len(route)-1):
                for j in range(i+1,len(route)):
                    candidate=route[:i]+list(reversed(route[i:j+1]))+route[j+1:];score=cost(candidate)
                    if score<best-.01:route=candidate;best=score;changed=True;break
                if changed:break
            if not changed:break
        return goals[route[0]]

class RotationMixin:
    rotation_steps=12
    def _route_goal(self,client,pending):
        if not getattr(self,'_rotation_done',False) and self.coverage_visited:
            self._rotation_done=True
            targets=[(polygon_centroid(p),'clear',ch) for ch,p in self.regions.items() if ch not in self.cleared]
            if targets and pending:
                best=math.inf;selected=list(pending);angle_chosen=0
                for step in range(self.rotation_steps):
                    angle=math.pi/6*step/self.rotation_steps;c,s=math.cos(angle),math.sin(angle)
                    points=[(c*p[0]-s*p[1],s*p[0]+c*p[1]) for p in pending]
                    goals=[(p,'scan',i) for i,p in enumerate(points)]+targets
                    route=nearest_route(client.position,goals,40)
                    score=sum(distance(client.position if i==0 else route[i-1][0],goal[0]) for i,goal in enumerate(route))
                    if score<best-1e-6:best=score;selected=points;angle_chosen=math.degrees(angle)
                pending[:]=selected;self.stats['coverage_rotation_deg']=angle_chosen
        return super()._route_goal(client,pending)




if __name__=='__main__':
    import argparse,json,sys,time,statistics
    from pathlib import Path
    from problem3.scenarios import generate_suite
    from problem3.simulator import LocalSimulator,ObservationClient
    parser=argparse.ArgumentParser();parser.add_argument('--split',default='development');parser.add_argument('--count',type=int,default=24);parser.add_argument('names',nargs='+');args=parser.parse_args()
    body={}
    for name in args.names:
        policy_cls=policy_factory(name); rows=[]
        for case in generate_suite(4,args.split,args.count):
            sim=LocalSimulator(case);sim.enter();error=None;result={}
            try:result=policy_cls().run(ObservationClient(sim))
            except Exception as e:error=repr(e)
            stats=sim.statistics();row={'id':case['case_id'],'error':error,**stats,'policy':result};rows.append(row)
        full=[r['error'] is None and r['cleared_count']==r['source_count'] and r['policy']['completion_certified'] for r in rows]
        summary={'mean':statistics.mean(r['average_clear_time_s'] for r in rows),'move':statistics.mean(r['movement_m'] for r in rows),'action':statistics.mean(r['actions'] for r in rows),'pass':sum(good and r['average_clear_time_s']<=500 for good,r in zip(full,rows))/len(rows),'full':sum(full),'failures':[(r['id'],r['error']) for good,r in zip(full,rows) if not good]}
        body[name]={'summary':summary,'episodes':rows};print(name,json.dumps(summary),flush=True)
    output=Path(__file__).resolve().parents[1] / 'results' / 'iterations_v2' / f'routing_{args.split}_{args.count}_{"_".join(args.names)}.json'
    output.write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
