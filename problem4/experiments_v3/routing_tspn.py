"""Variable service-point radio scheduling with bounded staged localization."""
import math
from problem3.geometry import distance,polygon_centroid,enclosing_circle
from problem4.routing import two_opt,or_opt,route_length
from problem4.policy import SearchPolicy as ProductionPolicy
from problem4.experiments_v3.routing import predicted_radius,EnrouteMixin

class VariableServiceMixin:
    service_uncertainty_weight=1.
    service_max_stages=8
    service_min_uncertainty=55.
    service_width=.08
    service_refine_route=True
    def _radio_candidates(self,channel):
        polygon=self.regions[channel];anchor,bearing=self.observations[channel][-1];theta=math.radians(bearing)
        forward=(math.cos(theta),math.sin(theta));side=(-forward[1],forward[0]);projections=[(p[0]-anchor[0])*forward[0]+(p[1]-anchor[1])*forward[1] for p in polygon]
        low,high=min(projections),max(projections);candidates=[]
        for quantile in (.1,.25,.4,.55,.7,.85,.95):
            step=low+(high-low)*quantile;width=max(15.,min(140.,step*self.service_width),step*math.tan(math.radians(self.config.bearing_error_deg))+.01)
            mid=(anchor[0]+step*forward[0],anchor[1]+step*forward[1])
            candidates += [(mid[0]+sign*width*side[0],mid[1]+sign*width*side[1]) for sign in (-1,1)]
        attempted=getattr(self,'_service_attempts',{}).get(channel,[])
        candidates=[p for p in candidates if all(distance(p,prev)>5 for prev in attempted)]
        return candidates
    def _service_goal(self,client,pending):
        super()._route_goal(client,pending)
        mapping={self._goal_key((p,'scan',i)):(p,'scan',i) for i,p in enumerate(pending)}
        mapping.update({('clear',ch):(polygon_centroid(poly),'clear',ch) for ch,poly in self.regions.items() if ch not in self.cleared})
        goals=[mapping[k] for k in self._route_keys]
        for _ in range(2):
            for i,goal in enumerate(goals):
                point,kind,channel=goal
                if kind=='scan':continue
                polygon=self.regions[channel];center,radius=enclosing_circle(polygon)
                if radius<=self.service_min_uncertainty or len(getattr(self,'_service_attempts',{}).get(channel,[]))>=self.service_max_stages:continue
                candidates=self._radio_candidates(channel)
                if not candidates:continue
                previous=client.position if i==0 else goals[i-1][0];nxt=goals[i+1][0] if i+1<len(goals) else None;anchor,_=self.observations[channel][-1]
                def objective(p):
                    estimated,probability=predicted_radius(polygon,anchor,p)
                    uncertainty=estimated*probability+radius*(1-probability)
                    return distance(previous,p)+(distance(p,nxt) if nxt else 0)+self.service_uncertainty_weight*uncertainty
                selected=min(candidates,key=objective);goals[i]=(selected,'probe',channel)
        if self.service_refine_route:
            points=[g[0] for g in goals]+[client.position];matrix=[[distance(a,b) for b in points] for a in points]
            route=or_opt(two_opt(list(range(len(goals))),matrix),matrix,max_moves=8)
            goals=[goals[i] for i in route]
        return goals[0]
    def run(self,client):
        pending=self.coverage_points();self._service_attempts={}
        while pending or any(ch not in self.cleared for ch in self.regions):
            client.check_budget();point,action,identifier=self._service_goal(client,pending)
            if action=='scan':self._scan(client,pending.pop(identifier))
            elif action=='probe':
                self._service_attempts.setdefault(identifier,[]).append(point)
                result=self._measure(client,point,identifier)
                self.stats['staged_probes']=self.stats.get('staged_probes',0)+1
                if result=='no_signal':self._clip_history(identifier)
            else:self._localize(identifier,client)
            self._update_neighbors(client)
            if len(self.cleared)==16:return self._result('maximum_source_count_cleared',not pending)
        return self._result('certified_coverage_and_all_detected_cleared',True)

def get_class(name):
    attrs={}
    if 'low' in name:attrs['service_uncertainty_weight']=.25
    if 'high' in name:attrs['service_uncertainty_weight']=3.
    if 'wide' in name:attrs['service_width']=.2
    if 'fixedorder' in name:attrs['service_refine_route']=False
    bases=(EnrouteMixin,VariableServiceMixin,ProductionPolicy) if 'enroute' in name else (VariableServiceMixin,ProductionPolicy)
    return type(name,bases,attrs)
