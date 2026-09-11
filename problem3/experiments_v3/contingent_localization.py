"""Value a complete executable localization controller, rather than a residual.

PredictionClient contains only a synthetic source sampled from the current
public polygon. It is never constructed from real simulator source data.
Actual execution uses exactly the TerminalPolicy evaluated by the predictor.
"""
from __future__ import annotations
import copy,math
from problem3.geometry import distance,enclosing_circle,polygon_centroid
from problem3.policy import SearchPolicy as LegacyPolicy
from problem3.experiments_v3.policy import NegativeMixin,LocalizationMixin,IncrementalMixin
from problem3.experiments_v3.negative_disks import NegativeDiskMixin
from problem3.experiments_v3.journey import ClearRegionMixin
from problem3.experiments_v3.lookahead import LookaheadMixin
from problem3.experiments_v3.coverage_family_tuning import get_policy

Base=get_policy(9,1700.)


class TerminalPolicy(ClearRegionMixin,NegativeDiskMixin,NegativeMixin,LocalizationMixin,LegacyPolicy):
    """At most five ordinary geometric probes, then the existing optical cover."""


class StepTerminalPolicy(IncrementalMixin,TerminalPolicy):pass
class LookaheadStepTerminalPolicy(LookaheadMixin,StepTerminalPolicy):pass


class PredictionClient:
    def __init__(self,start,current_channel,channel,hypothesis,radius,noise,observations):
        self.position=start;self.current_channel=current_channel
        self.channel=channel;self.hypothesis=hypothesis;self.radius=radius;self.noise=noise
        self.old_observations=observations
        self.virtual_time_s=0.;self.actions=0;self.success=False
        self.measurements={}
    def check_budget(self):
        if self.actions>10000:raise RuntimeError('Unexpectedly unbounded prediction controller')
    def _move(self,point):
        self.virtual_time_s+=distance(self.position,point)/5.;self.position=point;self.actions+=1
    def measure(self,point,channel):
        assert channel==self.channel
        self._move(point);self.virtual_time_s+=5.+(channel!=self.current_channel);self.current_channel=channel
        if self.success or distance(point,self.hypothesis)>self.radius:return dict(accepted=True,measure_result='no_signal')
        if distance(point,self.hypothesis)<=5.:return dict(accepted=True,measure_result='near')
        key=tuple(round(v,7) for v in point)
        if key not in self.measurements:
            old=next((angle for anchor,angle in self.old_observations if distance(point,anchor)<1e-7),None)
            angle=math.degrees(math.atan2(self.hypothesis[1]-point[1],self.hypothesis[0]-point[0]))
            self.measurements[key]=old if old is not None else round((angle+self.noise)%360,2)%360
        return dict(accepted=True,measure_result='direction',svd_deg=self.measurements[key])
    def clear(self,point,channel):
        assert channel==self.channel
        self._move(point);success=distance(point,self.hypothesis)<=20.+1e-9 and not self.success
        self.virtual_time_s+=5. if success else 3.
        self.success|=success
        return dict(accepted=True,clear_result='success' if success else 'no_target_in_range')


def clone_terminal(parent,channel):
    cls=getattr(parent,'contingent_terminal_type',TerminalPolicy)
    terminal=cls(config=copy.copy(parent.config))
    terminal.regions[channel]=list(parent.regions[channel])
    terminal.observations[channel]=list(parent.observations[channel])
    terminal.negative_history={channel:list(getattr(parent,'negative_history',{}).get(channel,[]))}
    return terminal


def run_terminal(terminal,client,channel,first_point):
    terminal._measure(client,first_point,channel)
    for _ in range(8):
        if channel in terminal.cleared:return
        terminal._localize(channel,client)
    raise RuntimeError('Terminal controller did not clear its source')


