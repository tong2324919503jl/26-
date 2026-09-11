"""A fixed-direction sweep only after all 20 origin readings were absent.

The certified scan locations and localization controller remain unchanged.
Only their visit schedule changes. Finished scans advance a fixed angular
frontier; source estimates behind it are deferred until the circle is scanned.
"""
from __future__ import annotations
import math
from problem3.geometry import distance,polygon_centroid
from problem4.routing import nearest_seed,insertion_seed,route_length
from problem3.experiments_v3.optical_band import OpticalBandPolicy,AggressiveBandPolicy


def fixed_end_two_opt(route,matrix):
    route=list(route);start=len(matrix)-1
    for _ in range(40):
        best=-.01;change=None
        for i in range(len(route)-2):
            a=start if i==0 else route[i-1];b=route[i]
            for j in range(i+1,len(route)-1):
                c=route[j];d=route[j+1]
                delta=matrix[a][c]+matrix[b][d]-matrix[a][b]-matrix[c][d]
                if delta<best:best=delta;change=(i,j)
        if change is None:break
        i,j=change;route[i:j+1]=reversed(route[i:j+1])
    return route


def local_window_order(start,goals,next_point):
    if len(goals)<=1:return list(range(len(goals)))
    points=[goal[0] for goal in goals]+([next_point] if next_point is not None else [])+[start]
    matrix=[[distance(a,b) for b in points] for a in points]
    seeds=[nearest_seed(matrix),insertion_seed(matrix)]
    if next_point is not None:
        last=len(goals)
        seeds=[fixed_end_two_opt([i for i in seed if i!=last]+[last],matrix) for seed in seeds]
    else:
        from problem4.routing import two_opt
        seeds=[two_opt(seed,matrix) for seed in seeds]
    chosen=min(seeds,key=lambda route:route_length(route,matrix))
    return [i for i in chosen if i<len(goals)]


class AnnularSweepMixin:
    sweep_window_deg=0.
    sweep_backward_grace_deg=0.
    sweep_stick_to_source=True

    def _phase(self,point):
        return (self._sweep_sign*(math.atan2(point[1],point[0])-self._sweep_cut))%math.tau

    def _initialize_sweep(self,client,pending):
        first=self.coverage_visited[1]
        first_angle=math.atan2(first[1],first[0]);best=None
        # Half a scan spacing leaves a small starting arc available on either
        # side of the first station. Direction is chosen once from known goals.
        offset=math.pi/self.annular_count
        points=list(pending)+[polygon_centroid(poly) for ch,poly in self.regions.items() if ch not in self.cleared]
        for sign in (-1,1):
            cut=first_angle-sign*offset
            ordered=sorted(points,key=lambda p:(sign*(math.atan2(p[1],p[0])-cut))%math.tau)
            length=sum(distance(a,b) for a,b in zip([client.position]+ordered,ordered))
            if best is None or length<best[0]:best=(length,sign,cut)
        _,self._sweep_sign,self._sweep_cut=best
        self._sweep_progress=0.
        self._sweep_deferred=set()
        self._sweep_active_channel=None
        self.stats['annular_sweep_direction']=self._sweep_sign

    def _scan(self,client,point):
        result=super()._scan(client,point)
        if hasattr(self,'_sweep_sign'):
            phase=self._phase(point)
            if phase+1e-7<self._sweep_progress:
                raise RuntimeError('Fixed annular scanner order reversed')
            self._sweep_progress=max(self._sweep_progress,phase)
            self.stats['annular_sweep_scan_steps']=self.stats.get('annular_sweep_scan_steps',0)+1
        return result

    def _route_goal(self,client,pending):
        original=super()._route_goal(client,pending)
        # This guard preserves every nonempty-origin case exactly, including
        # inherited phase choice, warm starts and physical actions.
        if not getattr(self,'_annular_decision',False):return original
        if len(self.coverage_visited)<2:return original
        if not hasattr(self,'_sweep_sign'):self._initialize_sweep(client,pending)
        if not pending or len(set(self.regions)|self.cleared)==16:
            return original
        if (self.sweep_stick_to_source and self._sweep_active_channel is not None
                and self._sweep_active_channel not in self.cleared):
            ch=self._sweep_active_channel
            return polygon_centroid(self.regions[ch]),'clear',ch
        self._sweep_active_channel=None
        entries=[]
        for i,point in enumerate(pending):entries.append((self._phase(point),(point,'scan',i)))
        grace=math.radians(self.sweep_backward_grace_deg)
        for ch,polygon in self.regions.items():
            if ch in self.cleared:continue
            point=polygon_centroid(polygon);phase=self._phase(point)
            if ch in self._sweep_deferred:continue
            if phase<self._sweep_progress-grace-1e-8:
                self._sweep_deferred.add(ch)
                self.stats['annular_sweep_deferred_sources']=self.stats.get('annular_sweep_deferred_sources',0)+1
                continue
            entries.append((phase,(point,'clear',ch)))
        entries.sort(key=lambda item:(item[0],item[1][1],item[1][2]))
        if not entries:return original
        width=math.radians(self.sweep_window_deg)
        end=1
        while end<len(entries) and entries[end][0]<=entries[0][0]+width+1e-9:end+=1
        goals=[goal for _,goal in entries[:end]]
        next_point=entries[end][1][0] if end<len(entries) else None
        order=local_window_order(client.position,goals,next_point) if width else list(range(len(goals)))
        selected=goals[order[0]]
        ordered_goals=[goals[i] for i in order]+[goal for _,goal in entries[end:]]
        self._route_keys=[self._goal_key(goal) for goal in ordered_goals]
        if selected[1]=='clear':self._sweep_active_channel=selected[2]
        self.stats['annular_sweep_decisions']=self.stats.get('annular_sweep_decisions',0)+1
        return selected