class ContingentMixin:
    contingent_enabled=True
    contingent_noise=(-1.,0.,1.)
    contingent_radius_quadrature=True

    def _contingent_candidates(self,channel,client):
        state=getattr(self,'_local_state',{}).get(channel,{})
        original=super()._probe_point(channel,client,state.get('count',0))
        if not self.contingent_enabled:return [original]
        polygon=self.regions[channel];anchor,bearing=self.observations[channel][-1]
        theta=math.radians(bearing);forward=(math.cos(theta),math.sin(theta));side=(-forward[1],forward[0])
        projs=[(p[0]-anchor[0])*forward[0]+(p[1]-anchor[1])*forward[1] for p in polygon]
        points=[original]
        for quantile in (.25,.75):
            step=min(projs)+quantile*(max(projs)-min(projs));width=max(25.,min(100.,.05*step))
            for sign in (-1.,1.):points.append((anchor[0]+step*forward[0]+sign*width*side[0],anchor[1]+step*forward[1]+sign*width*side[1]))
        history=[p for p,_ in self.observations[channel]]+getattr(self,'negative_history',{}).get(channel,[])
        result=[]
        for point in points:
            if all(distance(point,p)>=2. for p in history) and all(distance(point,p)>1. for p in result):result.append(point)
        return result or [original]

    def _choose_contingent(self,channel,client):
        candidates=self._contingent_candidates(channel,client)
        if len(candidates)==1:return candidates[0]
        polygon=self.regions[channel];positives=self.observations[channel]
        negatives=getattr(self,'negative_history',{}).get(channel,[])
        nodes=self._rollout_nodes(polygon,positives,negatives)
        if not nodes:return candidates[0]
        best=None;total_actions=0;failures=0
        for point in candidates:
            score=0.
            for weight,source,rlo,rhi in nodes:
                if self.contingent_radius_quadrature and rhi-rlo>1e-6:
                    radii=[rlo+(rhi-rlo)*(1+s/math.sqrt(3))/2 for s in (-1.,1.)]
                else:radii=[(rlo+rhi)/2]
                for radius in radii:
                    for noise in self.contingent_noise:
                        terminal=clone_terminal(self,channel)
                        forecast=PredictionClient(client.position,client.current_channel,channel,source,radius,noise,positives)
                        try:
                            run_terminal(terminal,forecast,channel,point)
                            cost=forecast.virtual_time_s
                        except RuntimeError:
                            # A hypothetical point near an outward numerical
                            # boundary may violate exact R feasibility. It may
                            # penalize a candidate but never affect real bounds.
                            cost=100000.;failures+=1
                        total_actions+=forecast.actions
                        score+=weight*cost/(len(radii)*len(self.contingent_noise))
            if best is None or score<best[0]:best=(score,point)
        self.stats['contingent_prediction_actions']=self.stats.get('contingent_prediction_actions',0)+total_actions
        self.stats['contingent_prediction_failures']=self.stats.get('contingent_prediction_failures',0)+failures
        return best[1]

    def _localize(self,channel,client):
        if enclosing_circle(self.regions[channel])[1]<=60.:return super()._localize(channel,client)
        point=self._choose_contingent(channel,client)
        terminal=clone_terminal(self,channel)
        run_terminal(terminal,client,channel,point)
        self.regions[channel]=terminal.regions[channel]
        self.observations[channel]=terminal.observations[channel]
        self.negative_history[channel]=terminal.negative_history[channel]
        self.cleared.update(terminal.cleared)
        for key,value in terminal.stats.items():self.stats[key]=self.stats.get(key,0)+value
        self.stats['contingent_completed_sources']=self.stats.get('contingent_completed_sources',0)+1
        return True


class ContingentPolicy(ContingentMixin,Base):pass
class TerminalOnlyPolicy(ContingentPolicy):contingent_enabled=False


class InterleavedContingentMixin(ContingentMixin):
    """The same continuation rule yields after each radio read to global routing.

    Neighbor observations may tighten the target while it is waiting. Those
    new public bounds are copied in before the next continuation step.
    """
    contingent_terminal_type=StepTerminalPolicy
    def _localize(self,channel,client):
        if not hasattr(self,'_terminal_continuations'):self._terminal_continuations={}
        if channel not in self._terminal_continuations:
            if enclosing_circle(self.regions[channel])[1]<=60.:
                return super(ContingentMixin,self)._localize(channel,client)
            point=self._choose_contingent(channel,client)
            self._measure(client,point,channel)
            if channel in self.cleared:return True
            terminal=self.contingent_terminal_type(config=copy.copy(self.config))
            self._terminal_continuations[channel]=terminal
            self.stats['interleaved_contingent_sources']=self.stats.get('interleaved_contingent_sources',0)+1
            return False
        terminal=self._terminal_continuations[channel]
        terminal.regions[channel]=list(self.regions[channel])
        terminal.observations[channel]=list(self.observations[channel])
        terminal.negative_history={channel:list(self.negative_history.get(channel,[]))}
        terminal.stats={key:0 for key in terminal.stats}
        success=terminal._localize(channel,client)
        self.regions[channel]=terminal.regions[channel]
        self.observations[channel]=terminal.observations[channel]
        self.negative_history[channel]=terminal.negative_history[channel]
        self.cleared.update(terminal.cleared)
        for key,value in terminal.stats.items():self.stats[key]=self.stats.get(key,0)+value
        if success:self._terminal_continuations.pop(channel)
        return success


class InterleavedContingentPolicy(InterleavedContingentMixin,Base):pass
class InterleavedTerminalOnlyPolicy(InterleavedContingentPolicy):contingent_enabled=False
class FullControllerRolloutPolicy(InterleavedContingentPolicy):contingent_terminal_type=LookaheadStepTerminalPolicy
class FullControllerControlPolicy(FullControllerRolloutPolicy):contingent_enabled=False


def verify_prediction_client():
    from problem3.simulator import LocalSimulator
    source=(700.,-300.);case={'seed':1,'sources':[dict(channel=7,x=source[0],y=source[1],radius=1250.,orientation_deg=None)]}
    checked=0
    actions=[('measure',(0.,0.)),('measure',(701.,-300.)),('measure',(2200.,0.)),
             ('measure',(690.,-280.)),('measure',(690.,-280.)),
             ('clear',(690.,-280.)),('clear',(690.,-300.)),('measure',(690.,-300.))]
    for noise in (-1.,0.,1.):
        simulator=LocalSimulator(case);simulator.enter();simulator._error=lambda channel:noise
        client=PredictionClient((0.,0.),1,7,source,1250.,noise,[])
        for action,point in actions:
            observed=getattr(simulator,action)(point,7);predicted=getattr(client,action)(point,7)
            key='measure_result' if action=='measure' else 'clear_result'
            assert observed[key]==predicted[key] and observed.get('svd_deg')==predicted.get('svd_deg')
            assert abs(simulator.virtual_time_s-client.virtual_time_s)<1e-8
            checked+=1
    return {'prediction_client_transition_checks':checked,'includes_fixed_point_repeat_and_failed_clear':True}


if __name__=='__main__':
    from problem3.experiments_v3.benchmark import run,generate_suite,ROOT
    import sys,json
    if len(sys.argv)>1 and sys.argv[1]=='--check':print(verify_prediction_client());raise SystemExit(0)
    n=int(sys.argv[1]) if len(sys.argv)>1 else 48
    requested=sys.argv[2:];classes=(Base,TerminalOnlyPolicy,ContingentPolicy,InterleavedContingentPolicy,InterleavedTerminalOnlyPolicy,FullControllerRolloutPolicy,FullControllerControlPolicy)
    if requested:classes=tuple(cls for cls in classes if cls.__name__ in requested)
    cases=generate_suite(3,'development_v2',n);results={}
    for cls in classes:
        r=run(cls,cases);results[cls.__name__]=r
        print(cls.__name__,{k:v for k,v in r.items() if k!='rows'},flush=True)
        print({key:sum(row['policy'].get(key,0) for row in r['rows']) for key in ('contingent_prediction_actions','contingent_prediction_failures','contingent_completed_sources')},flush=True)
        suffix=('_'+('_'.join(requested))) if requested else ''
        (ROOT/f'problem3/results/iterations_v3/contingent_localization_{n}{suffix}.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