class StrictAnnularSweepPolicy(AnnularSweepMixin,OpticalBandPolicy):pass
class FrontierAnnularSweepPolicy(StrictAnnularSweepPolicy):sweep_backward_grace_deg=20.
class LocalAnnularSweepPolicy(StrictAnnularSweepPolicy):
    sweep_window_deg=25.
    sweep_backward_grace_deg=20.
class UnlockedAnnularSweepPolicy(LocalAnnularSweepPolicy):sweep_stick_to_source=False
class AggressiveLocalAnnularSweepPolicy(AnnularSweepMixin,AggressiveBandPolicy):
    sweep_window_deg=25.
    sweep_backward_grace_deg=20.
    sweep_reference_class=AggressiveBandPolicy


if __name__=='__main__':
    from problem3.experiments_v3.benchmark import run,generate_suite,ROOT
    from problem3.experiments_v3.coverage_family_tuning import fingerprints
    import sys,json
    n=int(sys.argv[1]) if len(sys.argv)>1 else 48
    requested=sys.argv[2:]
    classes=(OpticalBandPolicy,StrictAnnularSweepPolicy,FrontierAnnularSweepPolicy,LocalAnnularSweepPolicy,UnlockedAnnularSweepPolicy,AggressiveBandPolicy,AggressiveLocalAnnularSweepPolicy)
    if requested:classes=tuple(cls for cls in classes if cls.__name__ in requested)
    before=fingerprints();cases=generate_suite(3,'development_v2',n);results={}
    for cls in classes:
        r=run(cls,cases);results[cls.__name__]=r
        print(cls.__name__,{k:v for k,v in r.items() if k!='rows'},flush=True)
        reference_class=getattr(cls,'sweep_reference_class',OpticalBandPolicy)
        if cls not in (OpticalBandPolicy,AggressiveBandPolicy) and reference_class.__name__ in results:
            reference=results[reference_class.__name__]['rows'];unchanged=triggered=0
            for old,new in zip(reference,r['rows']):
                if not new['policy'].get('zero_origin_geometry',{}).get('triggered',False):
                    if old['sim']!=new['sim']:raise RuntimeError('A nonempty-origin physical trajectory changed')
                    unchanged+=1
                else:triggered+=1
            print({'unchanged_nonempty_origin_cases':unchanged,'empty_origin_triggered_cases':triggered},flush=True)
        if before!=fingerprints():raise RuntimeError('Frozen dependency fingerprint changed during comparison')
        suffix=('_'+('_'.join(requested))) if requested else ''
        (ROOT/f'problem3/results/iterations_v3/annular_sweep_{n}{suffix}.json').write_text(json.dumps({'dependencies':before,'branches':results},ensure_ascii=False,indent=2),encoding='utf8')
